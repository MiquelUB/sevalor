"""Servei unificat de conciliació post-obra, evidències PWA i auditoria d'OT (Zero Mock Data)."""

from __future__ import annotations

import base64
import binascii
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

import filetype  # type: ignore[import-untyped]
from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Article,
    AuditoriaPostObra,
    CapaAnotacio,
    CapaVectorial,
    Client,
    EinaCustodia,
    FullaPicking,
    HistorialAssignacioVehicle,
    Incidencia,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    OrdreTreballOperari,
    OrdreTreballTramTemps,
    PlanolBase,
    Pressupost,
    TiquetDespesa,
    Usuari,
    Vehicle,
)
from app.services.barema_service import (
    calcular_cost_ma_obra_real,
    obtenir_barema_empresa,
    resoldre_preu_hora_control_panel,
)
from app.services.sovereign_storage import SovereignStorageGateway

logger = logging.getLogger("sevalor.reconciliacio_ot")

ESTATS_OT_CONCLOSES = frozenset(
    {
        "COMPLERT",
        "COMPLETADA",
        "FINALITZADA",
        "TANCADA",
        "EXECUTADA_PENDENT_VALIDACIO",
        "ALBARA_SIGNAT",
        "VALIDADA_PER_FACTURAR",
        "PREFACTURADA",
        "FACTURADA",
    }
)

ESTATS_OT_NO_CONCLOSES = frozenset(
    {
        "PENDENT",
        "ASSIGNADA",
        "PROGRAMADA",
        "EN_RUTA",
        "EN_CURS",
        "EN_OBRA",
        "PAUSADA",
        "BLOQUEJADA",
        "INCIDENCIA",
    }
)

LLINDAR_MERMA_CONTINUA_PCT = 250.0
LLINDAR_MARGE_CRITIC_PCT = 15.0
MAX_SIGNATURA_BYTES = 5 * 1024 * 1024  # 5 MB

_DATA_URI_IMG_RE = re.compile(
    r"^data:image/(png|webp|jpeg|jpg);base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_ALLOWED_IMG_EXTS = {"png": "image/png", "webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg"}


def _q2(val: Decimal | float | int | None) -> Decimal:
    return Decimal(str(val if val is not None else 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _q3(val: Decimal | float | int | None) -> Decimal:
    return Decimal(str(val if val is not None else 0)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )


def _es_rol_costos_interns(rol_usuari: Optional[str]) -> bool:
    """Només BOSS i SECRETARIA poden veure costos interns (PMP, cost mà d'obra, marges)."""
    return str(rol_usuari or "").upper() in {"BOSS", "SECRETARIA"}


def validar_i_decodificar_signatura_base64(
    signatura_base64: str,
    *,
    exigir_magic_bytes: bool = False,
) -> Tuple[bytes, str, str]:
    """Valida i descodifica una signatura digital en base64.

    Args:
        signatura_base64: Cadena base64 pura o Data URI (`data:image/png;base64,...`).
        exigir_magic_bytes: Si True, exigeix capçalera binària PNG/WebP/JPEG real verificada per `filetype`.

    Returns:
        Tupla `(raw_bytes, ext, content_type)`.

    Raises:
        HTTPException(422): Si el format, MIME, base64 o mida són invàlids.
    """
    raw_str = (signatura_base64 or "").strip()
    if not raw_str:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La signatura digital no pot estar buida.",
        )

    declared_ext: Optional[str] = None
    b64_body = raw_str
    if raw_str.lower().startswith("data:"):
        match = _DATA_URI_IMG_RE.match(raw_str)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Format de signatura no permès. Només s'accepten imatges PNG, WebP o JPEG.",
            )
        declared_ext = match.group(1).lower()
        if declared_ext == "jpeg":
            declared_ext = "jpg"
        b64_body = match.group(2).strip()

    try:
        raw_bytes = base64.b64decode(b64_body, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La signatura base64 està corrupta o no és vàlida.",
        ) from exc

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El contingut binari de la signatura és buit.",
        )
    if len(raw_bytes) > MAX_SIGNATURA_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La signatura supera el límit màxim de 5 MB.",
        )

    kind = filetype.guess(raw_bytes)
    detected_ext: Optional[str] = None
    if kind is not None and kind.extension in _ALLOWED_IMG_EXTS:
        detected_ext = "jpg" if kind.extension == "jpeg" else str(kind.extension)
    elif raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_ext = "png"
    elif raw_bytes.startswith(b"\xff\xd8\xff"):
        detected_ext = "jpg"
    elif len(raw_bytes) >= 12 and raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
        detected_ext = "webp"

    if exigir_magic_bytes and detected_ext is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La signatura no conté Magic Bytes d'imatge vàlids (PNG, WebP o JPEG).",
        )

    final_ext = detected_ext or declared_ext
    if final_ext not in _ALLOWED_IMG_EXTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No s'ha pogut verificar el format d'imatge de la signatura.",
        )

    return raw_bytes, final_ext, _ALLOWED_IMG_EXTS[final_ext]


async def desar_signatura_client_ot(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    ordre_treball_id: uuid.UUID,
    signatura_base64: str,
    *,
    exigir_magic_bytes: bool = False,
) -> str:
    """Valida i desa la imatge de signatura del client al disc sobirà de l'empresa."""
    raw_bytes, ext, content_type = validar_i_decodificar_signatura_base64(
        signatura_base64,
        exigir_magic_bytes=exigir_magic_bytes,
    )
    nom_fitxer = f"ot_{ordre_treball_id}_signatura_client.{ext}"
    return await SovereignStorageGateway.pujar_fitxer_binari(
        db=db,
        empresa_id=empresa_id,
        categoria="ots_historic",
        nom_fitxer=nom_fitxer,
        content=raw_bytes,
        content_type=content_type,
    )


