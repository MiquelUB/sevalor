"""Servei de detecció automàtica de trencament d'estoc i redacció HITL d'emails a proveïdors (FR-010)."""

import logging
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    AlertaGarantiaRecompra,
    Article,
    Empresa,
    EstocMagatzem,
    Proveidor,
)
from app.services.pressupost_service import construir_mailto_url

logger = logging.getLogger("sevalor.recompra")

_EMAIL_REGEX = re.compile(r"^[^@\s\r\n]+@[^@\s\r\n]+\.[^@\s\r\n]+$")


def _sanititzar_linia(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"[\r\n\t]+", " ", str(text)).strip()


def validar_email_destinatari(email_raw: Optional[str]) -> str:
    """Valida format d'email segur contra injecció de capçaleres SMTP."""
    net = (email_raw or "").strip()
    if not net or not _EMAIL_REGEX.match(net):
        raise ValueError("Cal indicar una adreça electrònica de destinatari vàlida.")
    return net


def construir_text_esborrany_email_recompra(
    empresa_nom: str,
    proveidor_nom: Optional[str],
    items: Sequence[Dict[str, Any]],
    notes_extra: Optional[str] = None,
) -> Tuple[str, str]:
    """Construeix assumpte i cos d'esborrany d'email de comanda de reposició (HITL, sense auto-enviament)."""
    emp_net = _sanititzar_linia(empresa_nom) or "la nostra empresa"
    prov_net = _sanititzar_linia(proveidor_nom) or "Proveïdor"

    if len(items) == 1:
        it = items[0]
        ref = _sanititzar_linia(str(it.get("referencia") or "S/R"))
        nom = _sanititzar_linia(str(it.get("nom") or "Article"))
        assumpte = f"Sol·licitud de reposició de material — {ref} {nom} ({emp_net})"[:180]
    else:
        assumpte = (
            f"Sol·licitud de reposició d'estoc ({len(items)} referències) — {emp_net}"
        )[:180]

    linies_cos: List[str] = [
        f"Benvolguts {prov_net},",
        "",
        f"Des de {emp_net} us fem arribar la sol·licitud de comanda de reposició per als següents articles en trencament o sota estoc mínim:",
        "",
    ]
    for it in items:
        ref = _sanititzar_linia(str(it.get("referencia") or "S/R"))
        nom = _sanititzar_linia(str(it.get("nom") or "Material"))
        unitat = _sanititzar_linia(str(it.get("unitat_mesura") or "UNITAT"))
        qty = float(it.get("quantitat_aprovada") or it.get("quantitat_proposada") or 1.0)
        qty_str = f"{qty:g}"
        cb = _sanititzar_linia(str(it.get("codi_barres") or ""))
        cb_txt = f" | Codi barres: {cb}" if cb else ""
        linies_cos.append(f"- [{ref}] {nom}: {qty_str} {unitat}{cb_txt}")

    if notes_extra and notes_extra.strip():
        linies_cos.extend(["", f"Observacions: {notes_extra.strip()}"])

    linies_cos.extend(
        [
            "",
            "Si us plau, confirmeu-nos disponibilitat, preu vigent i termini previst d'entrega al nostre magatzem central.",
            "",
            "Atentament,",
            f"Departament de Compres i Magatzem — {emp_net}",
        ]
    )

    return assumpte, "\n".join(linies_cos)


