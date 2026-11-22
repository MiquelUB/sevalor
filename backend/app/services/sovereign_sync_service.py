"""Servei de Reconciliació i Auto-Reparació Sobirana (PostgreSQL -> Disc Dur Dedicat via WSS).

Garanteix que totes les entitats operatives d'una empresa (vehicles, operaris, clients,
finques, contractes, proveïdors, articles amb estoc real, eines, albarans, factures,
picking, pressupostos, OTs actives/històriques, informes post-obra, mermes, incidències,
jornades, tiquets de despesa/combustible, memoràndums i FAQs) estiguin sempre sincronitzades
en format JSON signat amb HMAC al disc dur dedicat de l'empresa.

Principis Zero-Storage i Seguretat:
- Mai retorna registres directament des de SQL cap als subagents del Copilot: escriu al
  disc dur de l'empresa via `SovereignStorageGateway.desar_entitat_json` (signat HMAC) i
  els subagents sempre llegeixen exclusivament del disc sobirà verificat.
- Aïllament multi-tenant estricte: activa `SET LOCAL app.current_empresa_id` (RLS) i filtra
  explícitament per `empresa_id == emp_uuid` a cada consulta.
- Privadesa estricta: mai exporta `password_hash`, `pin_hash`, `secret_2fa`, `ip_allowlist`
  ni `iban_xifrat_simetric` als fitxers JSON del disc.
- Només executa backfills/read-repair quan el túnel WSS del PC de l'empresa està online
  (o `LOCAL_FS` explícit), per no saturar la cua efímera `OFFLINE_TRANSIT` de `/tmp`.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import set_tenant_context
from app.models.models import (
    AlbaraProveidor,
    Article,
    AuditoriaPostObra,
    Client,
    ContracteMantenimentMRR,
    DocumentFlota,
    EinaCustodia,
    EstocMagatzem,
    FacturaCapcalera,
    FacturaLinia,
    FacturaProveidor,
    FaqCorporativaRag,
    Finca,
    FullaPicking,
    Incidencia,
    LiniaPicking,
    Magatzem,
    MantenimentVehicle,
    MemorandumTecnicCopilot,
    MermaInventari,
    MovimentEstoc,
    OrdreTreball,
    Pressupost,
    Proveidor,
    RegistreJornadaLaboral,
    TiquetCarburant,
    TiquetCombustible,
    TiquetDespesa,
    Usuari,
    Vehicle,
)
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.vault_tunnel import empresa_target_key, vault_tunnel_broker

logger = logging.getLogger("sevalor.sovereign_sync")

# Categories operatives sincronitzables des de PostgreSQL cap al disc sobirà
CATEGORIES_SINCRONITZABLES: Tuple[str, ...] = (
    "clients",
    "finques",
    "contractes",
    "proveidors",
    "magatzem_articles",
    "magatzem_eines",
    "albarans",
    "factures_proveidors",
    "picking",
    "pressupostos",
    "factures_pdf",
    "ots_actives",
    "ots_historic",
    "ots_informes",
    "copilot_mermes_preus",
    "incidencies_registres",
    "vehicles",
    "alertes_flota",
    "operaris",
    "jornades",
    "tiquets_despesa",
    "copilot_memorandums",
    "protocols_interns",
)

# Cooldown de read-repair per (empresa_id, categoria) en segons per evitar bucles repetits
_READ_REPAIR_COOLDOWN_S: float = 30.0
_READ_REPAIR_LAST_TS: Dict[Tuple[str, str], float] = {}
_READ_REPAIR_LOCKS: Dict[Tuple[str, str], asyncio.Lock] = {}


def reset_read_repair_state() -> None:
    """Reinicia el cooldown de read-repair (útil en tests o després d'una sincronització manual)."""
    _READ_REPAIR_LAST_TS.clear()


def _iso(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return str(val)


def _num(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None:
        return default
    if isinstance(val, (int, float, Decimal)):
        return float(val)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def serialize_usuari_safe(u: Usuari) -> Dict[str, Any]:
    """Serialitza un `Usuari` sense exposar cap credencial ni dada sensible d'autenticació."""
    return {
        "id": str(u.id),
        "empresa_id": str(u.empresa_id),
        "nif": u.nif,
        "nom": u.nom,
        "cognoms": u.cognoms or "",
        "email": u.email,
        "telefon": u.telefon,
        "rol": u.rol,
        "estat": u.estat,
        "especialitat": u.especialitat,
        "estat_operatiu": u.estat_operatiu or "DISPONIBLE",
        "cost_hora_eur": _num(u.cost_hora_eur, 0.0),
        "vehicle_assignat_id": str(u.vehicle_assignat_id) if u.vehicle_assignat_id else None,
        "carnet_conduir": u.carnet_conduir or "B",
        "carnet_caducitat": _iso(u.carnet_caducitat),
        "prl_certificat_vigencia": _iso(u.prl_certificat_vigencia),
        "created_at": _iso(u.created_at),
    }


def serialize_vehicle(
    v: Vehicle,
    *,
    conductor_nom: Optional[str] = None,
    documents: Optional[List[Dict[str, Any]]] = None,
    manteniments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Serialitza un `Vehicle` amb tots els camps requerits pels subagents de flota i planificació."""
    return {
        "id": str(v.id),
        "empresa_id": str(v.empresa_id),
        "matricula": v.matricula,
        "marca": v.marca,
        "model": v.model,
        "tipus": v.tipus or "DIESEL",
        "distintiu_ambiental": v.distintiu_ambiental,
        "estat": v.estat,
        "odometre_acumulat": int(v.odometre_acumulat or 0),
        "horometre_acumulat": _num(v.horometre_acumulat, 0.0),
        "odometre_inici_contracte": int(v.odometre_inici_contracte or 0),
        "conductor_habitual_id": str(v.conductor_habitual_id) if v.conductor_habitual_id else None,
        "conductor": conductor_nom,
        "magatzem_id": str(v.magatzem_id) if v.magatzem_id else None,
        "data_proxima_itv": _iso(v.data_proxima_itv),
        "estat_itv": v.estat_itv,
        "data_caducitat_asseguranca": _iso(v.data_caducitat_asseguranca),
        "companyia_asseguradora": v.companyia_asseguradora,
        "polissa_asseguranca": v.polissa_asseguranca,
        "carnet_necessari": v.carnet_necessari or "B",
        "historial_reparacions": v.historial_reparacions,
        "regim_adquisicio": v.regim_adquisicio or "PROPIETAT",
        "renting_limit_km": v.renting_limit_km,
        "data_inici_contracte": _iso(v.data_inici_contracte),
        "data_fi_contracte": _iso(v.data_fi_contracte),
        "data_venciment_renting": _iso(v.data_venciment_renting),
        "quota_mensual_eur": _num(v.quota_mensual_eur, 0.0),
        "tarifa_diaria_eur": _num(v.tarifa_diaria_eur, 0.0),
        "preu_km_exces_eur": _num(v.preu_km_exces_eur, 0.0),
        "valor_residual_eur": _num(v.valor_residual_eur),
        "fianca_eur": _num(v.fianca_eur),
        "empresa_renting": v.empresa_renting,
        "num_contracte_renting": v.num_contracte_renting,
        "categoria_ue": v.categoria_ue,
        "mma_kg": v.mma_kg,
        "tara_kg": v.tara_kg,
        "carrega_util_kg": v.carrega_util_kg,
        "mmr_amb_fre_kg": v.mmr_amb_fre_kg,
        "requereix_cap": bool(v.requereix_cap),
        "equipament_homologat": list(v.equipament_homologat or []),
        "certificats_prl_requerits": list(v.certificats_prl_requerits or []),
        "dades_pesants": v.dades_pesants if isinstance(v.dades_pesants, dict) else None,
        "estat_semafor": v.estat_semafor,
        "apte_assignacio_pwa": bool(v.apte_assignacio_pwa) if v.apte_assignacio_pwa is not None else True,
        "consum_l_100km": _num(v.consum_l_100km),
        "consum_mitjana_historica": _num(v.consum_mitjana_historica),
        "consum_adblue_litres": _num(v.consum_adblue_litres),
        "places": v.places,
        "documents": documents or [],
        "manteniments": manteniments or [],
        "created_at": _iso(v.created_at),
    }


def serialize_finca(f: Finca, *, client_nom: Optional[str] = None) -> Dict[str, Any]:
    """Serialitza una `Finca` per a la carpeta `01_clients/finques_i_instal_lacions`."""
    return {
        "id": str(f.id),
        "empresa_id": str(f.empresa_id),
        "client_id": str(f.client_id) if f.client_id else None,
        "client_nom": client_nom,
        "nom": f.nom,
        "adreca": f.adreca,
        "latitud": _num(f.latitud),
        "longitud": _num(f.longitud),
        "ref_cadastral": f.ref_cadastral,
        "poligon_sigpac": f.poligon_sigpac,
        "parcel_sigpac": f.parcel_sigpac,
        "superficie_ha": _num(f.superficie_ha),
        "actiu": bool(f.actiu) if f.actiu is not None else True,
        "created_at": _iso(f.created_at),
    }


# ---------------------------------------------------------------------------
# Recol·lectors per categoria (retornen llista de `(item_id, payload)`)
# ---------------------------------------------------------------------------


async def _collect_clients(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    rows = (await db.execute(select(Client).where(Client.empresa_id == emp_id))).scalars().all()
    items: List[Tuple[str, Dict[str, Any]]] = []
    for c in rows:
        items.append(
            (
                str(c.id),
                {
                    "id": str(c.id),
                    "empresa_id": str(emp_id),
                    "codi": c.codi,
                    "rao_social": c.rao_social,
                    "nif": c.nif,
                    "telefon": c.telefon,
                    "email": c.email,
                    "adreca_fiscal": c.adreca_fiscal,
                    "estat_canal_telegram": c.estat_canal_telegram,
                    "telegram_chat_id": c.telegram_chat_id,
                    "limit_risc_credit": _num(c.limit_risc_credit),
                    "estat_risc_operatiu": c.estat_risc_operatiu,
                    "actiu": bool(c.actiu) if c.actiu is not None else True,
                    "created_at": _iso(c.created_at),
                },
            )
        )
    return items


async def _collect_finques(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    clients = (await db.execute(select(Client.id, Client.rao_social).where(Client.empresa_id == emp_id))).all()
    cli_map = {str(cid): nom for cid, nom in clients}
    rows = (await db.execute(select(Finca).where(Finca.empresa_id == emp_id))).scalars().all()
    return [
        (str(f.id), serialize_finca(f, client_nom=cli_map.get(str(f.client_id))))
        for f in rows
    ]


async def _collect_contractes(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    clients = (await db.execute(select(Client.id, Client.rao_social).where(Client.empresa_id == emp_id))).all()
    cli_map = {str(cid): nom for cid, nom in clients}
    rows = (
        await db.execute(
            select(ContracteMantenimentMRR).where(ContracteMantenimentMRR.empresa_id == emp_id)
        )
    ).scalars().all()
    items: List[Tuple[str, Dict[str, Any]]] = []
    for c in rows:
        items.append(
            (
                str(c.id),
                {
                    "id": str(c.id),
                    "empresa_id": str(emp_id),
                    "client_id": str(c.client_id) if c.client_id else None,
                    "client_nom": cli_map.get(str(c.client_id)),
                    "codi_contracte": c.codi_contracte,
                    "quota_mensual_mrr": _num(c.quota_mensual_mrr, 0.0),
                    "data_inici": _iso(c.data_inici),
                    "data_fi": _iso(c.data_fi),
                    "actiu": bool(c.actiu) if c.actiu is not None else True,
                    "created_at": _iso(c.created_at),
                },
            )
        )
    return items


async def _collect_proveidors(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    rows = (await db.execute(select(Proveidor).where(Proveidor.empresa_id == emp_id))).scalars().all()
    return [
        (
            str(p.id),
            {
                "id": str(p.id),
                "empresa_id": str(emp_id),
                "codi": p.codi,
                "rao_social": p.rao_social,
                "nif": p.nif,
                "telefon": p.telefon,
                "email": p.email,
                "especialitat": p.especialitat,
                "es_recc": bool(p.es_recc),
                "aplica_isp_defecte": bool(p.aplica_isp_defecte),
                "actiu": bool(p.actiu) if p.actiu is not None else True,
                "created_at": _iso(p.created_at),
            },
        )
        for p in rows
    ]


async def _collect_magatzem_articles(
    db: AsyncSession, emp_id: uuid.UUID
) -> List[Tuple[str, Dict[str, Any]]]:
    articles = (await db.execute(select(Article).where(Article.empresa_id == emp_id))).scalars().all()
    magatzems = (await db.execute(select(Magatzem).where(Magatzem.empresa_id == emp_id))).scalars().all()
    estocs = (await db.execute(select(EstocMagatzem).where(EstocMagatzem.empresa_id == emp_id))).scalars().all()
    moviments = (
        await db.execute(
            select(MovimentEstoc)
            .where(MovimentEstoc.empresa_id == emp_id)
            .order_by(MovimentEstoc.created_at.desc())
            .limit(200)
        )
    ).scalars().all()

    mag_map = {str(m.id): m for m in magatzems}
    estocs_per_art: Dict[str, List[Dict[str, Any]]] = {}
    for e in estocs:
        aid = str(e.article_id)
        m = mag_map.get(str(e.magatzem_id))
        estocs_per_art.setdefault(aid, []).append(
            {
                "magatzem_id": str(e.magatzem_id),
                "magatzem_nom": m.nom if m else "Magatzem",
                "magatzem_tipus": m.tipus if m else "CENTRAL",
                "quantitat_fisica": _num(e.quantitat_fisica, 0.0),
                "quantitat_virtual_reservada": _num(e.quantitat_virtual_reservada, 0.0),
                "quantitat_cuarentena": _num(e.quantitat_cuarentena, 0.0),
                "ubicacio_passadis": e.ubicacio_passadis,
            }
        )

    art_nom_map = {str(a.id): a.nom for a in articles}
    items: List[Tuple[str, Dict[str, Any]]] = []
    for a in articles:
        aid = str(a.id)
        art_estocs = estocs_per_art.get(aid, [])
        if art_estocs:
            fis = sum(float(x.get("quantitat_fisica") or 0.0) for x in art_estocs)
            res = sum(float(x.get("quantitat_virtual_reservada") or 0.0) for x in art_estocs)
            disp = fis - res
        else:
            fis = float(a.estoc_total_actual or 0.0)
            res = 0.0
            disp = fis

        items.append(
            (
                aid,
                {
                    "id": aid,
                    "empresa_id": str(emp_id),
                    "referencia_inventari": a.referencia_inventari,
                    "referencia": a.referencia_inventari,
                    "codi_barres": a.codi_barres,
                    "nom": a.nom,
                    "unitat_mesura": a.unitat_mesura or "UNITAT",
                    "familia": a.familia,
                    "estoc_minim": _num(a.estoc_minim, 0.0),
                    "estoc_optim": _num(a.estoc_optim, 0.0),
                    "quantitat_fisica": fis,
                    "quantitat_virtual_reservada": res,
                    "estoc_disponible": disp,
                    "estoc_real": disp,
                    "estocs": art_estocs,
                    "preu_cost": _num(a.preu_cost, 0.0),
                    "pmp_actual": _num(a.pmp_actual, 0.0),
                    "preu_venda": _num(a.preu_venda, 0.0),
                    "proveidor_id": str(a.proveidor_id) if a.proveidor_id else None,
                    "actiu": bool(a.actiu) if a.actiu is not None else True,
                    "created_at": _iso(a.created_at),
                },
            )
        )

    for mov in moviments:
        items.append(
            (
                f"mov_{mov.id}",
                {
                    "id": str(mov.id),
                    "empresa_id": str(emp_id),
                    "tipus_registre": "MOVIMENT_ESTOC",
                    "article_id": str(mov.article_id),
                    "article_nom": art_nom_map.get(str(mov.article_id), "Article"),
                    "magatzem_id": str(mov.magatzem_id) if mov.magatzem_id else None,
                    "tipus_moviment": mov.tipus_moviment,
                    "quantitat": _num(mov.quantitat, 0.0),
                    "referencia_document": mov.referencia_document,
                    "notes": mov.notes,
                    "usuari_id": str(mov.usuari_id) if mov.usuari_id else None,
                    "created_at": _iso(mov.created_at),
                },
            )
        )

    return items


async def _collect_magatzem_eines(
    db: AsyncSession, emp_id: uuid.UUID
) -> List[Tuple[str, Dict[str, Any]]]:
    eines = (await db.execute(select(EinaCustodia).where(EinaCustodia.empresa_id == emp_id))).scalars().all()
    magatzems = (await db.execute(select(Magatzem).where(Magatzem.empresa_id == emp_id))).scalars().all()
    usuaris = (
        await db.execute(select(Usuari.id, Usuari.nom, Usuari.cognoms).where(Usuari.empresa_id == emp_id))
    ).all()
    mag_map = {str(m.id): m for m in magatzems}
    op_map = {str(uid): f"{nom or ''} {cog or ''}".strip() for uid, nom, cog in usuaris}

    items: List[Tuple[str, Dict[str, Any]]] = []
    for e in eines:
        mag = mag_map.get(str(e.magatzem_id)) if e.magatzem_id else None
        custodi = op_map.get(str(e.custodiat_per_operari_id)) if e.custodiat_per_operari_id else None
        items.append(
            (
                str(e.id),
                {
                    "id": str(e.id),
                    "empresa_id": str(emp_id),
                    "referencia_fabricant": e.referencia_fabricant,
                    "nom": e.nom,
                    "model": e.model,
                    "numero_serie": e.numero_serie,
                    "estat": e.estat,
                    "custodiat_per_operari_id": (
                        str(e.custodiat_per_operari_id) if e.custodiat_per_operari_id else None
                    ),
                    "custodi": custodi,
                    "custodiat_per": custodi,
                    "ordre_treball_id": str(e.ordre_treball_id) if e.ordre_treball_id else None,
                    "magatzem_id": str(e.magatzem_id) if e.magatzem_id else None,
                    "magatzem_nom": mag.nom if mag else "Nau Central Base",
                    "magatzem_tipus": mag.tipus if mag else "CENTRAL",
                    "ubicacio": mag.nom if mag else "Nau Central Base",
                    "es_furgoneta": bool(mag and str(mag.tipus or "").upper() == "FURGONETA"),
                    "data_ultima_calibracio": _iso(e.data_ultima_calibracio),
                    "data_propera_calibracio": _iso(e.data_propera_calibracio),
                    "data_fi_garantia": _iso(e.data_fi_garantia),
                    "observacions": e.observacions,
                    "created_at": _iso(e.created_at),
                },
            )
        )
    return items


async def _collect_albarans(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    provs = (
        await db.execute(select(Proveidor.id, Proveidor.rao_social).where(Proveidor.empresa_id == emp_id))
    ).all()
    prov_map = {str(pid): nom for pid, nom in provs}
    rows = (
        await db.execute(select(AlbaraProveidor).where(AlbaraProveidor.empresa_id == emp_id))
    ).scalars().all()
    return [
        (
            str(a.id),
            {
                "id": str(a.id),
                "empresa_id": str(emp_id),
                "proveidor_id": str(a.proveidor_id) if a.proveidor_id else None,
                "proveidor_nom": prov_map.get(str(a.proveidor_id)),
                "numero_albara": a.numero_albara,
                "data_albara": _iso(a.data_albara),
                "estat": a.estat,
                "fitxer_path": a.fitxer_path,
                "created_at": _iso(a.created_at),
            },
        )
        for a in rows
    ]


async def _collect_factures_proveidors(
    db: AsyncSession, emp_id: uuid.UUID
) -> List[Tuple[str, Dict[str, Any]]]:
    provs = (
        await db.execute(select(Proveidor.id, Proveidor.rao_social).where(Proveidor.empresa_id == emp_id))
    ).all()
    prov_map = {str(pid): nom for pid, nom in provs}
    rows = (
        await db.execute(select(FacturaProveidor).where(FacturaProveidor.empresa_id == emp_id))
    ).scalars().all()
    return [
        (
            str(f.id),
            {
                "id": str(f.id),
                "empresa_id": str(emp_id),
                "proveidor_id": str(f.proveidor_id) if f.proveidor_id else None,
                "proveidor_nom": prov_map.get(str(f.proveidor_id)),
                "numero_factura": f.numero_factura,
                "data_factura": _iso(f.data_factura),
                "base_imposable": _num(f.base_imposable, 0.0),
                "quota_iva": _num(f.quota_iva, 0.0),
                "total": _num(f.total, 0.0),
                "albara_numero": f.albara_numero,
                "estat": f.estat,
                "estat_pagament": f.estat_pagament,
                "pagada": bool(f.pagada),
                "data_venciment": _iso(f.data_venciment),
                "created_at": _iso(f.created_at),
            },
        )
        for f in rows
    ]


async def _collect_picking(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    fulles = (await db.execute(select(FullaPicking).where(FullaPicking.empresa_id == emp_id))).scalars().all()
    linies = (await db.execute(select(LiniaPicking).where(LiniaPicking.empresa_id == emp_id))).scalars().all()
    ots = (await db.execute(select(OrdreTreball.id, OrdreTreball.codi).where(OrdreTreball.empresa_id == emp_id))).all()
    arts = (
        await db.execute(
            select(Article.id, Article.nom, Article.referencia_inventari, Article.preu_venda).where(
                Article.empresa_id == emp_id
            )
        )
    ).all()

    fulla_map = {str(fp.id): fp for fp in fulles}
    ot_map = {str(oid): codi for oid, codi in ots}
    art_map = {
        str(aid): {"nom": nom, "referencia": ref, "preu_venda": _num(pvp, 0.0)}
        for aid, nom, ref, pvp in arts
    }

    items: List[Tuple[str, Dict[str, Any]]] = []
    for lp in linies:
        fp = fulla_map.get(str(lp.picking_id))
        ot_id_str = str(fp.ordre_treball_id) if fp and fp.ordre_treball_id else None
        art_info = art_map.get(str(lp.article_id), {})
        items.append(
            (
                f"linia_{lp.id}",
                {
                    "id": str(lp.id),
                    "empresa_id": str(emp_id),
                    "picking_id": str(lp.picking_id),
                    "ordre_treball_id": ot_id_str,
                    "ordre_treball_codi": ot_map.get(ot_id_str) if ot_id_str else None,
                    "vehicle_id": str(fp.vehicle_id) if fp and fp.vehicle_id else None,
                    "estat_picking": fp.estat_picking if fp else None,
                    "article_id": str(lp.article_id),
                    "article_nom": art_info.get("nom"),
                    "referencia": art_info.get("referencia"),
                    "preu_venda_unitari": art_info.get("preu_venda"),
                    "magatzem_id": str(lp.magatzem_id) if lp.magatzem_id else None,
                    "quantitat_prevista": _num(lp.quantitat_prevista, 0.0),
                    "quantitat_carregada_pick_in": _num(lp.quantitat_carregada_pick_in, 0.0),
                    "quantitat_retornada_pick_out": _num(lp.quantitat_retornada_pick_out, 0.0),
                    "quantitat_mermada": _num(lp.quantitat_mermada, 0.0),
                    "created_at": _iso(lp.created_at),
                },
            )
        )
    return items


async def _collect_pressupostos(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    clients = (await db.execute(select(Client.id, Client.rao_social).where(Client.empresa_id == emp_id))).all()
    cli_map = {str(cid): nom for cid, nom in clients}
    rows = (await db.execute(select(Pressupost).where(Pressupost.empresa_id == emp_id))).scalars().all()
    return [
        (
            str(p.id),
            {
                "id": str(p.id),
                "empresa_id": str(emp_id),
                "client_id": str(p.client_id) if p.client_id else None,
                "client_nom": cli_map.get(str(p.client_id)),
                "numero": p.numero,
                "total": _num(p.total, 0.0),
                "estat": p.estat,
                "created_at": _iso(p.created_at),
            },
        )
        for p in rows
    ]


async def _collect_factures_pdf(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    caps = (
        await db.execute(select(FacturaCapcalera).where(FacturaCapcalera.empresa_id == emp_id))
    ).scalars().all()
    linies = (await db.execute(select(FacturaLinia).where(FacturaLinia.empresa_id == emp_id))).scalars().all()
    linies_map: Dict[str, List[Dict[str, Any]]] = {}
    for lin in linies:
        fid = str(lin.factura_id)
        linies_map.setdefault(fid, []).append(
            {
                "id": str(lin.id),
                "obra_id": str(lin.obra_id) if lin.obra_id else None,
                "ordre_treball_id": str(lin.obra_id) if lin.obra_id else None,
                "article_id": str(lin.article_id) if lin.article_id else None,
                "concepte": lin.concepte,
                "quantitat": _num(lin.quantitat, 0.0),
                "preu_venda_unitari": _num(lin.preu_venda_unitari, 0.0),
                "tipus_iva": _num(lin.tipus_iva, 21.0),
                "subtotal": _num(lin.subtotal, 0.0),
            }
        )

    items: List[Tuple[str, Dict[str, Any]]] = []
    for f in caps:
        fid = str(f.id)
        f_linies = linies_map.get(fid, [])
        first_obra = next((x["obra_id"] for x in f_linies if x.get("obra_id")), None)
        items.append(
            (
                fid,
                {
                    "id": fid,
                    "empresa_id": str(emp_id),
                    "numero_factura": f.numero_factura,
                    "serie": f.serie,
                    "client_id": str(f.client_id) if f.client_id else None,
                    "ordre_treball_id": first_obra,
                    "data_emissio": _iso(f.data_emissio),
                    "base_imposable": _num(f.base_imposable, 0.0),
                    "quota_iva": _num(f.quota_iva, 0.0),
                    "liquid_exigible": _num(f.liquid_exigible, 0.0),
                    "total": _num(f.liquid_exigible, 0.0),
                    "estat_cobrament": f.estat_cobrament,
                    "estat_document": f.estat_document,
                    "linies": f_linies,
                    "created_at": _iso(f.created_at),
                },
            )
        )
    return items


async def _collect_ots_by_closed(
    db: AsyncSession, emp_id: uuid.UUID, *, closed: bool
) -> List[Tuple[str, Dict[str, Any]]]:
    clients = (await db.execute(select(Client.id, Client.rao_social).where(Client.empresa_id == emp_id))).all()
    finques = (await db.execute(select(Finca.id, Finca.nom).where(Finca.empresa_id == emp_id))).all()
    usuaris = (
        await db.execute(select(Usuari.id, Usuari.nom, Usuari.cognoms).where(Usuari.empresa_id == emp_id))
    ).all()
    cli_map = {str(cid): nom for cid, nom in clients}
    fin_map = {str(fid): nom for fid, nom in finques}
    op_map = {str(uid): f"{nom or ''} {cog or ''}".strip() for uid, nom, cog in usuaris}

    stmt = select(OrdreTreball).where(OrdreTreball.empresa_id == emp_id)
    if closed:
        stmt = stmt.where(OrdreTreball.estat == "TANCADA")
    else:
        stmt = stmt.where(OrdreTreball.estat != "TANCADA")
    rows = (await db.execute(stmt)).scalars().all()

    items: List[Tuple[str, Dict[str, Any]]] = []
    for o in rows:
        items.append(
            (
                str(o.id),
                {
                    "id": str(o.id),
                    "empresa_id": str(emp_id),
                    "codi": o.codi,
                    "titol": o.titol,
                    "descripcio": o.descripcio,
                    "estat": o.estat,
                    "adreca": o.adreca,
                    "client_id": str(o.client_id) if o.client_id else None,
                    "client_nom": cli_map.get(str(o.client_id)),
                    "finca_id": str(o.finca_id) if o.finca_id else None,
                    "finca_nom": fin_map.get(str(o.finca_id)),
                    "cap_de_colla_id": str(o.cap_de_colla_id) if o.cap_de_colla_id else None,
                    "tecnic": op_map.get(str(o.cap_de_colla_id)),
                    "vehicle_id": str(o.vehicle_id) if o.vehicle_id else None,
                    "data_planificacio": _iso(o.data_planificacio),
                    "latitud": _num(o.latitud),
                    "longitud": _num(o.longitud),
                    "vertical": o.vertical,
                    "import_pressupostat": _num(o.import_pressupostat),
                    "hores_imputades_facturables": _num(o.hores_imputades_facturables),
                    "created_at": _iso(o.created_at),
                },
            )
        )
    return items


async def _collect_ots_actives(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    return await _collect_ots_by_closed(db, emp_id, closed=False)


async def _collect_ots_historic(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    return await _collect_ots_by_closed(db, emp_id, closed=True)


async def _collect_ots_informes(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    ots = (await db.execute(select(OrdreTreball.id, OrdreTreball.codi).where(OrdreTreball.empresa_id == emp_id))).all()
    ot_map = {str(oid): codi for oid, codi in ots}
    rows = (
        await db.execute(select(AuditoriaPostObra).where(AuditoriaPostObra.empresa_id == emp_id))
    ).scalars().all()
    return [
        (
            str(a.id),
            {
                "id": str(a.id),
                "empresa_id": str(emp_id),
                "ordre_treball_id": str(a.ordre_treball_id),
                "codi_ot": ot_map.get(str(a.ordre_treball_id)),
                "desviacio_hores": _num(a.desviacio_hores, 0.0),
                "desviacio_materials": a.desviacio_materials,
                "desviacio_km": _num(a.desviacio_km, 0.0),
                "despeses_camp": _num(a.despeses_camp, 0.0),
                "marge_previst_percentatge": _num(a.marge_previst_percentatge, 0.0),
                "marge_real_liquidat_percentatge": _num(a.marge_real_liquidat_percentatge, 0.0),
                "alerta_merma_operativa": bool(a.alerta_merma_operativa),
                "detall_merma": a.detall_merma,
                "estat": a.estat,
                "created_at": _iso(a.created_at),
            },
        )
        for a in rows
    ]


async def _collect_copilot_mermes_preus(
    db: AsyncSession, emp_id: uuid.UUID
) -> List[Tuple[str, Dict[str, Any]]]:
    arts = (await db.execute(select(Article.id, Article.nom).where(Article.empresa_id == emp_id))).all()
    ots = (await db.execute(select(OrdreTreball.id, OrdreTreball.codi).where(OrdreTreball.empresa_id == emp_id))).all()
    art_map = {str(aid): nom for aid, nom in arts}
    ot_map = {str(oid): codi for oid, codi in ots}
    rows = (await db.execute(select(MermaInventari).where(MermaInventari.empresa_id == emp_id))).scalars().all()
    return [
        (
            str(m.id),
            {
                "id": str(m.id),
                "empresa_id": str(emp_id),
                "article_id": str(m.article_id),
                "article_nom": art_map.get(str(m.article_id)),
                "ordre_treball_id": str(m.ordre_treball_id) if m.ordre_treball_id else None,
                "codi_ot": ot_map.get(str(m.ordre_treball_id)) if m.ordre_treball_id else None,
                "quantitat": _num(m.quantitat, 0.0),
                "pmp_aplicat": _num(m.pmp_aplicat, 0.0),
                "cost_total": _num(m.cost_total, 0.0),
                "motiu": m.motiu,
                "notes": m.notes,
                "alerta_merma_operativa": True,
                "created_at": _iso(m.created_at),
            },
        )
        for m in rows
    ]


async def _collect_incidencies(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    ots = (await db.execute(select(OrdreTreball.id, OrdreTreball.codi).where(OrdreTreball.empresa_id == emp_id))).all()
    usuaris = (
        await db.execute(select(Usuari.id, Usuari.nom, Usuari.cognoms).where(Usuari.empresa_id == emp_id))
    ).all()
    ot_map = {str(oid): codi for oid, codi in ots}
    op_map = {str(uid): f"{nom or ''} {cog or ''}".strip() for uid, nom, cog in usuaris}
    rows = (await db.execute(select(Incidencia).where(Incidencia.empresa_id == emp_id))).scalars().all()
    return [
        (
            str(inc.id),
            {
                "id": str(inc.id),
                "empresa_id": str(emp_id),
                "ordre_treball_id": str(inc.ordre_treball_id) if inc.ordre_treball_id else None,
                "ordre_treball_codi": ot_map.get(str(inc.ordre_treball_id)) if inc.ordre_treball_id else None,
                "vehicle_id": str(inc.vehicle_id) if inc.vehicle_id else None,
                "operari_id": str(inc.operari_id) if inc.operari_id else None,
                "operari_nom": op_map.get(str(inc.operari_id)) if inc.operari_id else None,
                "ambit": inc.ambit,
                "tipus": inc.tipus,
                "gravetat": inc.gravetat,
                "estat": inc.estat,
                "text_observacions": inc.text_observacions,
                "created_at": _iso(inc.created_at),
            },
        )
        for inc in rows
    ]


async def _collect_vehicles(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    usuaris = (
        await db.execute(select(Usuari.id, Usuari.nom, Usuari.cognoms).where(Usuari.empresa_id == emp_id))
    ).all()
    op_map = {str(uid): f"{nom or ''} {cog or ''}".strip() for uid, nom, cog in usuaris}

    docs = (await db.execute(select(DocumentFlota).where(DocumentFlota.empresa_id == emp_id))).scalars().all()
    docs_map: Dict[str, List[Dict[str, Any]]] = {}
    for d in docs:
        vid = str(d.vehicle_id)
        docs_map.setdefault(vid, []).append(
            {
                "id": str(d.id),
                "tipus_document": d.tipus_document,
                "nom_arxiu": d.nom_arxiu,
                "data_document": _iso(d.data_document),
            }
        )

    mants = (
        await db.execute(select(MantenimentVehicle).where(MantenimentVehicle.empresa_id == emp_id))
    ).scalars().all()
    mants_map: Dict[str, List[Dict[str, Any]]] = {}
    for m in mants:
        vid = str(m.vehicle_id)
        mants_map.setdefault(vid, []).append(
            {
                "id": str(m.id),
                "data_manteniment": _iso(m.data_manteniment),
                "tipus": m.tipus,
                "descripcio": m.descripcio,
                "taller": m.taller,
                "cost_euros": _num(m.cost_euros, 0.0),
            }
        )

    rows = (await db.execute(select(Vehicle).where(Vehicle.empresa_id == emp_id))).scalars().all()
    return [
        (
            str(v.id),
            serialize_vehicle(
                v,
                conductor_nom=op_map.get(str(v.conductor_habitual_id)) if v.conductor_habitual_id else None,
                documents=docs_map.get(str(v.id), []),
                manteniments=mants_map.get(str(v.id), []),
            ),
        )
        for v in rows
    ]


async def _collect_alertes_flota(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    docs = (await db.execute(select(DocumentFlota).where(DocumentFlota.empresa_id == emp_id))).scalars().all()
    return [
        (
            f"doc_{d.id}",
            {
                "id": str(d.id),
                "empresa_id": str(emp_id),
                "vehicle_id": str(d.vehicle_id),
                "tipus_document": d.tipus_document,
                "nom_arxiu": d.nom_arxiu,
                "ruta_arxiu": d.ruta_arxiu,
                "data_document": _iso(d.data_document),
            },
        )
        for d in docs
    ]


async def _collect_operaris(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    rows = (await db.execute(select(Usuari).where(Usuari.empresa_id == emp_id))).scalars().all()
    return [(f"operari_{u.id}", serialize_usuari_safe(u)) for u in rows]


async def _collect_jornades(db: AsyncSession, emp_id: uuid.UUID) -> List[Tuple[str, Dict[str, Any]]]:
    usuaris = (
        await db.execute(select(Usuari.id, Usuari.nom, Usuari.cognoms).where(Usuari.empresa_id == emp_id))
    ).all()
    op_map = {str(uid): f"{nom or ''} {cog or ''}".strip() for uid, nom, cog in usuaris}
    rows = (
        await db.execute(
            select(RegistreJornadaLaboral)
            .where(RegistreJornadaLaboral.empresa_id == emp_id)
            .order_by(RegistreJornadaLaboral.data_jornada.desc())
            .limit(300)
        )
    ).scalars().all()
    return [
        (
            str(j.id),
            {
                "id": str(j.id),
                "empresa_id": str(emp_id),
                "usuari_id": str(j.usuari_id),
                "usuari_nom": op_map.get(str(j.usuari_id)),
                "data_jornada": _iso(j.data_jornada),
                "hora_inici": _iso(j.hora_inici),
                "hora_fi": _iso(j.hora_fi),
                "estat": j.estat,
                "hores_ordinaries": _num(j.hores_ordinaries, 0.0),
                "hores_extraordinaries": _num(j.hores_extraordinaries, 0.0),
                "hores_imputades_ot": _num(j.hores_imputades_ot, 0.0),
                "created_at": _iso(j.created_at),
            },
        )
        for j in rows
    ]


async def _collect_tiquets_despesa(
    db: AsyncSession, emp_id: uuid.UUID
) -> List[Tuple[str, Dict[str, Any]]]:
    items: List[Tuple[str, Dict[str, Any]]] = []

    despeses = (
        await db.execute(
            select(TiquetDespesa)
            .where(TiquetDespesa.empresa_id == emp_id)
            .order_by(TiquetDespesa.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    for t in despeses:
        items.append(
            (
                str(t.id),
                {
                    "id": str(t.id),
                    "empresa_id": str(emp_id),
                    "categoria": t.categoria,
                    "usuari_id": str(t.usuari_id) if t.usuari_id else None,
                    "vehicle_id": str(t.vehicle_id) if t.vehicle_id else None,
                    "ordre_treball_id": str(t.ordre_treball_id) if t.ordre_treball_id else None,
                    "data_tiquet": _iso(t.data_tiquet),
                    "rao_social": t.rao_social,
                    "import_total": _num(t.import_total, 0.0),
                    "estat_aprovacio": t.estat_aprovacio,
                    "created_at": _iso(t.created_at),
                },
            )
        )

    comb = (
        await db.execute(
            select(TiquetCombustible)
            .where(TiquetCombustible.empresa_id == emp_id)
            .order_by(TiquetCombustible.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    for tc in comb:
        items.append(
            (
                f"comb_{tc.id}",
                {
                    "id": str(tc.id),
                    "empresa_id": str(emp_id),
                    "categoria": "COMBUSTIBLE",
                    "vehicle_id": str(tc.vehicle_id),
                    "usuari_id": str(tc.conductor_id) if tc.conductor_id else None,
                    "data_tiquet": _iso(tc.data_tiquet),
                    "import_total": _num(tc.import_euros, 0.0),
                    "litres": _num(tc.litres, 0.0),
                    "kwh_recarrega": _num(tc.kwh_recarrega),
                    "litres_adblue": _num(tc.litres_adblue),
                    "odometre_registrat": tc.odometre_registrat,
                    "created_at": _iso(tc.created_at),
                },
            )
        )

    carb = (
        await db.execute(
            select(TiquetCarburant)
            .where(TiquetCarburant.empresa_id == emp_id)
            .order_by(TiquetCarburant.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    for tcr in carb:
        items.append(
            (
                f"carb_{tcr.id}",
                {
                    "id": str(tcr.id),
                    "empresa_id": str(emp_id),
                    "categoria": "COMBUSTIBLE",
                    "vehicle_id": str(tcr.vehicle_id),
                    "usuari_id": str(tcr.operari_id) if tcr.operari_id else None,
                    "data_tiquet": _iso(tcr.data_repostatge),
                    "import_total": _num(tcr.import_, 0.0) if hasattr(tcr, "import_") else _num(getattr(tcr, "import", None), 0.0),
                    "litres": _num(tcr.litres, 0.0),
                    "odometre_registrat": tcr.odometre_valor,
                    "created_at": _iso(tcr.created_at),
                },
            )
        )

    return items


async def _collect_copilot_memorandums(
    db: AsyncSession, emp_id: uuid.UUID
) -> List[Tuple[str, Dict[str, Any]]]:
    rows = (
        await db.execute(
            select(MemorandumTecnicCopilot).where(MemorandumTecnicCopilot.empresa_id == emp_id)
        )
    ).scalars().all()
    return [
        (
            str(m.id),
            {
                "id": str(m.id),
                "empresa_id": str(emp_id),
                "ordre_treball_id": str(m.ordre_treball_id) if m.ordre_treball_id else None,
                "incidencia_id": str(m.incidencia_id) if m.incidencia_id else None,
                "dictamen_pericial": m.dictamen_pericial,
                "motiu_dictamen": m.motiu_dictamen,
                "estimacio_temps_extra_minuts": m.estimacio_temps_extra_minuts,
                "cost_estimat_total": _num(m.cost_estimat_total, 0.0),
                "estat": m.estat,
                "validat_per_enginyer": bool(m.validat_per_enginyer),
                "created_at": _iso(m.created_at),
            },
        )
        for m in rows
    ]


async def _collect_protocols_interns(
    db: AsyncSession, emp_id: uuid.UUID
) -> List[Tuple[str, Dict[str, Any]]]:
    rows = (
        await db.execute(
            select(FaqCorporativaRag).where(
                FaqCorporativaRag.empresa_id == emp_id,
                FaqCorporativaRag.actiu.is_(True),
            )
        )
    ).scalars().all()
    return [
        (
            f"faq_{f.id}",
            {
                "id": str(f.id),
                "empresa_id": str(emp_id),
                "pregunta": f.pregunta,
                "titol": f.pregunta,
                "resposta": f.resposta,
                "contingut": f.resposta,
                "categoria": f.categoria or "PROCEDIMENT",
                "tags": f.paraules_clau or "",
                "created_at": _iso(f.created_at),
            },
        )
        for f in rows
    ]


_COLLECTORS: Dict[str, Callable[[AsyncSession, uuid.UUID], Awaitable[List[Tuple[str, Dict[str, Any]]]]]] = {
    "clients": _collect_clients,
    "finques": _collect_finques,
    "contractes": _collect_contractes,
    "proveidors": _collect_proveidors,
    "magatzem_articles": _collect_magatzem_articles,
    "magatzem_eines": _collect_magatzem_eines,
    "albarans": _collect_albarans,
    "factures_proveidors": _collect_factures_proveidors,
    "picking": _collect_picking,
    "pressupostos": _collect_pressupostos,
    "factures_pdf": _collect_factures_pdf,
    "ots_actives": _collect_ots_actives,
    "ots_historic": _collect_ots_historic,
    "ots_informes": _collect_ots_informes,
    "copilot_mermes_preus": _collect_copilot_mermes_preus,
    "incidencies_registres": _collect_incidencies,
    "vehicles": _collect_vehicles,
    "alertes_flota": _collect_alertes_flota,
    "operaris": _collect_operaris,
    "jornades": _collect_jornades,
    "tiquets_despesa": _collect_tiquets_despesa,
    "copilot_memorandums": _collect_copilot_memorandums,
    "protocols_interns": _collect_protocols_interns,
}


async def _is_disk_writable_now(db: AsyncSession, emp_uuid: uuid.UUID) -> bool:
    """Comprova si el disc dur dedicat de l'empresa és accessible ara mateix (WSS online o LOCAL_FS)."""
    try:
        mode, _target, _secret = await SovereignStorageGateway.resoldre_desti_disc_empresa(db, emp_uuid)
    except Exception:
        return False

    if mode == "LOCAL_FS":
        return True
    if mode == "WSS_TUNNEL":
        return await vault_tunnel_broker.is_online(empresa_target_key(emp_uuid))
    return False


async def sincronitzar_categoria_al_disc(
    db: AsyncSession,
    empresa_id: uuid.UUID | str,
    categoria: str,
    *,
    only_missing: bool = True,
    max_concurrency: int = 6,
) -> Dict[str, int]:
    """Sincronitza una única categoria des de PostgreSQL cap al disc dur sobirà de l'empresa.

    Retorna `{"escrits": N, "existents": M, "total_bd": T, "errors": E}`.
    """
    collector = _COLLECTORS.get(categoria)
    if collector is None:
        return {"escrits": 0, "existents": 0, "total_bd": 0, "errors": 0}

    emp_uuid = empresa_id if isinstance(empresa_id, uuid.UUID) else uuid.UUID(str(empresa_id))
    if not await _is_disk_writable_now(db, emp_uuid):
        return {"escrits": 0, "existents": 0, "total_bd": 0, "errors": 0}

    # Aïllament RLS obligatori abans de consultar PostgreSQL
    try:
        await set_tenant_context(db, str(emp_uuid))
    except Exception as exc:
        logger.warning("No s'ha pogut establir context RLS per sync %s/%s: %s", emp_uuid, categoria, exc)

    rows = await collector(db, emp_uuid)
    total_bd = len(rows)
    if total_bd == 0:
        return {"escrits": 0, "existents": 0, "total_bd": 0, "errors": 0}

    existing_ids: set[str] = set()
    if only_missing:
        try:
            existents = await SovereignStorageGateway.llegir_entitats_json(db, emp_uuid, categoria)
            for item in existents:
                meta = item.get("_sovereign_meta")
                if isinstance(meta, dict) and meta.get("item_id"):
                    existing_ids.add(str(meta["item_id"]))
                if item.get("id"):
                    existing_ids.add(str(item["id"]))
        except Exception as exc:
            logger.warning(
                "Error llegint fitxes existents de %s per empresa=%s durant sync: %s",
                categoria,
                emp_uuid,
                exc,
            )

    pendents = [
        (item_id, payload)
        for item_id, payload in rows
        if not only_missing or (item_id not in existing_ids and str(payload.get("id") or "") not in existing_ids)
    ]

    existents_count = total_bd - len(pendents)
    if not pendents:
        return {"escrits": 0, "existents": existents_count, "total_bd": total_bd, "errors": 0}

    sem = asyncio.Semaphore(max(1, max_concurrency))
    escrits = 0
    errors = 0

    async def _write_one(item_id: str, payload: Dict[str, Any]) -> None:
        nonlocal escrits, errors
        async with sem:
            try:
                await SovereignStorageGateway.desar_entitat_json(
                    db=db,
                    empresa_id=emp_uuid,
                    categoria=categoria,
                    item_id=item_id,
                    dades=payload,
                )
                escrits += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    "Error sincronitzant %s/%s al disc d'empresa=%s: %s",
                    categoria,
                    item_id,
                    emp_uuid,
                    exc,
                )

    await asyncio.gather(*(_write_one(item_id, payload) for item_id, payload in pendents))

    if escrits > 0:
        logger.info(
            "Sincronització sobirana %s per empresa=%s: escrits=%d, existents=%d, errors=%d",
            categoria,
            emp_uuid,
            escrits,
            existents_count,
            errors,
        )
    return {
        "escrits": escrits,
        "existents": existents_count,
        "total_bd": total_bd,
        "errors": errors,
    }


async def sincronitzar_entitats_empresa_al_disc(
    db: AsyncSession,
    empresa_id: uuid.UUID | str,
    *,
    categories: Optional[Sequence[str]] = None,
    only_missing: bool = True,
) -> Dict[str, Any]:
    """Reconcilia totes les categories operatives de l'empresa cap al seu disc dur sobirà."""
    emp_uuid = empresa_id if isinstance(empresa_id, uuid.UUID) else uuid.UUID(str(empresa_id))
    cats: Iterable[str] = categories if categories is not None else CATEGORIES_SINCRONITZABLES

    if not await _is_disk_writable_now(db, emp_uuid):
        return {
            "empresa_id": str(emp_uuid),
            "online": False,
            "total_escrits": 0,
            "total_errors": 0,
            "categories": {},
        }

    detall: Dict[str, Dict[str, int]] = {}
    total_escrits = 0
    total_errors = 0

    for cat in cats:
        if cat not in _COLLECTORS:
            continue
        try:
            res = await sincronitzar_categoria_al_disc(
                db, emp_uuid, cat, only_missing=only_missing
            )
            detall[cat] = res
            total_escrits += res["escrits"]
            total_errors += res["errors"]
        except Exception as exc:
            logger.warning(
                "Fallada sincronitzant categoria=%s per empresa=%s: %s", cat, emp_uuid, exc
            )
            detall[cat] = {"escrits": 0, "existents": 0, "total_bd": 0, "errors": 1}
            total_errors += 1

    # Reiniciem el cooldown de les categories sincronitzades
    for cat in detall:
        _READ_REPAIR_LAST_TS.pop((str(emp_uuid), cat), None)

    return {
        "empresa_id": str(emp_uuid),
        "online": True,
        "total_escrits": total_escrits,
        "total_errors": total_errors,
        "categories": detall,
    }


async def reparar_categoria_buida_si_cal(
    db: Any,
    empresa_id: uuid.UUID | str,
    categoria: str,
) -> bool:
    """Auto-repara una carpeta buida del disc sobirà escrivint els registres faltants via WSS.

    IMPORTANT:
    - Mai s'executa si `db` no és una `AsyncSession` real (protegeix tests amb stubs).
    - Mai s'executa si el disc no és escrivible ara mateix (WSS offline).
    - Aplica un cooldown de 30s per `(empresa_id, categoria)` i un lock per evitar tempestes.
    - Retorna `True` només si s'ha escrit almenys 1 fitxa nova al disc (el llamador torna a
      llegir del disc sobirà verificat amb HMAC).
    """
    if categoria not in _COLLECTORS:
        return False
    if not isinstance(db, AsyncSession):
        return False

    emp_str = str(empresa_id)
    key = (emp_str, categoria)
    now = time.monotonic()
    last_ts = _READ_REPAIR_LAST_TS.get(key)
    if last_ts is not None and (now - last_ts) < _READ_REPAIR_COOLDOWN_S:
        return False

    lock = _READ_REPAIR_LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        last_ts = _READ_REPAIR_LAST_TS.get(key)
        if last_ts is not None and (now - last_ts) < _READ_REPAIR_COOLDOWN_S:
            return False

        _READ_REPAIR_LAST_TS[key] = now
        try:
            emp_uuid = empresa_id if isinstance(empresa_id, uuid.UUID) else uuid.UUID(emp_str)
            stats = await sincronitzar_categoria_al_disc(
                db, emp_uuid, categoria, only_missing=True
            )
            return stats["escrits"] > 0
        except Exception as exc:
            logger.warning(
                "Auto-reparació de categoria=%s per empresa=%s fallida: %s",
                categoria,
                emp_str,
                exc,
            )
            return False