def calcular_estat_disclaimer_ot(
    estat_ot: str,
    *,
    te_tram_obert: bool,
    validada_per_id: Optional[uuid.UUID],
    factura_id: Optional[uuid.UUID],
    factura_estat_document: Optional[str],
) -> Dict[str, Any]:
    """Determina el disclaimer canònic del header de la Fulla 360° d'una OT."""
    estat_up = str(estat_ot or "").upper()
    if factura_id is not None:
        if str(factura_estat_document or "").upper() == "ESBORRANY_PREFACTURA":
            return {
                "codi": "PREFACTURADA",
                "titol": "CONCLOSA — Pendent de facturar (Pre-factura en esborrany)",
                "descripcio": "La pre-factura Sèrie PRE està generada i pendent d'emissió fiscal definitiva.",
                "nivell": "warning",
                "es_conclosa": True,
                "es_facturada": False,
                "pot_validar": False,
                "pot_prefacturar": False,
            }
        return {
            "codi": "FACTURADA",
            "titol": "CONCLOSA I FACTURADA — Factura Veri*factu emesa",
            "descripcio": "La tasca té una factura legal emesa i inalterable associada.",
            "nivell": "success",
            "es_conclosa": True,
            "es_facturada": True,
            "pot_validar": False,
            "pot_prefacturar": False,
        }

    es_conclosa = estat_up in ESTATS_OT_CONCLOSES and not te_tram_obert
    if not es_conclosa:
        return {
            "codi": "NO_CONCLOSA",
            "titol": "NO CONCLOSA — La feina no ha finalitzat",
            "descripcio": (
                "Hi ha un tram de temps actiu o l'operari encara no ha tancat l'ordre a camp. "
                "No es pot validar ni passar a pre-facturació."
            ),
            "nivell": "neutral",
            "es_conclosa": False,
            "es_facturada": False,
            "pot_validar": False,
            "pot_prefacturar": False,
        }

    es_validada = estat_up == "VALIDADA_PER_FACTURAR" or validada_per_id is not None
    if not es_validada:
        return {
            "codi": "CONCLOSA_PENDENT_VALIDACIO",
            "titol": "CONCLOSA A CAMP — Pendent de conciliació i validació",
            "descripcio": (
                "Revisa la documentació de la PWA (fotos QA, signatura, hores, materials i incidències) "
                "i valida la fulla abans de passar-la a pre-facturació."
            ),
            "nivell": "attention",
            "es_conclosa": True,
            "es_facturada": False,
            "pot_validar": True,
            "pot_prefacturar": False,
        }

    return {
        "codi": "VALIDADA_PENDENT_FACTURAR",
        "titol": "CONCLOSA I VALIDADA — Pendent de facturar",
        "descripcio": "La fulla 360° està actualitzada i conciliada. Llista per passar a pre-facturació.",
        "nivell": "info",
        "es_conclosa": True,
        "es_facturada": False,
        "pot_validar": True,
        "pot_prefacturar": True,
    }