def enviar_email_recompra_smtp(
    *,
    empresa_nom: str,
    destinatari_email: str,
    assumpte: str,
    cos_missatge: str,
) -> Tuple[bool, Optional[str]]:
    """Envia el correu de reposició al proveïdor via SMTP Stalwart només després de confirmació humana."""
    dest = validar_email_destinatari(destinatari_email)
    smtp_host = (settings.STALWART_SMTP_HOST or "").strip()
    smtp_port = int(settings.STALWART_SMTP_PORT or 587)
    smtp_user = (settings.STALWART_USER or "").strip()
    smtp_pass = settings.STALWART_PASSWORD

    if not smtp_host or (smtp_host in ("localhost", "127.0.0.1") and not smtp_pass):
        return (
            False,
            "El servidor de correu SMTP no està configurat a l'entorn (STALWART_SMTP_HOST / STALWART_PASSWORD).",
        )

    msg = EmailMessage()
    msg["From"] = f"{_sanititzar_linia(empresa_nom) or 'Sevalor'} <{smtp_user or 'no-reply@sevalor.app'}>"
    msg["To"] = dest
    msg["Subject"] = _sanititzar_linia(assumpte)
    msg.set_content(cos_missatge)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
            server.ehlo()
            if smtp_port in (587, 25):
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPException:
                    pass
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, None
    except Exception as exc:
        logger.warning("Error enviant email de recompra per SMTP (%s:%s): %s", smtp_host, smtp_port, exc)
        return False, f"No s'ha pogut connectar al servidor SMTP ({smtp_host}:{smtp_port}): {exc}"


async def avaluar_i_sincronitzar_alertes_recompra(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    article_ids: Optional[Sequence[uuid.UUID]] = None,
) -> List[AlertaGarantiaRecompra]:
    """Avalua trencaments d'estoc reals i sincronitza alertes RECOMPRA_STOCK amb esborrany d'email HITL.

    - Crea o actualitza alertes `ACTIVA` quan `actiu is True`, `estoc_minim > 0` i `disponible <= estoc_minim`.
    - Auto-resol (`RESOLTA_ESTOC`) les alertes `ACTIVA` quan l'estoc es reposa o l'article es desactiva.
    - MAI envia emails automàticament (`enviat_automaticament=False`, `requereix_aprovacio_humana=True`).
    Retorna les alertes acabades de crear en aquesta passada.
    """
    empresa_nom = (
        await db.execute(select(Empresa.nom).where(Empresa.id == empresa_id))
    ).scalar() or "Sevalor"

    stmt_arts = (
        select(Article, Proveidor.rao_social, Proveidor.email)
        .outerjoin(Proveidor, Article.proveidor_id == Proveidor.id)
        .where(Article.empresa_id == empresa_id)
    )
    if article_ids is not None:
        ids_clean = [aid for aid in article_ids if aid is not None]
        if not ids_clean:
            return []
        stmt_arts = stmt_arts.where(Article.id.in_(ids_clean))

    articles_rows = (await db.execute(stmt_arts)).all()
    if not articles_rows:
        return []

    target_art_ids = [art.id for art, _pnom, _pemail in articles_rows]

    stmt_estocs = (
        select(
            EstocMagatzem.article_id,
            func.coalesce(func.sum(EstocMagatzem.quantitat_fisica), 0.0),
            func.coalesce(func.sum(EstocMagatzem.quantitat_virtual_reservada), 0.0),
        )
        .where(
            EstocMagatzem.empresa_id == empresa_id,
            EstocMagatzem.article_id.in_(target_art_ids),
        )
        .group_by(EstocMagatzem.article_id)
    )
    estoc_map: Dict[uuid.UUID, float] = {
        row[0]: max(0.0, float(row[1] or 0.0) - float(row[2] or 0.0))
        for row in (await db.execute(stmt_estocs)).all()
    }

    stmt_existing = (
        select(AlertaGarantiaRecompra)
        .where(
            AlertaGarantiaRecompra.empresa_id == empresa_id,
            AlertaGarantiaRecompra.tipus_alerta == "RECOMPRA_STOCK",
            AlertaGarantiaRecompra.estat.in_(("ACTIVA", "APROVADA")),
            AlertaGarantiaRecompra.article_id.in_(target_art_ids),
        )
        .order_by(AlertaGarantiaRecompra.updated_at.desc())
    )
    active_map: Dict[uuid.UUID, List[AlertaGarantiaRecompra]] = {}
    approved_map: Dict[uuid.UUID, List[AlertaGarantiaRecompra]] = {}
    for al in (await db.execute(stmt_existing)).scalars().all():
        if not al.article_id:
            continue
        if al.estat == "ACTIVA":
            active_map.setdefault(al.article_id, []).append(al)
        elif al.estat == "APROVADA":
            approved_map.setdefault(al.article_id, []).append(al)

    ara = datetime.now(timezone.utc)
    noves_alertes: List[AlertaGarantiaRecompra] = []

    for art, prov_nom, prov_email in articles_rows:
        disponible = estoc_map.get(art.id, 0.0)
        estoc_min = float(art.estoc_minim or 0.0)
        en_trencament = bool(
            (art.actiu is None or art.actiu is True)
            and estoc_min > 0.0
            and disponible <= estoc_min
        )
        actives = active_map.get(art.id, [])
        aprovades = approved_map.get(art.id, [])

        if not en_trencament:
            # Quan entra estoc i se supera el mínim, resol tant pendents com comandes aprovades en curs.
            for alerta_prev in actives + aprovades:
                prop_old = dict(alerta_prev.dades_comanda_proposta or {})
                prop_old["estat_hitl"] = "RESOLTA_PER_ESTOC"
                prop_old["estoc_disponible"] = disponible
                prop_old["resolt_en"] = ara.isoformat()
                alerta_prev.estat = "RESOLTA_ESTOC"
                alerta_prev.dades_comanda_proposta = prop_old
                alerta_prev.updated_at = ara
            continue

        # Si ja hi ha una comanda aprovada/enviada esperant recepció de material, no duplicar esborrany nou.
        if not actives and aprovades:
            continue

        alerta_existent = actives[0] if actives else None

        estoc_opt = float(art.estoc_optim or 0.0)
        qty_sug = round(max(estoc_opt - disponible, estoc_min * 2.0 - disponible, 1.0), 2)
        preu_unit = float(getattr(art, "pmp_actual", None) or art.preu_cost or 0.0)

        item_dict: Dict[str, Any] = {
            "article_id": str(art.id),
            "referencia": art.referencia_inventari,
            "codi_barres": getattr(art, "codi_barres", None),
            "nom": art.nom,
            "unitat_mesura": art.unitat_mesura,
            "estoc_disponible": disponible,
            "estoc_minim": estoc_min,
            "estoc_optim": estoc_opt,
            "quantitat_proposada": qty_sug,
        }
        assumpte, cos = construir_text_esborrany_email_recompra(
            empresa_nom=empresa_nom,
            proveidor_nom=prov_nom,
            items=[item_dict],
        )
        mailto_url = (
            construir_mailto_url(prov_email, assumpte, cos)
            if prov_email and _EMAIL_REGEX.match(str(prov_email).strip())
            else None
        )

        proposta: Dict[str, Any] = {
            **item_dict,
            "proveidor_id": str(art.proveidor_id) if art.proveidor_id else None,
            "proveidor_nom": prov_nom,
            "proveidor_email": prov_email,
            "preu_unitari_estimat": preu_unit,
            "import_estimat": round(qty_sug * preu_unit, 2),
            "esborrany_email_assumpte": assumpte,
            "esborrany_email_cos": cos,
            "mailto_url": mailto_url,
            "enviat_automaticament": False,
            "requereix_aprovacio_humana": True,
            "estat_hitl": "ESBORRANY_PENDENT_APROVACIO",
        }
        missatge = (
            f"Trencament d'estoc a {art.nom} ({art.referencia_inventari}): "
            f"disponible {disponible} <= mínim {estoc_min}. Esborrany per {qty_sug} {art.unitat_mesura}."
        )

        if alerta_existent is not None:
            alerta_existent.proveidor_id = art.proveidor_id
            alerta_existent.missatge = missatge
            alerta_existent.dades_comanda_proposta = proposta
            alerta_existent.updated_at = ara
        else:
            nova = AlertaGarantiaRecompra(
                empresa_id=empresa_id,
                tipus_alerta="RECOMPRA_STOCK",
                article_id=art.id,
                proveidor_id=art.proveidor_id,
                missatge=missatge,
                estat="ACTIVA",
                dades_comanda_proposta=proposta,
            )
            db.add(nova)
            noves_alertes.append(nova)

    await db.flush()
    return noves_alertes