class ReconciliacioOTService:
    """Motor real (Zero-Mock) de conciliació documental, tècnica i econòmica d'Ordres de Treball."""

    @classmethod
    async def obtenir_conciliacio_completa(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        ordre_treball_id: uuid.UUID,
        rol_usuari: Optional[str] = "ENGINYER",
    ) -> Dict[str, Any]:
        """Consolida totes les dades reals de camp (PWA), oficina i facturació d'una OT.

        Respecta la Barrera Econòmica:
        - `ENGINYER` veu totes les dades tècniques i les dades comercials del client
          (pressupost, tarifa PVP/h, PVP materials, pre-factura i factura final).
        - Només `BOSS` i `SECRETARIA` reben costos interns (PMP, cost mà d'obra real, marges).
        """
        mostrar_costos_interns = _es_rol_costos_interns(rol_usuari)

        ot = (
            await db.execute(
                select(OrdreTreball).where(
                    OrdreTreball.id == ordre_treball_id,
                    OrdreTreball.empresa_id == empresa_id,
                )
            )
        ).scalars().first()
        if not ot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ordre de treball no trobada",
            )

        # 1. Entitats base relacionades
        client_obj = (
            await db.execute(
                select(Client).where(Client.id == ot.client_id, Client.empresa_id == empresa_id)
            )
        ).scalars().first()

        validador_nom: Optional[str] = None
        if ot.validada_per_id:
            val_u = (
                await db.execute(
                    select(Usuari).where(
                        Usuari.id == ot.validada_per_id,
                        Usuari.empresa_id == empresa_id,
                    )
                )
            ).scalars().first()
            if val_u:
                validador_nom = f"{val_u.nom} {val_u.cognoms or ''}".strip()

        vehicle_info: Optional[Dict[str, Any]] = None
        veh_cost_per_km = Decimal("0.32")
        veh_preu_km_facturable = Decimal("0.45")
        km_imputats_val = int(ot.km_imputats or 0)
        odometre_inici_reg: Optional[int] = None
        odometre_fi_reg: Optional[int] = None
        vehicle_pickout_estat: str = "PENDENT"

        if ot.vehicle_id:
            veh = (
                await db.execute(
                    select(Vehicle).where(
                        Vehicle.id == ot.vehicle_id,
                        Vehicle.empresa_id == empresa_id,
                    )
                )
            ).scalars().first()
            if veh:
                c_km_raw = getattr(veh, "cost_per_km_eur", None)
                if c_km_raw is not None and Decimal(str(c_km_raw)) > 0:
                    veh_cost_per_km = Decimal(str(c_km_raw))
                p_km_raw = getattr(veh, "preu_km_exces_eur", None)
                if p_km_raw is not None and Decimal(str(p_km_raw)) > 0:
                    veh_preu_km_facturable = Decimal(str(p_km_raw))

                # Comprovar si hi ha odòmetre registrat o moviment d'assignació
                odo_actual = getattr(veh, "odometre_acumulat", None)
                if odo_actual is not None:
                    odometre_fi_reg = int(odo_actual)

                # Si l'OT té data de planificació, consultar si hi ha historial
                hist_row = (
                    await db.execute(
                        select(HistorialAssignacioVehicle)
                        .where(
                            HistorialAssignacioVehicle.empresa_id == empresa_id,
                            HistorialAssignacioVehicle.vehicle_id == veh.id,
                        )
                        .order_by(HistorialAssignacioVehicle.data_inici.desc())
                    )
                ).scalars().first()
                if hist_row:
                    odometre_inici_reg = hist_row.odometre_inici
                    if hist_row.odometre_fi is not None:
                        odometre_fi_reg = hist_row.odometre_fi
                        vehicle_pickout_estat = "COMPLERT"
                    elif hist_row.data_fi is not None:
                        vehicle_pickout_estat = "COMPLERT"
                    else:
                        vehicle_pickout_estat = "RETORNAT" if str(ot.estat or "").upper() in ESTATS_OT_CONCLOSES else "EN_TRAJECTE"
                elif str(ot.estat or "").upper() in ESTATS_OT_CONCLOSES:
                    vehicle_pickout_estat = "COMPLERT"

                # Si no s'havia imputat km manualment però tenim odòmetres, derivar km_imputats
                if km_imputats_val <= 0 and odometre_inici_reg is not None and odometre_fi_reg is not None:
                    km_diff = odometre_fi_reg - odometre_inici_reg
                    if km_diff > 0:
                        km_imputats_val = km_diff

                valor_desplacament_pvp = _q2(Decimal(km_imputats_val) * veh_preu_km_facturable)

                vehicle_info = {
                    "id": str(veh.id),
                    "matricula": veh.matricula,
                    "marca_model": f"{veh.marca} {veh.model}".strip(),
                    "carnet_necessari": getattr(veh, "carnet_necessari", None),
                    "cost_per_km_eur": float(_q2(veh_cost_per_km)) if mostrar_costos_interns else None,
                    "preu_km_facturable": float(_q2(veh_preu_km_facturable)),
                    "km_imputats": km_imputats_val,
                    "odometre_inici": odometre_inici_reg,
                    "odometre_fi": odometre_fi_reg,
                    "estat_pickout": vehicle_pickout_estat,
                    "valor_desplacament_pvp": float(valor_desplacament_pvp),
                }

        # Quadrilla assignada (Cap de colla + Operaris)
        ops_rows = (
            await db.execute(
                select(OrdreTreballOperari, Usuari)
                .join(Usuari, OrdreTreballOperari.operari_id == Usuari.id)
                .where(
                    OrdreTreballOperari.empresa_id == empresa_id,
                    OrdreTreballOperari.ordre_treball_id == ot.id,
                )
                .order_by(OrdreTreballOperari.es_cap_de_colla.desc(), Usuari.nom.asc())
            )
        ).all()
        operaris_list: List[Dict[str, Any]] = [
            {
                "id": str(u.id),
                "nom": f"{u.nom} {u.cognoms or ''}".strip(),
                "rol": u.rol,
                "es_cap_de_colla": bool(oto.es_cap_de_colla),
                "telefon": u.telefon,
            }
            for oto, u in ops_rows
        ]

        planol_info: Optional[Dict[str, Any]] = None
        if ot.planol_id:
            pl = (
                await db.execute(
                    select(PlanolBase).where(
                        PlanolBase.id == ot.planol_id,
                        PlanolBase.empresa_id == empresa_id,
                    )
                )
            ).scalars().first()
            if pl:
                planol_info = {
                    "id": str(pl.id),
                    "titol": pl.titol,
                    "codi_referencia": pl.codi_referencia,
                    "tipus_fitxer": pl.tipus_fitxer,
                }

        # 2. Trams de temps, hores reals i desviacions GPS
        trams = list(
            (
                await db.execute(
                    select(OrdreTreballTramTemps)
                    .where(
                        OrdreTreballTramTemps.empresa_id == empresa_id,
                        OrdreTreballTramTemps.ordre_treball_id == ot.id,
                    )
                    .order_by(OrdreTreballTramTemps.hora_inici.asc())
                )
            )
            .scalars()
            .all()
        )
        te_tram_obert = any(t.hora_fi is None for t in trams) or (
            str(ot.estat or "").upper() == "EN_CURS"
            and ot.hora_inici_real is not None
            and ot.hora_fi_real is None
        )
        temps_segons = sum(int(t.durada_segons or 0) for t in trams if t.hora_fi is not None)
        hores_reals = _q2(ot.hores_imputades_facturables or 0)
        if hores_reals <= Decimal("0.00") and temps_segons > 0:
            hores_reals = _q2(Decimal(temps_segons) / Decimal("3600"))

        hores_previstes = Decimal("0.00")
        if ot.hora_inici_prevista and ot.hora_fi_prevista and ot.hora_fi_prevista > ot.hora_inici_prevista:
            diff_sec = (ot.hora_fi_prevista - ot.hora_inici_prevista).total_seconds()
            hores_previstes = _q2(Decimal(str(diff_sec)) / Decimal("3600"))
        desviacio_hores = _q2(hores_reals - hores_previstes)

        # Càlcul de format humà sexagesimal per a conciliació exacta (ex: 1.43h -> 1h 26m)
        total_min_reals = int(round(float(hores_reals) * 60))
        h_reals_int = total_min_reals // 60
        m_reals_int = total_min_reals % 60
        hores_reals_human = f"{h_reals_int}h {m_reals_int:02d}m" if hores_reals > 0 else "0h 00m"

        total_min_prev = int(round(float(hores_previstes) * 60))
        h_prev_int = total_min_prev // 60
        m_prev_int = total_min_prev % 60
        hores_previstes_human = f"{h_prev_int}h {m_prev_int:02d}m" if hores_previstes > 0 else "0h 00m"

        desviacions_gps: List[Dict[str, Any]] = []
        if ot.desviacio_geovalla or ot.justificacio_geovalla:
            desviacions_gps.append(
                {
                    "origen": "OT",
                    "justificacio": ot.justificacio_geovalla,
                    "foto_evidencia": bool(ot.foto_evidencia_desviacio),
                }
            )
        for idx, t in enumerate(trams, start=1):
            if t.desviacio_geovalla or t.justificacio_gps:
                desviacions_gps.append(
                    {
                        "origen": f"TRAM_{idx}",
                        "tram_id": str(t.id),
                        "justificacio": t.justificacio_gps,
                    }
                )

        # 3. Protocol de 3 Fotos QA al Disc Sobirà
        fotos_qa: Dict[str, bool] = {}
        for tipus_f in ("inicial", "intermedia", "final"):
            nom_f = f"ot_{ot.id}_foto_{tipus_f}.webp"
            try:
                exists_active = await SovereignStorageGateway.existeix_fitxer_categoria(
                    db=db,
                    empresa_id=empresa_id,
                    categoria="ots_actives",
                    nom_fitxer=nom_f,
                )
                if not exists_active:
                    exists_historic = await SovereignStorageGateway.existeix_fitxer_categoria(
                        db=db,
                        empresa_id=empresa_id,
                        categoria="ots_historic",
                        nom_fitxer=nom_f,
                    )
                    fotos_qa[tipus_f] = exists_historic
                else:
                    fotos_qa[tipus_f] = True
            except Exception:
                fotos_qa[tipus_f] = False
        protocol_fotos_complet = all(fotos_qa.values())

        # 4. Materials (Fulla de Picking + Furgoneta)
        pk_rows = (
            await db.execute(
                select(FullaPicking, LiniaPicking, Article, Magatzem)
                .join(LiniaPicking, LiniaPicking.picking_id == FullaPicking.id)
                .join(Article, LiniaPicking.article_id == Article.id)
                .outerjoin(Magatzem, LiniaPicking.magatzem_id == Magatzem.id)
                .where(
                    FullaPicking.empresa_id == empresa_id,
                    FullaPicking.ordre_treball_id == ot.id,
                )
                .order_by(LiniaPicking.created_at.asc())
            )
        ).all()

        materials_list: List[Dict[str, Any]] = []
        valor_materials_pvp_calc = Decimal("0.00")
        cost_materials_previst_pmp = Decimal("0.00")
        cost_materials_real_pmp = Decimal("0.00")
        cost_mermes_real_pmp = Decimal("0.00")
        estat_picking_global: Optional[str] = None
        alerta_consum_excessiu = False
        detall_merma_msgs: List[str] = []

        for fp, lp, art, mag in pk_rows:
            estat_picking_global = fp.estat_picking
            q_prev = _q3(lp.quantitat_prevista or 0)
            q_in = _q3(lp.quantitat_carregada_pick_in or 0)
            q_out = _q3(lp.quantitat_retornada_pick_out or 0)
            q_merma = _q3(lp.quantitat_mermada or 0)

            # Si hi ha pick_in registrat, consum real = max(0, pick_in - pick_out); si encara no hi ha pick_in, 0
            q_consum = max(Decimal("0.000"), _q3(q_in - q_out)) if q_in > 0 else Decimal("0.000")
            q_base_factura = q_consum if q_in > 0 else q_prev
            desviacio_q = _q3(q_consum - q_prev) if q_in > 0 else Decimal("0.000")

            pvp_u = _q2(art.preu_venda or 0)
            pmp_raw = art.preu_cost_mitja if float(art.preu_cost_mitja or 0) > 0 else art.preu_cost
            pmp_u = Decimal(str(pmp_raw or 0))

            sub_pvp = _q2(q_base_factura * pvp_u)
            valor_materials_pvp_calc += sub_pvp

            cost_prev_lin = _q2(q_prev * pmp_u)
            cost_real_lin = _q2(q_base_factura * pmp_u)
            cost_merma_lin = _q2(q_merma * pmp_u)
            cost_materials_previst_pmp += cost_prev_lin
            cost_materials_real_pmp += cost_real_lin
            cost_mermes_real_pmp += cost_merma_lin

            if q_prev > 0 and q_in > 0:
                ratio_pct = float((q_consum / q_prev) * Decimal("100"))
                if ratio_pct >= LLINDAR_MERMA_CONTINUA_PCT:
                    alerta_consum_excessiu = True
                    detall_merma_msgs.append(
                        f"Consum de {art.nom} excedit ({ratio_pct:.0f}% del previst: {float(q_consum)} vs {float(q_prev)})."
                    )

            origen_estoc = str(getattr(lp, "origen_estoc", None) or "NAU").upper()
            mat_item: Dict[str, Any] = {
                "linia_id": str(lp.id),
                "picking_id": str(fp.id),
                "article_id": str(art.id),
                "article_nom": art.nom,
                "referencia_inventari": art.referencia_inventari,
                "unitat_mesura": art.unitat_mesura or "UNITAT",
                "origen_estoc": origen_estoc,
                "magatzem_id": str(lp.magatzem_id) if lp.magatzem_id else None,
                "magatzem_nom": mag.nom if mag else None,
                "quantitat_prevista": float(q_prev),
                "quantitat_carregada_pick_in": float(q_in),
                "quantitat_retornada_pick_out": float(q_out),
                "quantitat_mermada": float(q_merma),
                "consum_real": float(q_consum),
                "desviacio_quantitat": float(desviacio_q),
                "consum_aplicat_magatzem": float(_q3(getattr(lp, "consum_aplicat_magatzem", 0) or 0)),
                "preu_venda_unitari": float(pvp_u),
                "subtotal_pvp": float(sub_pvp),
            }
            if mostrar_costos_interns:
                mat_item["preu_cost_pmp"] = float(_q2(pmp_u))
                mat_item["cost_real_pmp"] = float(cost_real_lin)
                mat_item["cost_merma_pmp"] = float(cost_merma_lin)
            else:
                mat_item["preu_cost_pmp"] = None
                mat_item["cost_real_pmp"] = None
                mat_item["cost_merma_pmp"] = None

            materials_list.append(mat_item)

        # 5. Eines en custòdia (incloses les assignades a l'OT o en custòdia dels operaris de la quadrilla)
        eina_conds = [EinaCustodia.ordre_treball_id == ot.id]
        colla_op_ids = [uuid.UUID(str(op["id"])) for op in operaris_list if op.get("id")]
        if ot.cap_de_colla_id and ot.cap_de_colla_id not in colla_op_ids:
            colla_op_ids.append(ot.cap_de_colla_id)

        if colla_op_ids:
            eina_conds.append(
                and_(
                    EinaCustodia.custodiat_per_operari_id.in_(colla_op_ids),
                    EinaCustodia.estat.in_(["CUSTODIADA", "EN_VEHICLE", "AVARIADA"]),
                )
            )

        eines_rows = list(
            (
                await db.execute(
                    select(EinaCustodia).where(
                        EinaCustodia.empresa_id == empresa_id,
                        or_(*eina_conds),
                    ).order_by(EinaCustodia.nom.asc())
                )
            )
            .scalars()
            .all()
        )
        # Deduplicar per ID
        seen_eines_ids = set()
        dedup_eines_rows = []
        for e in eines_rows:
            if e.id not in seen_eines_ids:
                seen_eines_ids.add(e.id)
                dedup_eines_rows.append(e)

        eines_list = [
            {
                "id": str(e.id),
                "nom": e.nom,
                "model": getattr(e, "model", None),
                "numero_serie": e.numero_serie,
                "estat": e.estat,
                "en_custodia_efectiva": bool(e.estat in ("CUSTODIADA", "EN_VEHICLE", "AVARIADA")),
                "requereix_pickout": bool(e.estat == "AVARIADA" or e.estat == "CUSTODIADA" or e.estat == "EN_VEHICLE"),
                "custodiat_per_id": str(e.custodiat_per_operari_id) if e.custodiat_per_operari_id else None,
            }
            for e in dedup_eines_rows
        ]

        # 6. Incidències d'obra vinculades a l'OT
        inc_rows = list(
            (
                await db.execute(
                    select(Incidencia)
                    .where(
                        Incidencia.empresa_id == empresa_id,
                        Incidencia.ordre_treball_id == ot.id,
                    )
                    .order_by(Incidencia.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        incidencies_list = [
            {
                "id": str(inc.id),
                "ambit": inc.ambit,
                "tipus": inc.tipus,
                "gravetat": inc.gravetat,
                "estat": inc.estat,
                "text_observacions": inc.text_observacions,
                "te_foto": bool(inc.foto_path),
                "te_audio": bool(inc.audio_path),
                "created_at": inc.created_at.isoformat() if inc.created_at else None,
            }
            for inc in inc_rows
        ]
        incidencies_obertes_count = sum(
            1 for inc in inc_rows if str(inc.estat or "").upper() not in {"VERD", "RESOLTA", "TANCADA"}
        )

        # 7. Tiquets de despesa de camp vinculats a l'OT
        tiquets_rows = list(
            (
                await db.execute(
                    select(TiquetDespesa)
                    .where(
                        TiquetDespesa.empresa_id == empresa_id,
                        TiquetDespesa.ordre_treball_id == ot.id,
                    )
                    .order_by(TiquetDespesa.data_tiquet.desc(), TiquetDespesa.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        total_tiquets_camp = _q2(sum((Decimal(str(t.import_total or 0)) for t in tiquets_rows), Decimal("0.00")))
        tiquets_list = []
        for tq in tiquets_rows:
            t_item: Dict[str, Any] = {
                "id": str(tq.id),
                "categoria": tq.categoria,
                "data_tiquet": tq.data_tiquet.isoformat() if tq.data_tiquet else None,
                "rao_social": tq.rao_social,
                "import_total": float(_q2(tq.import_total or 0)),
                "estat_aprovacio": tq.estat_aprovacio,
                "te_foto": bool(tq.foto_tiquet_path),
            }
            if mostrar_costos_interns:
                t_item["subcompte_pgc"] = tq.subcompte_pgc
                t_item["base_imposable"] = float(_q2(tq.base_imposable or 0))
                t_item["quota_iva"] = float(_q2(tq.quota_iva or 0))
            tiquets_list.append(t_item)

        # 8. Capes GIS As-Built vinculades a l'OT
        capes_vec = list(
            (
                await db.execute(
                    select(CapaVectorial)
                    .where(
                        CapaVectorial.empresa_id == empresa_id,
                        CapaVectorial.ordre_treball_id == ot.id,
                    )
                    .order_by(CapaVectorial.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        capes_anot = list(
            (
                await db.execute(
                    select(CapaAnotacio)
                    .where(
                        CapaAnotacio.empresa_id == empresa_id,
                        CapaAnotacio.ordre_treball_id == ot.id,
                    )
                    .order_by(CapaAnotacio.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        capes_gis_list: List[Dict[str, Any]] = [
            {
                "id": str(c.id),
                "tipus": "VECTORIAL",
                "nom": c.nom,
                "disciplina": c.disciplina,
                "color_hex": c.color_hex,
                "num_elements": len((c.geometries_geojson or {}).get("features", [])),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in capes_vec
        ] + [
            {
                "id": str(c.id),
                "tipus": "ANOTACIO",
                "nom": c.nom_capa,
                "disciplina": "GENERAL",
                "color_hex": "#0284c7",
                "num_elements": 0,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in capes_anot
        ]

        # 9. Pressupost vinculat (si n'hi ha al client / disc sobirà)
        pressupost_info: Optional[Dict[str, Any]] = None
        pressupost_linies_raw: List[Dict[str, Any]] = []
        try:
            pres_json_items = await SovereignStorageGateway.llegir_entitats_json(
                db, empresa_id, "pressupostos"
            )
            for item in pres_json_items:
                if isinstance(item, dict) and str(item.get("ordre_treball_id") or "") == str(ot.id):
                    pres_db = (
                        await db.execute(
                            select(Pressupost).where(
                                Pressupost.id == uuid.UUID(str(item["id"])),
                                Pressupost.empresa_id == empresa_id,
                            )
                        )
                    ).scalars().first()
                    if pres_db:
                        pressupost_linies_raw = list(item.get("linies") or [])
                        pressupost_info = {
                            "id": str(pres_db.id),
                            "numero": pres_db.numero,
                            "estat": pres_db.estat,
                            "total": float(_q2(pres_db.total or 0)),
                            "created_at": pres_db.created_at.isoformat() if pres_db.created_at else None,
                            "total_linies": len(pressupost_linies_raw),
                        }
                        break
        except Exception:
            pressupost_info = None

        # Detectar ítems de material del pressupost pendents de facturar o no inclosos al picking
        linies_pendents_facturar: List[Dict[str, Any]] = []
        if pressupost_linies_raw:
            picked_art_ids = {str(m["article_id"]) for m in materials_list if m.get("article_id")}
            picked_noms = {str(m["article_nom"]).strip().lower() for m in materials_list if m.get("article_nom")}
            for pl in pressupost_linies_raw:
                c_nom = str(pl.get("concepte") or "").strip()
                art_id_pl = str(pl.get("article_id") or "") if pl.get("article_id") else None
                es_mat = str(pl.get("tipus_linia") or "").upper() == "MATERIAL" or bool(art_id_pl) or "material" in str(pl.get("seccio") or "").lower()
                if es_mat:
                    coincideix = (art_id_pl and art_id_pl in picked_art_ids) or (c_nom.lower() in picked_noms)
                    if not coincideix:
                        linies_pendents_facturar.append({
                            "concepte": c_nom,
                            "quantitat": float(pl.get("quantitat") or 1.0),
                            "preu_unitari": float(pl.get("preu_unitari") or 0.0),
                            "subtotal": float(pl.get("subtotal") or 0.0),
                        })

        # 10. Pre-factura o Factura final vinculada a l'OT (via funció SECURITY DEFINER acotada a l'OT,
        # preservant intactes les polítiques RLS `economics_boss_only` sobre consultes globals)
        factura_info: Optional[Dict[str, Any]] = None
        res_fact_fn = await db.execute(
            text("SELECT public.obtenir_factura_comercial_ot(:emp_id, :ot_id)"),
            {"emp_id": empresa_id, "ot_id": ot.id},
        )
        raw_fact = res_fact_fn.scalar_one_or_none()
        if isinstance(raw_fact, dict):
            factura_info = {
                "id": str(raw_fact["id"]),
                "serie": raw_fact.get("serie"),
                "numero_factura": raw_fact.get("numero_factura"),
                "estat_document": raw_fact.get("estat_document"),
                "estat_cobrament": raw_fact.get("estat_cobrament"),
                "data_emissio": raw_fact.get("data_emissio"),
                "data_venciment": raw_fact.get("data_venciment"),
                "base_imposable": float(_q2(raw_fact.get("base_imposable") or 0)),
                "quota_iva": float(_q2(raw_fact.get("quota_iva") or 0)),
                "liquid_exigible": float(_q2(raw_fact.get("liquid_exigible") or 0)),
                "linies": [
                    {
                        "id": str(fl.get("id")),
                        "concepte": fl.get("concepte"),
                        "quantitat": float(_q3(fl.get("quantitat") or 0)),
                        "preu_venda_unitari": float(_q2(fl.get("preu_venda_unitari") or 0)),
                        "tipus_iva": float(_q2(fl.get("tipus_iva") or 0)),
                        "subtotal": float(_q2(fl.get("subtotal") or 0)),
                    }
                    for fl in (raw_fact.get("linies") or [])
                ],
            }

        # 11. Valoració comercial (tots 3 rols) vs. Costos i Marges interns (només BOSS / SECRETARIA)
        barema_empresa = await obtenir_barema_empresa(db, empresa_id)
        preu_hora_pvp = _q2(
            await resoldre_preu_hora_control_panel(
                db,
                empresa_id,
                ot,
                barema_cache=barema_empresa,
                barema_fetched=True,
            )
        )
        valor_ma_obra_previst_pvp = _q2(hores_previstes * preu_hora_pvp)
        valor_ma_obra_pvp = _q2(hores_reals * preu_hora_pvp)
        pvp_materials_ot = _q2(ot.pvp_materials_aplicat or 0)
        valor_materials_pvp = (
            valor_materials_pvp_calc if valor_materials_pvp_calc > 0 else pvp_materials_ot
        )
        import_pressupostat = _q2(ot.import_pressupostat_net or ot.import_pressupostat or 0)
        if import_pressupostat <= 0 and pressupost_info:
            import_pressupostat = _q2(pressupost_info["total"])

        total_previst_pvp = _q2(valor_ma_obra_previst_pvp + valor_materials_pvp)
        total_valorat_pvp = _q2(valor_ma_obra_pvp + valor_materials_pvp)
        base_ingressos = (
            _q2(factura_info["base_imposable"])
            if factura_info and Decimal(str(factura_info["base_imposable"] or 0)) > 0
            else (
                import_pressupostat
                if import_pressupostat > 0
                else (total_valorat_pvp if total_valorat_pvp > 0 else total_previst_pvp)
            )
        )

        # Costos reals interns
        if cost_materials_real_pmp <= 0 and Decimal(str(ot.cost_materials_pmp or 0)) > 0:
            cost_materials_real_pmp = _q2(ot.cost_materials_pmp)
        elif cost_materials_real_pmp <= 0 and Decimal(str(ot.cost_materials_picking_pmp or 0)) > 0:
            cost_materials_real_pmp = _q2(ot.cost_materials_picking_pmp)
        if cost_materials_previst_pmp <= 0 and cost_materials_real_pmp > 0:
            cost_materials_previst_pmp = cost_materials_real_pmp

        cost_ma_obra_previst = Decimal("0.00")
        if hores_previstes > 0:
            cost_ma_obra_previst = _q2(
                await calcular_cost_ma_obra_real(db, empresa_id, ot, [], float(hores_previstes))
            )

        cost_ma_obra_real = _q2(ot.cost_ma_obra_real or 0)
        if cost_ma_obra_real <= 0 and hores_reals > 0:
            cost_ma_obra_real = _q2(
                await calcular_cost_ma_obra_real(db, empresa_id, ot, trams, float(hores_reals))
            )
        cost_flota_real = _q2(ot.cost_flota_real or 0)

        cost_total_previst = _q2(
            cost_materials_previst_pmp + cost_ma_obra_previst + cost_flota_real
        )
        marge_previst_eur = _q2(base_ingressos - cost_total_previst)
        marge_previst_pct = (
            _q2((marge_previst_eur / base_ingressos) * Decimal("100"))
            if base_ingressos > 0
            else Decimal("0.00")
        )

        cost_total_real = _q2(
            cost_materials_real_pmp
            + cost_mermes_real_pmp
            + cost_ma_obra_real
            + cost_flota_real
            + total_tiquets_camp
        )
        marge_real_eur = _q2(base_ingressos - cost_total_real)
        marge_real_pct = (
            _q2((marge_real_eur / base_ingressos) * Decimal("100"))
            if base_ingressos > 0
            else Decimal("0.00")
        )
        bloqueig_marge_critic = bool(
            base_ingressos > 0 and float(marge_real_pct) < LLINDAR_MARGE_CRITIC_PCT
        )

        # 12. Auditoria post-obra existent (si n'hi ha)
        auditoria_obj = (
            await db.execute(
                select(AuditoriaPostObra).where(
                    AuditoriaPostObra.empresa_id == empresa_id,
                    AuditoriaPostObra.ordre_treball_id == ot.id,
                )
            )
        ).scalars().first()

        # 13. Disclaimer i comprovació de preparació per pre-facturar
        disclaimer = calcular_estat_disclaimer_ot(
            ot.estat,
            te_tram_obert=te_tram_obert,
            validada_per_id=ot.validada_per_id,
            factura_id=uuid.UUID(factura_info["id"]) if factura_info else ot.factura_id,
            factura_estat_document=(
                str(factura_info.get("estat_document") or "") if factura_info else None
            ),
        )

        motius_bloqueig: List[str] = []
        if not disclaimer["es_conclosa"]:
            motius_bloqueig.append("La feina no ha finalitzat a camp.")
        if te_tram_obert:
            motius_bloqueig.append("Hi ha un tram de temps actiu pendent de tancar.")
        if disclaimer["es_conclosa"] and not disclaimer["es_facturada"] and disclaimer["codi"] == "CONCLOSA_PENDENT_VALIDACIO":
            motius_bloqueig.append("Cal completar i validar la conciliació tècnica de la Fulla 360°.")

        resum_comercial: Dict[str, Any] = {
            "import_pressupostat": float(import_pressupostat),
            "hores_previstes": float(hores_previstes),
            "hores_reals": float(hores_reals),
            "desviacio_hores": float(desviacio_hores),
            "km_imputats": int(ot.km_imputats or 0),
            "preu_venda_hora_aplicat": float(preu_hora_pvp),
            "valor_ma_obra_previst_pvp": float(valor_ma_obra_previst_pvp),
            "valor_ma_obra_pvp": float(valor_ma_obra_pvp),
            "valor_materials_pvp": float(valor_materials_pvp),
            "total_tiquets_camp": float(total_tiquets_camp),
            "total_previst_pvp": float(total_previst_pvp),
            "total_valorat_pvp": float(total_valorat_pvp),
        }

        resum_intern: Dict[str, Any] = {
            "cost_materials_previst_pmp": float(cost_materials_previst_pmp)
            if mostrar_costos_interns
            else None,
            "cost_materials_pmp": float(cost_materials_real_pmp)
            if mostrar_costos_interns
            else None,
            "cost_mermes_pmp": float(cost_mermes_real_pmp) if mostrar_costos_interns else None,
            "cost_ma_obra_previst": float(cost_ma_obra_previst) if mostrar_costos_interns else None,
            "cost_ma_obra_real": float(cost_ma_obra_real) if mostrar_costos_interns else None,
            "cost_flota_real": float(cost_flota_real) if mostrar_costos_interns else None,
            "cost_tiquets_camp": float(total_tiquets_camp) if mostrar_costos_interns else None,
            "cost_total_previst": float(cost_total_previst) if mostrar_costos_interns else None,
            "cost_total_real": float(cost_total_real) if mostrar_costos_interns else None,
            "marge_previst_eur": float(marge_previst_eur) if mostrar_costos_interns else None,
            "marge_previst_percentatge": float(marge_previst_pct) if mostrar_costos_interns else None,
            "marge_real_eur": float(marge_real_eur) if mostrar_costos_interns else None,
            "marge_real_percentatge": float(marge_real_pct) if mostrar_costos_interns else None,
            "bloqueig_marge_critic": bloqueig_marge_critic if mostrar_costos_interns else None,
        }

        return {
            "ordre_treball_id": str(ot.id),
            "codi": ot.codi,
            "titol": ot.titol,
            "estat": ot.estat,
            "versio": ot.versio,
            "client_id": str(ot.client_id),
            "client_nom": client_obj.rao_social if client_obj else None,
            "vehicle": vehicle_info,
            "operaris_assignats": operaris_list,
            "planol": planol_info,
            "disclaimer": disclaimer,
            "validacio": {
                "validada": bool(ot.validada_per_id is not None or str(ot.estat or "").upper() == "VALIDADA_PER_FACTURAR"),
                "validada_per_id": str(ot.validada_per_id) if ot.validada_per_id else None,
                "validada_per_nom": validador_nom,
                "data_validacio": ot.data_validacio.isoformat() if ot.data_validacio else None,
                "notes_validacio_tecnica": ot.notes_validacio_tecnica,
                "checklist_conciliacio": dict(ot.checklist_conciliacio or {}),
            },
            "temps_i_gps": {
                "te_tram_obert": te_tram_obert,
                "temps_acumulat_segons": temps_segons,
                "hores_previstes": float(hores_previstes),
                "hores_previstes_human": hores_previstes_human,
                "hores_reals": float(hores_reals),
                "hores_reals_human": hores_reals_human,
                "desviacio_hores": float(desviacio_hores),
                "hora_inici_real": ot.hora_inici_real.isoformat() if ot.hora_inici_real else None,
                "hora_fi_real": ot.hora_fi_real.isoformat() if ot.hora_fi_real else None,
                "desviacio_geovalla": bool(ot.desviacio_geovalla or bool(desviacions_gps)),
                "justificacio_geovalla": ot.justificacio_geovalla,
                "te_foto_geovalla": bool(ot.foto_evidencia_desviacio),
                "desviacions_gps": desviacions_gps,
                "trams_count": len(trams),
            },
            "fotos_qa": {
                "inicial": fotos_qa["inicial"],
                "intermedia": fotos_qa["intermedia"],
                "final": fotos_qa["final"],
                "total_pujades": sum(1 for v in fotos_qa.values() if v),
                "protocol_complet": protocol_fotos_complet,
            },
            "signatura": {
                "present": bool(ot.signatura_client_path),
                "path": ot.signatura_client_path,
                "nom_receptor": ot.nom_receptor,
                "dni_receptor": ot.dni_receptor,
                "observacions_tancament": ot.observacions_tancament,
                "data_signatura": ot.data_signatura.isoformat() if ot.data_signatura else None,
            },
            "materials": {
                "estat_picking": estat_picking_global,
                "total_linies": len(materials_list),
                "alerta_consum_excessiu": alerta_consum_excessiu,
                "detall_merma": " ".join(detall_merma_msgs) if detall_merma_msgs else None,
                "linies": materials_list,
                "linies_pendents_facturar": linies_pendents_facturar,
            },
            "eines": eines_list,
            "incidencies": {
                "total": len(incidencies_list),
                "obertes": incidencies_obertes_count,
                "items": incidencies_list,
            },
            "tiquets": {
                "total": len(tiquets_list),
                "import_total": float(total_tiquets_camp),
                "items": tiquets_list,
            },
            "capes_gis": capes_gis_list,
            "pressupost": pressupost_info,
            "factura": factura_info,
            "resum_comercial": resum_comercial,
            "resum_intern": resum_intern,
            "auditoria_post_obra": {
                "id": str(auditoria_obj.id),
                "estat": auditoria_obj.estat,
                "alerta_merma_operativa": auditoria_obj.alerta_merma_operativa,
                "bloqueig_consum_excessiu": auditoria_obj.bloqueig_consum_excessiu,
                "bloqueig_sync_pendent": auditoria_obj.bloqueig_sync_pendent,
                "data_aprovacio": auditoria_obj.data_aprovacio.isoformat()
                if auditoria_obj.data_aprovacio
                else None,
            }
            if auditoria_obj
            else None,
            "preparada_per_prefacturar": bool(disclaimer["pot_prefacturar"] and not motius_bloqueig),
            "motius_bloqueig_prefacturacio": motius_bloqueig,
        }

    @classmethod
    async def executar_auditoria_post_obra(
        cls,
        db: AsyncSession,
        empresa_id: uuid.UUID,
        ordre_treball_id: uuid.UUID,
        rol_usuari: Optional[str] = "BOSS",
        *,
        materials_override: Optional[List[Dict[str, Any]]] = None,
        hores_reals_override: Optional[float] = None,
        hores_previstes_override: Optional[float] = None,
        km_reals_override: Optional[float] = None,
        despeses_camp_override: Optional[float] = None,
        sync_pendent: bool = False,
        incidencies_registrades_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Executa i persisteix l'AuditoriaPostObra amb càlculs 100% reals (Zero Mock Data)."""
        mostrar_costos_interns = _es_rol_costos_interns(rol_usuari)

        # Carregar dades reals completes amb context intern (filtrarem la sortida segons rol_usuari)
        conc = await cls.obtenir_conciliacio_completa(
            db=db,
            empresa_id=empresa_id,
            ordre_treball_id=ordre_treball_id,
            rol_usuari="BOSS" if mostrar_costos_interns else rol_usuari,
        )

        # Upsert helper (auditories_post_obra té RLS restrictive economics_boss_only: només BOSS/SUPERADMIN hi escriuen)
        pot_persistir_auditoria = str(rol_usuari or "").upper() in {"BOSS", "SUPERADMIN"}
        auditoria: Optional[AuditoriaPostObra] = None
        if pot_persistir_auditoria:
            auditoria = (
                await db.execute(
                    select(AuditoriaPostObra).where(
                        AuditoriaPostObra.empresa_id == empresa_id,
                        AuditoriaPostObra.ordre_treball_id == ordre_treball_id,
                    )
                )
            ).scalars().first()

        if sync_pendent:
            auditoria_id_sync: Optional[str] = None
            if pot_persistir_auditoria:
                if not auditoria:
                    auditoria = AuditoriaPostObra(
                        empresa_id=empresa_id,
                        ordre_treball_id=ordre_treball_id,
                        desviacio_hores=0.0,
                        desviacio_materials=[],
                        desviacio_km=0.0,
                        despeses_camp=0.0,
                        marge_previst_percentatge=0.0,
                        marge_real_liquidat_percentatge=0.0,
                        bloqueig_sync_pendent=True,
                        estat="PENDENT_CONFIRMACIO",
                        detall_merma="Sincronització de fotos de camp pendent des de zona blanca.",
                    )
                    db.add(auditoria)
                else:
                    auditoria.bloqueig_sync_pendent = True
                    auditoria.estat = "PENDENT_CONFIRMACIO"
                    auditoria.detall_merma = "Sincronització de fotos de camp pendent des de zona blanca."
                await db.commit()
                auditoria_id_sync = str(auditoria.id)
            return {
                "auditoria_id": auditoria_id_sync,
                "estat_conciliacio": "Pendent de Campo",
                "bloqueig_facturacio": True,
                "missatge": (
                    "Sincronització de camp offline pendent; la línia de Triple Conciliació roman "
                    "en estat 'Pendent de Campo' fins al sincronitzat complet a nau."
                ),
            }

        resum_com = conc["resum_comercial"]
        resum_int = conc["resum_intern"]
        incidencies_reals = int(conc["incidencies"]["total"])
        incidencies_total = (
            incidencies_registrades_override
            if incidencies_registrades_override is not None and incidencies_registrades_override > 0
            else incidencies_reals
        )

        hores_prev = (
            Decimal(str(hores_previstes_override))
            if hores_previstes_override is not None and hores_previstes_override > 0
            else Decimal(str(resum_com["hores_previstes"] or 0))
        )
        hores_real = (
            Decimal(str(hores_reals_override))
            if hores_reals_override is not None and hores_reals_override > 0
            else Decimal(str(resum_com["hores_reals"] or 0))
        )
        desviacio_hores = _q2(hores_real - hores_prev)
        km_reals = (
            _q2(km_reals_override)
            if km_reals_override is not None and km_reals_override > 0
            else _q2(resum_com["km_imputats"] or 0)
        )
        despeses_camp = (
            _q2(despeses_camp_override)
            if despeses_camp_override is not None and despeses_camp_override > 0
            else _q2(resum_com["total_tiquets_camp"] or 0)
        )

        # Desviacions de materials (prioritza picking real de BD; si s'envien overrides explícits i no hi ha picking, els avalua sense preus inventats)
        bloqueig_merma = False
        detall_merma_parts: List[str] = []
        desviacions_materials_llista: List[Dict[str, Any]] = []
        desviacio_materials_import = Decimal("0.00")

        mat_linies_bd = conc["materials"]["linies"]
        if mat_linies_bd:
            for ml in mat_linies_bd:
                prev_q = Decimal(str(ml["quantitat_prevista"]))
                real_net_q = Decimal(str(ml["consum_real"]))
                desv_q = _q3(real_net_q - prev_q)
                pvp_u = Decimal(str(ml["preu_venda_unitari"] or 0))
                desviacio_materials_import += _q2(desv_q * pvp_u)
                desviacions_materials_llista.append(
                    {
                        "article_id": ml["article_id"],
                        "nom": ml["article_nom"],
                        "previst": float(prev_q),
                        "real_net": float(real_net_q),
                        "desviacio": float(desv_q),
                    }
                )
                if prev_q > 0:
                    ratio_consum = float((real_net_q / prev_q) * Decimal("100"))
                    if ratio_consum >= LLINDAR_MERMA_CONTINUA_PCT and incidencies_total == 0:
                        bloqueig_merma = True
                        detall_merma_parts.append(
                            f"Consum de {ml['article_nom']} excedit en +{float(desv_q):.1f} "
                            f"({ratio_consum:.0f}%, >250%) sense cap incidència de camp reportada."
                        )
        elif materials_override:
            for mat in materials_override:
                nom_mat = str(mat.get("nom") or mat.get("article") or "Material")
                prev_q = _q3(mat.get("previst", 0.0))
                real_q = _q3(mat.get("real", mat.get("quantitat_real", 0.0)))
                ret_q = _q3(mat.get("retornat", 0.0))
                real_net_q = max(Decimal("0.000"), _q3(real_q - ret_q))
                desv_q = _q3(real_net_q - prev_q)
                desviacions_materials_llista.append(
                    {
                        "nom": nom_mat,
                        "previst": float(prev_q),
                        "real_net": float(real_net_q),
                        "desviacio": float(desv_q),
                    }
                )
                if prev_q > 0:
                    ratio_consum = float((real_net_q / prev_q) * Decimal("100"))
                    if ratio_consum >= LLINDAR_MERMA_CONTINUA_PCT and incidencies_total == 0:
                        bloqueig_merma = True
                        detall_merma_parts.append(
                            f"Consum de {nom_mat} excedit en +{float(desv_q):.1f} "
                            f"({ratio_consum:.0f}%, >250%) sense cap incidència de camp reportada."
                        )

        preu_hora_pvp = _q2(resum_com["preu_venda_hora_aplicat"] or 0)
        partides_inicials = _q2(resum_com["import_pressupostat"] or 0)
        desviacio_ma_obra_import = _q2(desviacio_hores * preu_hora_pvp)
        total_proposat_corregit = _q2(
            partides_inicials + desviacio_materials_import + desviacio_ma_obra_import + despeses_camp
        )

        # Càlcul 100% real de marges (sense cap constant hardcodejada)
        cost_previst_total = _q2(resum_int["cost_materials_previst_pmp"] or 0)
        marge_previst_pct = (
            _q2(((partides_inicials - cost_previst_total) / partides_inicials) * Decimal("100"))
            if partides_inicials > 0
            else Decimal("0.00")
        )
        cost_real_total = _q2(
            Decimal(str(resum_int["cost_materials_pmp"] or 0))
            + Decimal(str(resum_int["cost_mermes_pmp"] or 0))
            + Decimal(str(resum_int["cost_ma_obra_real"] or 0))
            + Decimal(str(resum_int["cost_flota_real"] or 0))
            + despeses_camp
        )
        base_marge = partides_inicials if partides_inicials > 0 else total_proposat_corregit
        marge_real_pct = (
            _q2(((base_marge - cost_real_total) / base_marge) * Decimal("100"))
            if base_marge > 0
            else Decimal("0.00")
        )
        caiguda_marge = marge_previst_pct - marge_real_pct
        alerta_merma = bool(
            bloqueig_merma
            or (base_marge > 0 and float(marge_real_pct) < LLINDAR_MARGE_CRITIC_PCT)
            or (partides_inicials > 0 and caiguda_marge >= Decimal("5.00"))
        )
        detall_merma = " ".join(detall_merma_parts) if detall_merma_parts else None

        pressupost_corregit = {
            "partides_inicials": float(partides_inicials),
            "desviacio_materials_import": float(_q2(desviacio_materials_import)),
            "desviacio_ma_obra_import": float(desviacio_ma_obra_import),
            "despeses_camp_import": float(despeses_camp),
            "total_proposat_corregit": float(total_proposat_corregit),
            "data_proposta": datetime.now(timezone.utc).isoformat(),
            "estat_proposta": "PENDENT_CONFIRMACIO_ENGINYER",
        }

        auditoria_id_str: Optional[str] = None
        estat_auditoria = "PENDENT_CONFIRMACIO"

        if pot_persistir_auditoria:
            if not auditoria:
                auditoria = AuditoriaPostObra(
                    empresa_id=empresa_id,
                    ordre_treball_id=ordre_treball_id,
                    desviacio_hores=float(desviacio_hores),
                    desviacio_materials=desviacions_materials_llista,
                    desviacio_km=float(km_reals),
                    despeses_camp=float(despeses_camp),
                    marge_previst_percentatge=float(marge_previst_pct),
                    marge_real_liquidat_percentatge=float(marge_real_pct),
                    alerta_merma_operativa=alerta_merma,
                    detall_merma=detall_merma,
                    bloqueig_consum_excessiu=bloqueig_merma,
                    bloqueig_sync_pendent=False,
                    pressupost_corregit_proposta=pressupost_corregit,
                    estat="PENDENT_CONFIRMACIO",
                )
                db.add(auditoria)
            else:
                auditoria.desviacio_hores = float(desviacio_hores)
                auditoria.desviacio_materials = desviacions_materials_llista
                auditoria.desviacio_km = float(km_reals)
                auditoria.despeses_camp = float(despeses_camp)
                auditoria.marge_previst_percentatge = float(marge_previst_pct)
                auditoria.marge_real_liquidat_percentatge = float(marge_real_pct)
                auditoria.alerta_merma_operativa = alerta_merma
                auditoria.detall_merma = detall_merma
                auditoria.bloqueig_consum_excessiu = bloqueig_merma
                auditoria.bloqueig_sync_pendent = False
                auditoria.pressupost_corregit_proposta = pressupost_corregit

            await db.commit()
            auditoria_id_str = str(auditoria.id)
            estat_auditoria = auditoria.estat

            # Persistir al disc sobirà de l'empresa
            try:
                await SovereignStorageGateway.desar_entitat_json(
                    db=db,
                    empresa_id=empresa_id,
                    categoria="copilot_mermes_preus",
                    item_id=auditoria_id_str,
                    dades={
                        "id": auditoria_id_str,
                        "ordre_treball_id": str(auditoria.ordre_treball_id),
                        "desviacio_hores": float(auditoria.desviacio_hores),
                        "desviacio_materials": auditoria.desviacio_materials,
                        "marge_previst_percentatge": float(auditoria.marge_previst_percentatge),
                        "marge_real_liquidat_percentatge": float(
                            auditoria.marge_real_liquidat_percentatge
                        ),
                        "alerta_merma_operativa": auditoria.alerta_merma_operativa,
                        "detall_merma": auditoria.detall_merma,
                        "bloqueig_consum_excessiu": auditoria.bloqueig_consum_excessiu,
                        "pressupost_corregit_proposta": auditoria.pressupost_corregit_proposta,
                        "estat": auditoria.estat,
                    },
                )
            except Exception as exc:
                logger.warning("No s'ha pogut desar l'auditoria al disc del client: %s", exc)

        return {
            "auditoria_id": auditoria_id_str,
            "ordre_treball_id": str(ordre_treball_id),
            "desviacio_hores": float(desviacio_hores),
            "desviacio_materials": desviacions_materials_llista,
            "marge_previst_percentatge": float(marge_previst_pct)
            if mostrar_costos_interns
            else None,
            "marge_real_liquidat_percentatge": float(marge_real_pct)
            if mostrar_costos_interns
            else None,
            "alerta_merma_operativa": alerta_merma,
            "bloqueig_consum_excessiu": bloqueig_merma,
            "detall_merma": detall_merma,
            "pressupost_corregit_proposta": pressupost_corregit,
            "estat": estat_auditoria,
            "missatge": (
                "Auditoria post-obra realitzada amb dades reals de BD. "
                "Proposta pendent de confirmació humana (HITL)."
            ),
        }