def agrupar_alertes_recompra_per_proveidor(
    rows: Sequence[
        Tuple[
            AlertaGarantiaRecompra,
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[str],
        ]
    ],
    empresa_nom: str,
    rol: str,
) -> List[Dict[str, Any]]:
    """Agrupa alertes ACTIVA per proveïdor i genera un únic esborrany d'email conjunt (FR-010)."""
    is_enginyer = rol.upper() == "ENGINYER"
    grups: Dict[str, Dict[str, Any]] = {}

    for alerta, art_nom, art_ref, art_cb, prov_nom, prov_email in rows:
        proposta = dict(alerta.dades_comanda_proposta or {})
        prov_id_str = str(alerta.proveidor_id) if alerta.proveidor_id else "SENSE_PROVEIDOR"
        p_nom = prov_nom or proposta.get("proveidor_nom") or "Proveïdor sense assignar"
        p_email = prov_email or proposta.get("proveidor_email")

        if prov_id_str not in grups:
            grups[prov_id_str] = {
                "grup_key": prov_id_str,
                "proveidor_id": str(alerta.proveidor_id) if alerta.proveidor_id else None,
                "proveidor_nom": p_nom,
                "proveidor_email": p_email,
                "alerta_ids": [],
                "items": [],
                "import_total_estimat": 0.0,
            }

        qty_sug = float(proposta.get("quantitat_aprovada") or proposta.get("quantitat_proposada") or 1.0)
        preu_unit = float(proposta.get("preu_unitari_estimat") or 0.0)
        imp = float(proposta.get("import_estimat") or round(qty_sug * preu_unit, 2))

        grups[prov_id_str]["alerta_ids"].append(str(alerta.id))
        grups[prov_id_str]["items"].append(
            {
                "alerta_id": str(alerta.id),
                "article_id": str(alerta.article_id) if alerta.article_id else None,
                "referencia": art_ref or proposta.get("referencia"),
                "codi_barres": art_cb or proposta.get("codi_barres"),
                "nom": art_nom or proposta.get("nom"),
                "unitat_mesura": proposta.get("unitat_mesura") or "UNITAT",
                "estoc_disponible": float(proposta.get("estoc_disponible") or 0.0),
                "estoc_minim": float(proposta.get("estoc_minim") or 0.0),
                "quantitat_proposada": qty_sug,
                "preu_unitari_estimat": None if is_enginyer else preu_unit,
                "import_estimat": None if is_enginyer else imp,
            }
        )
        grups[prov_id_str]["import_total_estimat"] += imp

    resultat: List[Dict[str, Any]] = []
    for g in grups.values():
        assumpte, cos = construir_text_esborrany_email_recompra(
            empresa_nom=empresa_nom,
            proveidor_nom=g["proveidor_nom"] if g["proveidor_id"] else None,
            items=g["items"],
        )
        p_email = g["proveidor_email"]
        mailto_url = (
            construir_mailto_url(p_email, assumpte, cos)
            if p_email and _EMAIL_REGEX.match(str(p_email).strip())
            else None
        )
        resultat.append(
            {
                "grup_key": g["grup_key"],
                "proveidor_id": g["proveidor_id"],
                "proveidor_nom": g["proveidor_nom"],
                "proveidor_email": p_email,
                "alerta_ids": g["alerta_ids"],
                "total_articles": len(g["items"]),
                "items": g["items"],
                "import_total_estimat": None if is_enginyer else round(g["import_total_estimat"], 2),
                "esborrany_email_assumpte": assumpte,
                "esborrany_email_cos": cos,
                "mailto_url": mailto_url,
                "enviat_automaticament": False,
                "requereix_aprovacio_humana": True,
            }
        )
    return resultat
