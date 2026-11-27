"""
Motor de Passarel·la d'Emmagatzematge Sobirà (Zero-Storage Gateway).

Garanteix que totes les dades i fitxers de cada empresa es guardin exclusivament
al seu propi disc dur (`disc_dur_url`), ordenats per carpetes temàtiques:
clients, proveïdors, magatzem, factures, plànols, ordres_treball, incidències,
flota_i_operaris, copilot_ia (amb autoaprenentatge) i protocols_i_manuals.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.network_utils import (
    build_wss_tunnel_uri,
    is_wss_tunnel_uri,
    resolve_empresa_vault_token,
)
from app.models.models import Empresa
from app.services.vault_tunnel import (
    SUPERADMIN_TARGET_KEY,
    VaultTunnelError,
    VaultTunnelOfflineError,
    VaultTunnelRemoteError,
    VaultTunnelTimeoutError,
    empresa_target_key,
    vault_tunnel_broker,
)

logger = logging.getLogger("sevalor.sovereign_storage")

# Mapa canònic de categories lògiques -> carpetes físiques al disc dur del client
MAPA_CARPETES_CLIENT: Dict[str, str] = {
    # 01. Clients
    "clients": "01_clients/fitxes",
    "finques": "01_clients/finques_i_instal_lacions",
    "contractes": "01_clients/contractes_manteniment",
    # 02. Proveïdors
    "proveidors": "02_proveidors/fitxes",
    # 03. Magatzem
    "magatzem_articles": "03_magatzem/articles_i_estoc",
    "magatzem_eines": "03_magatzem/eines_custodia",
    "albarans": "03_magatzem/albarans_compra",
    "picking": "03_magatzem/picking_fulles",
    # 04. Factures i Comptabilitat
    "factures_pdf": "04_factures/emeses_verifactu_pdf",
    "factures_xml": "04_factures/emeses_verifactu_xml",
    "pressupostos": "04_factures/prefactures_i_pressupostos",
    "factures_proveidors": "04_factures/factures_proveidors",
    # 05. Plànols
    "planols": "05_planols/arxius_base",
    "planols_capes": "05_planols/capes_vectorials",
    "planols_informes": "05_planols/informes_exportats",
    # 06. Ordres de Treball
    "ots_actives": "06_ordres_treball/actives_buffer",
    "ots_historic": "06_ordres_treball/historic_tancades",
    "ots_informes": "06_ordres_treball/informes_post_obra",
    # 07. Incidències de Camp
    "incidencies_fotos": "07_incidencies/fotos_camp",
    "incidencies_audios": "07_incidencies/audios_veu",
    "incidencies_registres": "07_incidencies/registres",
    # 08. Flota i Operaris
    "vehicles": "08_flota_i_operaris/vehicles",
    "alertes_flota": "08_flota_i_operaris/vehicles/alertes_flota",
    "operaris": "08_flota_i_operaris/operaris",
    "documents_operaris": "08_flota_i_operaris/operaris/documents_rrhh",
    "alertes_operaris": "08_flota_i_operaris/operaris/alertes_rrhh",
    "tiquets_despesa": "08_flota_i_operaris/tiquets_despesa",
    "jornades": "08_flota_i_operaris/registres_jornada",
    # 09. Agent Copilot Dedicat i Autoaprenentatge
    "copilot_prompt": "09_copilot_ia/prompt_sistema",
    "copilot_memorandums": "09_copilot_ia/autoaprenentatge/memorandums_tecnics",
    "copilot_mermes_preus": "09_copilot_ia/autoaprenentatge/historic_preus_i_mermes",
    "copilot_feedback": "09_copilot_ia/autoaprenentatge/converses_i_feedback",
    "copilot_rag_index": "09_copilot_ia/index_vectorial_rag",
    # 10. Protocols de l'Empresa i Manuals Tècnics
    "protocols_interns": "10_protocols_i_manuals/procediments_interns",
    "manuals_fabricants": "10_protocols_i_manuals/manuals_fabricants",
    "normativa_prl": "10_protocols_i_manuals/normativa_i_prl",
    # 11. Configuració i Backups
    "configuracio": "11_configuracio_i_backups/identitat_camaleo",
    "backups": "11_configuracio_i_backups/backups_locals",
}


def sanititzar_nom(nom: str) -> str:
    """Neteja qualsevol nom de fitxer o identificador per impedir Path Traversal."""
    clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", str(nom).strip())
    if not clean or clean in (".", ".."):
        raise ValueError("Identificador o nom d'arxiu invàlid.")
    return clean


def inicialitzar_arbre_carpetes_disc(root_path: str | Path) -> List[str]:
    """Crea físicament totes les carpetes i subcarpetes oficials al disc dur del client."""
    base = Path(root_path).resolve()
    creades: List[str] = []
    for sub in sorted(set(MAPA_CARPETES_CLIENT.values())):
        folder = (base / sub).resolve()
        if not folder.is_relative_to(base):
            raise HTTPException(status_code=400, detail="Ruta de subcarpeta fora del disc autoritzat.")
        folder.mkdir(parents=True, exist_ok=True)
        creades.append(str(folder))
    return creades


CARPETES_SUPERADMIN: List[str] = [
    "01_tenants_b2b/fitxes_empreses",
    "01_tenants_b2b/llicencies_i_contractes",
    "02_facturacio_saas/factures_b2b_json",
    "02_facturacio_saas/factures_b2b_pdf",
    "02_facturacio_saas/factures_b2b_xml",
    "03_crm_comercial/leads",
    "03_crm_comercial/oportunitats",
    "03_crm_comercial/activitats",
    "04_rascador_prospeccio/tasques",
    "04_rascador_prospeccio/candidats",
    "04_rascador_prospeccio/criteris_feedback",
    "04_rascador_prospeccio/exclusions_rgpd",
    "05_correu_i_suport/missatges",
    "05_correu_i_suport/tiquets_suport",
    "06_telemetria_i_seguretat/auditoria",
    "06_telemetria_i_seguretat/alertes_seguretat",
    "06_telemetria_i_seguretat/certificats_baixa",
    "07_copilot_superadmin/prompt_sistema",
    "07_copilot_superadmin/memoria_ia",
    "08_backups_superadmin/backups_locals",
]

MAPA_CARPETES_SUPERADMIN: Dict[str, str] = {
    "tenants_fitxes": "01_tenants_b2b/fitxes_empreses",
    "tenants_llicencies": "01_tenants_b2b/llicencies_i_contractes",
    "saas_factures_json": "02_facturacio_saas/factures_b2b_json",
    "saas_factures_pdf": "02_facturacio_saas/factures_b2b_pdf",
    "saas_factures_xml": "02_facturacio_saas/factures_b2b_xml",
    "crm_leads": "03_crm_comercial/leads",
    "crm_oportunitats": "03_crm_comercial/oportunitats",
    "crm_activitats": "03_crm_comercial/activitats",
    "rascador_tasques": "04_rascador_prospeccio/tasques",
    "rascador_candidats": "04_rascador_prospeccio/candidats",
    "rascador_criteris": "04_rascador_prospeccio/criteris_feedback",
    "rascador_exclusions": "04_rascador_prospeccio/exclusions_rgpd",
    "correu_missatges": "05_correu_i_suport/missatges",
    "suport_tiquets": "05_correu_i_suport/tiquets_suport",
    "auditoria": "06_telemetria_i_seguretat/auditoria",
    "alertes_seguretat": "06_telemetria_i_seguretat/alertes_seguretat",
    "baixes_rgpd": "06_telemetria_i_seguretat/certificats_baixa",
    "copilot_prompt": "07_copilot_superadmin/prompt_sistema",
    "copilot_memoria": "07_copilot_superadmin/memoria_ia",
    "backups": "08_backups_superadmin/backups_locals",
}


def inicialitzar_arbre_carpetes_superadmin(root_path: str | Path) -> List[str]:
    """Crea físicament les 20 carpetes oficials del Disc Dur dedicat del Superadmin."""
    base = Path(root_path).resolve()
    creades: List[str] = []
    for sub in sorted(set(MAPA_CARPETES_SUPERADMIN.values())):
        folder = (base / sub).resolve()
        if not folder.is_relative_to(base):
            raise HTTPException(status_code=400, detail="Ruta de carpeta Superadmin invàlida.")
        folder.mkdir(parents=True, exist_ok=True)
        creades.append(str(folder))
    return creades


class SovereignStorageGateway:
    """Passarel·la que enruta totes les lectures i escriptures cap al disc dur del client."""

    _TRANSIT_ENC_PREFIX = b"SVENC1:"
    _INITIAL_TRANSIT_DIR = Path(
        os.getenv("SOVEREIGN_TRANSIT_QUEUE_DIR", "/tmp/sevalor_transit_queue")
    )
    TRANSIT_QUEUE_DIR = _INITIAL_TRANSIT_DIR

    @classmethod
    def _get_transit_queue_dir(cls) -> Path:
        if cls.TRANSIT_QUEUE_DIR != cls._INITIAL_TRANSIT_DIR:
            return cls.TRANSIT_QUEUE_DIR
        return Path(os.getenv("SOVEREIGN_TRANSIT_QUEUE_DIR", str(cls.TRANSIT_QUEUE_DIR)))

    @classmethod
    def _derive_transit_keys(cls, empresa_id: str | uuid.UUID, nonce: bytes) -> Tuple[bytes, bytes]:
        master = settings.SECRET_KEY.encode("utf-8")
        enc_key = hmac.new(master, f"transit-enc:{empresa_id}".encode("utf-8") + nonce, hashlib.sha256).digest()
        mac_key = hmac.new(master, f"transit-mac:{empresa_id}".encode("utf-8") + nonce, hashlib.sha256).digest()
        return enc_key, mac_key

    @classmethod
    def _encrypt_transit_payload(cls, empresa_id: str | uuid.UUID, raw_bytes: bytes) -> bytes:
        nonce = secrets.token_bytes(16)
        enc_key, mac_key = cls._derive_transit_keys(empresa_id, nonce)
        out = bytearray(len(raw_bytes))
        counter = 0
        offset = 0
        while offset < len(raw_bytes):
            block = hmac.new(enc_key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
            chunk_len = min(len(block), len(raw_bytes) - offset)
            for i in range(chunk_len):
                out[offset + i] = raw_bytes[offset + i] ^ block[i]
            offset += chunk_len
            counter += 1
        ciphertext = bytes(out)
        tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        return cls._TRANSIT_ENC_PREFIX + nonce + tag + ciphertext

    @classmethod
    def _decrypt_transit_payload(cls, empresa_id: str | uuid.UUID, stored_bytes: bytes) -> bytes:
        if not stored_bytes.startswith(cls._TRANSIT_ENC_PREFIX):
            return stored_bytes
        body = stored_bytes[len(cls._TRANSIT_ENC_PREFIX) :]
        if len(body) < 48:
            raise ValueError("Paquet de cua de trànsit corrupte.")
        nonce = body[:16]
        tag = body[16:48]
        ciphertext = body[48:]
        enc_key, mac_key = cls._derive_transit_keys(empresa_id, nonce)
        expected_tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Signatura HMAC del paquet de trànsit invàlida.")
        out = bytearray(len(ciphertext))
        counter = 0
        offset = 0
        while offset < len(ciphertext):
            block = hmac.new(enc_key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
            chunk_len = min(len(block), len(ciphertext) - offset)
            for i in range(chunk_len):
                out[offset + i] = ciphertext[offset + i] ^ block[i]
            offset += chunk_len
            counter += 1
        return bytes(out)

    @staticmethod
    async def recuperar_fitxa_superadmin_empresa(
        empresa_id: str | uuid.UUID,
    ) -> Dict[str, Any]:
        """Recupera la fitxa B2B exclusiva d'aquesta empresa des del Disc Dur de Superadmin."""
        emp_str = str(empresa_id)
        try:
            fitxes = await SuperadminStorageGateway.llegir_entitats_json("tenants_fitxes")
            for f in fitxes:
                if isinstance(f, dict) and str(f.get("id") or f.get("empresa_id") or "") == emp_str:
                    return f
        except Exception:
            pass
        return {}

    @classmethod
    async def autocurar_config_tunel_empresa(
        cls,
        db: Optional[AsyncSession],
        emp: Optional[Empresa],
        *,
        commit: bool = False,
    ) -> bool:
        """
        Si a la fila SQL d'Empresa li falta disc_dur_url, node_ia_url, vault_token o node_ia_actiu,
        els restaura des de la fitxa exclusiva d'aquesta mateixa empresa al Disc de Superadmin.
        """
        if emp is None:
            return False
        needs_heal = (
            not getattr(emp, "disc_dur_url", None)
            or not getattr(emp, "node_ia_url", None)
            or not getattr(emp, "vault_token", None)
            or not bool(getattr(emp, "node_ia_actiu", False))
        )
        if not needs_heal:
            return False

        fitxa = await cls.recuperar_fitxa_superadmin_empresa(emp.id)
        if not fitxa:
            return False

        had_any_url_in_sql = bool(
            getattr(emp, "node_ia_url", None) or getattr(emp, "disc_dur_url", None)
        )
        changed = False
        f_disc = fitxa.get("disc_dur_url")
        if not getattr(emp, "disc_dur_url", None) and isinstance(f_disc, str) and f_disc.strip():
            emp.disc_dur_url = f_disc.strip()
            changed = True

        f_node = fitxa.get("node_ia_url")
        if not getattr(emp, "node_ia_url", None) and isinstance(f_node, str) and f_node.strip():
            emp.node_ia_url = f_node.strip()
            changed = True

        f_tok = fitxa.get("vault_token")
        if not getattr(emp, "vault_token", None) and isinstance(f_tok, str) and f_tok.strip():
            emp.vault_token = f_tok.strip()
            changed = True

        if (
            not had_any_url_in_sql
            and not bool(getattr(emp, "node_ia_actiu", False))
            and bool(fitxa.get("node_ia_actiu", False))
        ):
            if getattr(emp, "node_ia_url", None) or getattr(emp, "disc_dur_url", None):
                emp.node_ia_actiu = True
                changed = True

        if (
            not had_any_url_in_sql
            and not bool(getattr(emp, "feature_copilot_ia", False))
            and bool(fitxa.get("feature_copilot_ia", False))
        ):
            emp.feature_copilot_ia = True
            changed = True

        if changed and commit and db is not None:
            try:
                await db.commit()
            except Exception:
                pass
        return changed

    @staticmethod
    async def resoldre_desti_disc_empresa(
        db: Optional[AsyncSession], empresa_id: str | uuid.UUID
    ) -> Tuple[str, str, Optional[str]]:
        """
        Obté la destinació del disc dur exclusiu configurat per a l'empresa.
        Retorna: (mode: 'WSS_TUNNEL' | 'OFFLINE_TRANSIT' | 'LOCAL_FS', base_target: str, secret: Optional[str]).

        ADR-001 (Fase 3 — Túnel WSS Únic, Zero Dualitat):
        - Eliminat definitivament `HTTP_VAULT` i qualsevol fallback silenciós a Hetzner.
        - Si el túnel WSS de l'empresa (`empresa:<uuid>`) està connectat -> `WSS_TUNNEL`.
        - Si està desconnectat -> `OFFLINE_TRANSIT` (cua xifrada `SVENC1:` amb drenatge automàtic).
        """
        emp_uuid = uuid.UUID(str(empresa_id))
        target_key = empresa_target_key(emp_uuid)

        # 1. Únic transport sobirà en producció i proves WSS: Túnel Invers Natiu WSS
        if await vault_tunnel_broker.is_online(target_key):
            return ("WSS_TUNNEL", target_key, None)

        # 2. En mode TESTING fora de Docker, permet ruta física explícita per a unit tests antics (fins Fase 5)
        if os.getenv("TESTING") == "1" and not os.path.exists("/.dockerenv"):
            emp = None
            if db is not None:
                if isinstance(db, AsyncSession):
                    db_lock = db.info.setdefault("_sevalor_db_lock", asyncio.Lock())
                    async with db_lock:
                        res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
                else:
                    res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
                emp = res.scalars().first()
            raw_disc = (getattr(emp, "disc_dur_url", None) or "").strip() if emp else ""
            if (
                raw_disc
                and not is_wss_tunnel_uri(raw_disc)
                and not raw_disc.startswith(("http://", "https://", "Carpeta Local:"))
                and ":1234" not in raw_disc
                and raw_disc.startswith("/")
            ):
                inicialitzar_arbre_carpetes_disc(raw_disc)
                return ("LOCAL_FS", str(Path(raw_disc).resolve()), None)

        secret: Optional[str] = None
        if db is not None:
            if isinstance(db, AsyncSession):
                db_lock = db.info.setdefault("_sevalor_db_lock", asyncio.Lock())
                async with db_lock:
                    res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
            else:
                res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
            emp_off = res.scalars().first()
            if emp_off is not None:
                secret = resolve_empresa_vault_token(emp_off)

        return ("OFFLINE_TRANSIT", build_wss_tunnel_uri(emp_uuid), secret)

    @classmethod
    def comptar_cua_transit_empresa(cls, empresa_id: str | uuid.UUID) -> int:
        """Retorna el nombre de paquets xifrats `SVENC1:` pendents de drenar per a una empresa."""
        emp_dir = (cls._get_transit_queue_dir() / str(empresa_id)).resolve()
        if not emp_dir.exists():
            return 0
        return len(list(emp_dir.glob("*.meta.json")))

    @classmethod
    def _encuar_paquet_transit(
        cls,
        empresa_id: str | uuid.UUID,
        tipus: str,
        subcarpeta: str,
        identificador: str,
        payload_bytes: bytes,
        content_type: str = "application/json",
    ) -> str:
        """Guarda temporalment i xifrat en cua de trànsit quan l'ordinador del client està apagat."""
        emp_dir = (cls._get_transit_queue_dir() / str(empresa_id)).resolve()
        emp_dir.mkdir(parents=True, exist_ok=True)
        pkt_id = f"{int(datetime.now(timezone.utc).timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
        meta_path = emp_dir / f"{pkt_id}.meta.json"
        data_path = emp_dir / f"{pkt_id}.bin"
        meta = {
            "pkt_id": pkt_id,
            "empresa_id": str(empresa_id),
            "tipus": tipus,
            "subcarpeta": subcarpeta,
            "identificador": identificador,
            "content_type": content_type,
            "encrypted": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        data_path.write_bytes(cls._encrypt_transit_payload(empresa_id, payload_bytes))
        return f"transit://{empresa_id}/{subcarpeta}/{identificador}"

    @classmethod
    async def drenar_cua_transit_empresa(
        cls, db: Optional[AsyncSession], empresa_id: str | uuid.UUID
    ) -> Dict[str, int]:
        """Envia tots els paquets xifrats `SVENC1:` pel túnel WSS de l'empresa i els purga (`unlink`) de Hetzner."""
        emp_dir = (cls._get_transit_queue_dir() / str(empresa_id)).resolve()
        if not emp_dir.exists():
            return {"enviats": 0, "pendents": 0}

        target_key = empresa_target_key(empresa_id)
        if not await vault_tunnel_broker.is_online(target_key):
            pendents_actuals = len(list(emp_dir.glob("*.meta.json")))
            return {"enviats": 0, "pendents": pendents_actuals}

        enviats = 0
        pendents = 0
        for meta_file in sorted(emp_dir.glob("*.meta.json")):
            bin_file = emp_dir / meta_file.name.replace(".meta.json", ".bin")
            if not bin_file.exists():
                meta_file.unlink(missing_ok=True)
                continue
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            raw_bytes = cls._decrypt_transit_payload(empresa_id, bin_file.read_bytes())
            try:
                if meta["tipus"] == "JSON":
                    content_obj = json.loads(raw_bytes.decode("utf-8"))
                    await vault_tunnel_broker.json_put(
                        target_key,
                        subcarpeta=str(meta["subcarpeta"]),
                        item_id=str(meta["identificador"]),
                        content=content_obj if isinstance(content_obj, dict) else {"value": content_obj},
                        timeout=15.0,
                    )
                else:
                    await vault_tunnel_broker.file_put(
                        target_key,
                        subcarpeta=str(meta["subcarpeta"]),
                        filename=str(meta["identificador"]),
                        content_bytes=raw_bytes,
                        content_type=str(meta.get("content_type") or "application/octet-stream"),
                        timeout=30.0,
                    )
                # Auto-purga immediata al servidor Hetzner (Zero-Storage)
                bin_file.unlink(missing_ok=True)
                meta_file.unlink(missing_ok=True)
                enviats += 1
            except (VaultTunnelOfflineError, VaultTunnelTimeoutError) as exc:
                logger.warning(
                    "Túnel WSS caigut durant drenatge de trànsit per %s: %s", empresa_id, exc
                )
                pendents += 1
                break
            except Exception as exc:
                logger.warning(
                    "Rebutjat drenatge de trànsit per %s (%s): %s",
                    empresa_id,
                    meta.get("identificador"),
                    exc,
                )
                pendents += 1

        if emp_dir.exists() and not any(emp_dir.iterdir()):
            try:
                emp_dir.rmdir()
            except OSError:
                pass
        return {"enviats": enviats, "pendents": pendents}

    @classmethod
    async def drenar_totes_cues_transit(cls, db: AsyncSession) -> Dict[str, int]:
        """Recorre totes les empreses amb paquets pendents en cua de trànsit i els sincronitza via WSS."""
        root = cls._get_transit_queue_dir()
        if not root.exists():
            return {"empreses": 0, "enviats": 0, "pendents": 0}
        total_empreses = 0
        total_enviats = 0
        total_pendents = 0
        for emp_dir in sorted(root.iterdir()):
            if not emp_dir.is_dir():
                continue
            try:
                uuid.UUID(emp_dir.name)
            except ValueError:
                continue
            total_empreses += 1
            res = await cls.drenar_cua_transit_empresa(db, emp_dir.name)
            total_enviats += res.get("enviats", 0)
            total_pendents += res.get("pendents", 0)
        return {"empreses": total_empreses, "enviats": total_enviats, "pendents": total_pendents}

    @classmethod
    async def verificar_roundtrip_wss(cls, empresa_id: str | uuid.UUID) -> Dict[str, Any]:
        """Comprova salut en viu, models LLM locals i prova real R/W/D sobre el túnel WSS de l'empresa."""
        target_key = empresa_target_key(empresa_id)
        cua_pendent = cls.comptar_cua_transit_empresa(empresa_id)
        if not await vault_tunnel_broker.is_online(target_key):
            return {
                "ok": False,
                "motiu": "TUNEL_OFFLINE",
                "codi_http": 503,
                "cua_transit_pendent": cua_pendent,
                "missatge": (
                    "L'ordinador dedicat de l'empresa no està connectat al túnel WSS de Sevalor. "
                    "Comprova que l'agent sobirà estigui encès."
                ),
            }

        probe_id = f"_healthcheck_{uuid.uuid4().hex[:8]}"
        sub_cfg = MAPA_CARPETES_CLIENT["configuracio"]
        try:
            health_json = await vault_tunnel_broker.health(target_key, timeout=8.0)
            await vault_tunnel_broker.json_put(
                target_key,
                subcarpeta=sub_cfg,
                item_id=probe_id,
                content={"probe": True, "ts": datetime.now(timezone.utc).isoformat()},
                timeout=8.0,
            )
            items = await vault_tunnel_broker.json_get_list(target_key, sub_cfg, timeout=8.0)
            await vault_tunnel_broker.json_delete(target_key, sub_cfg, probe_id, timeout=8.0)
            readable = isinstance(items, list)
            if not readable:
                return {
                    "ok": False,
                    "motiu": "ERROR_LECTURA_DISC",
                    "codi_http": 502,
                    "cua_transit_pendent": cua_pendent,
                    "missatge": "S'ha pogut escriure però no llegir el fitxer de prova al disc del client.",
                }
            models = health_json.get("models") if isinstance(health_json.get("models"), list) else []
            ia_proxy_ok = bool(health_json.get("llm_online", False))
            if not ia_proxy_ok:
                try:
                    m_res = await vault_tunnel_broker.call_llm_models(target_key, timeout=5.0)
                    raw_models = m_res.get("data") if isinstance(m_res, dict) else []
                    if isinstance(raw_models, list):
                        models = [
                            str(m.get("id") or m.get("name"))
                            for m in raw_models
                            if isinstance(m, dict) and (m.get("id") or m.get("name"))
                        ]
                        ia_proxy_ok = True
                except Exception:
                    ia_proxy_ok = False
            return {
                "ok": True,
                "codi_http": 200,
                "latencia_ms": health_json.get("latencia_ms"),
                "ia_proxy_ok": ia_proxy_ok,
                "models": models,
                "vault_root": health_json.get("vault_root"),
                "disc_a_lliure_gb": health_json.get("disc_a_lliure_gb"),
                "disc_b_lliure_gb": health_json.get("disc_b_lliure_gb"),
                "carpetes_count": health_json.get("carpetes_count", 38),
                "agent_version": health_json.get("agent_version"),
                "cua_transit_pendent": cua_pendent,
            }
        except VaultTunnelOfflineError:
            return {
                "ok": False,
                "motiu": "TUNEL_OFFLINE",
                "codi_http": 503,
                "cua_transit_pendent": cua_pendent,
                "missatge": "El túnel WSS de l'empresa s'ha desconnectat durant la verificació.",
            }
        except VaultTunnelTimeoutError:
            return {
                "ok": False,
                "motiu": "TIMEOUT",
                "codi_http": 504,
                "cua_transit_pendent": cua_pendent,
                "missatge": "Temps d'espera esgotat verificant el disc dur de l'empresa pel túnel WSS.",
            }
        except VaultTunnelError as exc:
            return {
                "ok": False,
                "motiu": exc.code,
                "codi_http": exc.status_code,
                "cua_transit_pendent": cua_pendent,
                "missatge": exc.detail,
            }

    @classmethod
    def _sign_meta(
        cls,
        empresa_id: str | uuid.UUID,
        categoria: str,
        subcarpeta: str,
        item_id: str,
    ) -> str:
        """Signatura HMAC-SHA256 anti-barreges per verificar pertinença física al tenant."""
        key = settings.SECRET_KEY.encode("utf-8")
        msg = f"{str(empresa_id)}|{categoria}|{subcarpeta}|{item_id}".encode("utf-8")
        return hmac.new(key, msg, hashlib.sha256).hexdigest()

    @classmethod
    def _filtrar_entitats_verificades(
        cls,
        empresa_id: str | uuid.UUID,
        categoria: str,
        subcarpeta: str,
        registres: Any,
    ) -> List[Dict[str, Any]]:
        """
        Escut Anti-Barreges: rebutja qualsevol fitxa JSON sense `_sovereign_meta`,
        amb `empresa_id` diferent o amb `hmac_tenant` manipulada o absent.
        """
        if not isinstance(registres, list):
            return []
        emp_str = str(empresa_id)
        verificades: List[Dict[str, Any]] = []
        for reg in registres:
            if not isinstance(reg, dict):
                continue
            meta = reg.get("_sovereign_meta")
            if not isinstance(meta, dict):
                logger.warning(
                    "Escut Anti-Barreges: registre sense _sovereign_meta rebutjat (empresa=%s, cat=%s).",
                    emp_str,
                    categoria,
                )
                continue
            if str(meta.get("empresa_id", "")) != emp_str:
                logger.warning(
                    "Escut Anti-Barreges: possible barreja cross-tenant rebutjada (esperat=%s, trobat=%s, cat=%s).",
                    emp_str,
                    meta.get("empresa_id"),
                    categoria,
                )
                continue
            meta_sub = meta.get("subcarpeta")
            if meta_sub and meta_sub != subcarpeta:
                logger.warning(
                    "Escut Anti-Barreges: subcarpeta discordant rebutjada (esperat=%s, trobat=%s).",
                    subcarpeta,
                    meta_sub,
                )
                continue
            sig = meta.get("hmac_tenant")
            item_id = meta.get("item_id")
            meta_cat = str(meta.get("categoria") or categoria)
            if not isinstance(sig, str) or not sig or not isinstance(item_id, str) or not item_id:
                logger.warning(
                    "Escut Anti-Barreges: signatura HMAC absent o incompleta rebutjada (empresa=%s, cat=%s).",
                    emp_str,
                    categoria,
                )
                continue
            expected_sig = cls._sign_meta(emp_str, meta_cat, subcarpeta, item_id)
            if not hmac.compare_digest(sig, expected_sig):
                logger.warning(
                    "Escut Anti-Barreges: signatura HMAC invàlida rebutjada (empresa=%s, cat=%s, item=%s).",
                    emp_str,
                    categoria,
                    item_id,
                )
                continue
            verificades.append(reg)
        return verificades

    @classmethod
    async def desar_entitat_json(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        categoria: str,
        item_id: str | uuid.UUID,
        dades: Dict[str, Any],
        timeout: float = 12.0,
    ) -> str:
        """
        Escriu el registre estructurat JSON directament dins la carpeta corresponent
        del disc dur del client (ex: 01_clients/fitxes/<id>.json).
        """
        subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
        id_net = sanititzar_nom(str(item_id))
        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)

        hmac_sig = cls._sign_meta(empresa_id, categoria, subcarpeta, id_net)
        payload_complet = {
            **dades,
            "_sovereign_meta": {
                "empresa_id": str(empresa_id),
                "categoria": categoria,
                "subcarpeta": subcarpeta,
                "item_id": id_net,
                "hmac_tenant": hmac_sig,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        if mode == "LOCAL_FS":
            folder = (Path(base_target) / subcarpeta).resolve()
            if not str(folder).startswith(str(Path(base_target).resolve())):
                raise HTTPException(status_code=400, detail="Ruta de disc invàlida.")
            folder.mkdir(parents=True, exist_ok=True)
            file_path = folder / f"{id_net}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload_complet, f, ensure_ascii=False, indent=2, default=str)
            return str(file_path)

        payload_bytes = json.dumps(payload_complet, ensure_ascii=False, indent=2, default=str).encode("utf-8")

        if mode == "OFFLINE_TRANSIT":
            return cls._encuar_paquet_transit(
                empresa_id=empresa_id,
                tipus="JSON",
                subcarpeta=subcarpeta,
                identificador=id_net,
                payload_bytes=payload_bytes,
                content_type="application/json",
            )

        # Mode WSS_TUNNEL (Túnel Invers Natiu WSS cap al PC de l'empresa)
        try:
            await vault_tunnel_broker.json_put(
                base_target,
                subcarpeta=subcarpeta,
                item_id=id_net,
                content=payload_complet,
                timeout=timeout,
            )
            return f"vault://{subcarpeta}/{id_net}.json"
        except (VaultTunnelOfflineError, VaultTunnelTimeoutError) as exc:
            logger.warning(
                "Túnel WSS de %s desconnectat (%s). Encuant a cua de trànsit xifrada SVENC1:...",
                empresa_id,
                exc,
            )
            transit_ref = cls._encuar_paquet_transit(
                empresa_id=empresa_id,
                tipus="JSON",
                subcarpeta=subcarpeta,
                identificador=id_net,
                payload_bytes=payload_bytes,
                content_type="application/json",
            )
            try:
                from app.workers.tasks import drenar_cua_transit_task

                drenar_cua_transit_task.delay(str(empresa_id))
            except Exception:
                pass
            return transit_ref
        except VaultTunnelRemoteError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @classmethod
    async def esborrar_entitat_json(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        categoria: str,
        item_id: str | uuid.UUID,
    ) -> bool:
        """Esborra una fitxa JSON del disc dur exclusiu de l'empresa via WSS."""
        subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
        id_net = sanititzar_nom(str(item_id))
        mode, base_target, _ = await cls.resoldre_desti_disc_empresa(db, empresa_id)

        if mode == "LOCAL_FS":
            folder = (Path(base_target) / subcarpeta).resolve()
            fp = (folder / f"{id_net}.json").resolve()
            if fp.is_file() and fp.is_relative_to(folder):
                fp.unlink()
                return True
            return False

        if mode == "OFFLINE_TRANSIT":
            return False

        try:
            return await vault_tunnel_broker.json_delete(
                base_target, subcarpeta=subcarpeta, item_id=id_net, timeout=10.0
            )
        except VaultTunnelError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @classmethod
    async def llegir_entitats_json(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        categoria: str,
        timeout: float = 12.0,
    ) -> List[Dict[str, Any]]:
        """Llegeix totes les fitxes JSON verificades (HMAC + tenant) d'una carpeta del disc dur del client."""
        subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)

        if mode == "LOCAL_FS":
            folder = (Path(base_target) / subcarpeta).resolve()
            if not folder.is_relative_to(Path(base_target).resolve()) or not folder.exists():
                return []
            registres: List[Dict[str, Any]] = []
            for fp in sorted(folder.glob("*.json"), key=os.path.getmtime, reverse=True):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        registres.append(json.load(f))
                except Exception:
                    continue
            return cls._filtrar_entitats_verificades(empresa_id, categoria, subcarpeta, registres)

        if mode == "OFFLINE_TRANSIT":
            emp_dir = (cls._get_transit_queue_dir() / str(empresa_id)).resolve()
            if not emp_dir.exists():
                return []
            by_id: Dict[str, Dict[str, Any]] = {}
            for meta_file in sorted(emp_dir.glob("*.meta.json")):
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    if meta.get("tipus") != "JSON" or meta.get("subcarpeta") != subcarpeta:
                        continue
                    bin_file = emp_dir / meta_file.name.replace(".meta.json", ".bin")
                    if not bin_file.is_file():
                        continue
                    raw = cls._decrypt_transit_payload(empresa_id, bin_file.read_bytes())
                    parsed = json.loads(raw.decode("utf-8"))
                    if isinstance(parsed, dict):
                        by_id[str(meta.get("identificador") or meta_file.name)] = parsed
                except Exception:
                    continue
            return cls._filtrar_entitats_verificades(
                empresa_id, categoria, subcarpeta, list(reversed(list(by_id.values())))
            )

        # Mode WSS_TUNNEL
        try:
            raw_data = await vault_tunnel_broker.json_get_list(
                base_target, subcarpeta=subcarpeta, timeout=timeout
            )
            return cls._filtrar_entitats_verificades(empresa_id, categoria, subcarpeta, raw_data)
        except (VaultTunnelOfflineError, VaultTunnelTimeoutError) as exc:
            logger.warning("Túnel WSS offline llegint entitats per empresa=%s: %s", empresa_id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_EMPRESA_OFFLINE",
                    "message": "El disc dur dedicat de l'empresa no està connectat al túnel WSS.",
                },
            ) from exc
        except VaultTunnelRemoteError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @classmethod
    async def llegir_text_fitxer(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        categoria: str,
        nom_fitxer: str,
    ) -> Optional[str]:
        """Llegeix de forma segura un fitxer de text (p.ex. system_prompt.txt, protocols .md) del disc dur del client."""
        subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
        try:
            nom_net = sanititzar_nom(nom_fitxer)
        except ValueError:
            return None

        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)
        if mode == "LOCAL_FS":
            base_resolved = Path(base_target).resolve()
            target = (base_resolved / subcarpeta / nom_net).resolve()
            if not target.is_relative_to(base_resolved) or not target.is_file():
                return None
            try:
                return target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None

        if mode == "OFFLINE_TRANSIT":
            transit_bin = cls._trobar_fitxer_transit(
                empresa_id, f"transit://{empresa_id}/{subcarpeta}/{nom_net}"
            )
            if transit_bin and transit_bin.is_file():
                try:
                    raw = cls._decrypt_transit_payload(empresa_id, transit_bin.read_bytes())
                    return raw.decode("utf-8", errors="replace")
                except Exception:
                    return None
            return None

        try:
            raw_bytes, _ = await vault_tunnel_broker.file_get(
                base_target, rel_path=f"{subcarpeta}/{nom_net}", timeout=10.0
            )
            return raw_bytes.decode("utf-8", errors="replace")
        except VaultTunnelRemoteError as exc:
            if exc.status_code == 404 or exc.code == "NOT_FOUND":
                return None
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        except (VaultTunnelOfflineError, VaultTunnelTimeoutError) as exc:
            logger.warning("Túnel WSS offline llegint fitxer per empresa=%s: %s", empresa_id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_EMPRESA_OFFLINE",
                    "motiu": "TUNEL_OFFLINE",
                    "message": "El disc dur dedicat de l'empresa no està connectat al túnel WSS.",
                },
            ) from exc
        except VaultTunnelError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @classmethod
    async def pujar_fitxer_binari(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        categoria: str,
        nom_fitxer: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Escriu un fitxer binari exclusivament al disc dur del client (LOCAL_FS muntat o HTTP_VAULT).
        Si l'Agent HTTP del client no respon, l'encua a TRANSIT_QUEUE_DIR per auto-purgar-lo en lliurar-lo.
        """
        subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
        nom_net = sanititzar_nom(nom_fitxer)
        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)

        if mode == "LOCAL_FS":
            folder = (Path(base_target) / subcarpeta).resolve()
            if not str(folder).startswith(str(Path(base_target).resolve())):
                raise HTTPException(status_code=400, detail="Ruta de disc invàlida.")
            folder.mkdir(parents=True, exist_ok=True)
            dest_file = folder / nom_net
            dest_file.write_bytes(content)
            return str(dest_file)

        if mode == "OFFLINE_TRANSIT":
            return cls._encuar_paquet_transit(
                empresa_id=empresa_id,
                tipus="BINARY",
                subcarpeta=subcarpeta,
                identificador=nom_net,
                payload_bytes=content,
                content_type=content_type,
            )

        # Mode WSS_TUNNEL (Agent Sobirà WSS al PC del client)
        try:
            await vault_tunnel_broker.file_put(
                base_target,
                subcarpeta=subcarpeta,
                filename=nom_net,
                content_bytes=content,
                content_type=content_type,
                timeout=30.0,
            )
            return f"vault://{subcarpeta}/{nom_net}"
        except (VaultTunnelOfflineError, VaultTunnelTimeoutError) as exc:
            logger.warning(
                "Túnel WSS del client %s desconnectat (%s). Encuant fitxer %s a cua de trànsit SVENC1:...",
                empresa_id,
                exc,
                nom_net,
            )
            transit_ref = cls._encuar_paquet_transit(
                empresa_id=empresa_id,
                tipus="BINARY",
                subcarpeta=subcarpeta,
                identificador=nom_net,
                payload_bytes=content,
                content_type=content_type,
            )
            try:
                from app.workers.tasks import drenar_cua_transit_task

                drenar_cua_transit_task.delay(str(empresa_id))
            except Exception:
                pass
            return transit_ref
        except VaultTunnelRemoteError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @classmethod
    def _trobar_fitxer_transit(
        cls, empresa_id: str | uuid.UUID, fitxer_path: str
    ) -> Optional[Path]:
        raw_clean = fitxer_path.replace("file://", "").strip()
        if not (raw_clean.startswith("transit://") or "transit" in raw_clean):
            return None
        emp_str = str(empresa_id)
        ident = raw_clean.replace("transit://", "").split("/")[-1]
        emp_dir = (cls._get_transit_queue_dir() / emp_str).resolve()
        if not emp_dir.exists():
            return None
        for meta_file in emp_dir.glob("*.meta.json"):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                if meta.get("identificador") == ident or meta.get("nom_desti") == ident:
                    bin_file = emp_dir / meta_file.name.replace(".meta.json", ".bin")
                    if bin_file.is_file():
                        return bin_file.resolve()
            except Exception:
                continue
        for b in emp_dir.glob("*.bin"):
            if ident in b.name:
                return b.resolve()
        return None

    @classmethod
    async def obtenir_bytes_fitxer(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        fitxer_path: str,
    ) -> Tuple[bytes, str]:
        """
        Retorna (content_bytes, filename) tant si el plànol és a LOCAL_FS, a transit:// com a vault:// (HTTP_VAULT).
        Necessari perquè /render pugui rasteritzar PDFs/imatges sense guardar res permanent a Hetzner.
        """
        transit_bin = cls._trobar_fitxer_transit(empresa_id, fitxer_path)
        if transit_bin and transit_bin.is_file():
            filename = os.path.basename(fitxer_path.replace("transit://", ""))
            return cls._decrypt_transit_payload(empresa_id, transit_bin.read_bytes()), filename

        real_path = await cls.resoldre_fitxer_real_path(db, empresa_id, fitxer_path)
        if real_path and real_path.is_file():
            return real_path.read_bytes(), real_path.name

        mode, base_target, _ = await cls.resoldre_desti_disc_empresa(db, empresa_id)
        if mode == "WSS_TUNNEL":
            rel_path = fitxer_path.replace("vault://", "").replace("transit://", "").lstrip("/")
            if rel_path.startswith(str(empresa_id) + "/"):
                rel_path = rel_path[len(str(empresa_id)) + 1 :]
            try:
                return await vault_tunnel_broker.file_get(base_target, rel_path=rel_path, timeout=30.0)
            except VaultTunnelRemoteError as exc:
                if exc.status_code == 404:
                    raise HTTPException(
                        status_code=404, detail="Fitxer no trobat al disc dur de l'empresa."
                    ) from exc
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
            except (VaultTunnelOfflineError, VaultTunnelTimeoutError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "NODE_EMPRESA_OFFLINE",
                        "message": "El disc dur dedicat de l'empresa no està connectat al túnel WSS.",
                    },
                ) from exc

        raise HTTPException(status_code=404, detail="Fitxer no trobat al disc dur de l'empresa.")

    @classmethod
    async def existeix_fitxer_categoria(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        categoria: str,
        nom_fitxer: str,
    ) -> bool:
        """Comprova si un fitxer binari existeix dins la carpeta corresponent del disc dur del client."""
        subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
        try:
            nom_net = sanititzar_nom(nom_fitxer)
        except ValueError:
            return False

        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)

        if mode == "LOCAL_FS":
            target = (Path(base_target) / subcarpeta / nom_net).resolve()
            return target.is_file()

        if mode == "OFFLINE_TRANSIT":
            found = cls._trobar_fitxer_transit(
                empresa_id, f"transit://{empresa_id}/{subcarpeta}/{nom_net}"
            )
            return bool(found and found.is_file())

        try:
            await vault_tunnel_broker.file_get(
                base_target, rel_path=f"{subcarpeta}/{nom_net}", timeout=8.0
            )
            return True
        except VaultTunnelError:
            return False

    @classmethod
    async def resoldre_fitxer_real_path(
        cls,
        db: Optional[AsyncSession],
        empresa_id: str | uuid.UUID,
        fitxer_path: Optional[str],
    ) -> Optional[Path]:
        """
        Localitza de forma exhaustiva i resilient la ruta física real d'un fitxer al disc dur de l'empresa.
        Cobreix rutes directes, cues de trànsit transit:// i rutes locals de l'empresa.
        """
        if not fitxer_path:
            return None

        # 1. Ruta directa al disc si ja és vàlida
        raw_clean = fitxer_path.replace("file://", "").strip()
        direct_path = Path(raw_clean)
        if direct_path.is_file():
            return direct_path.resolve()

        emp_str = str(empresa_id)
        filename = os.path.basename(raw_clean.replace("vault://", "").replace("transit://", ""))
        rel_path = raw_clean.replace("vault://", "").lstrip("/")

        # 2. Cua de trànsit temporal transit://
        if raw_clean.startswith("transit://") or "transit" in raw_clean:
            found_transit = cls._trobar_fitxer_transit(emp_str, raw_clean)
            if found_transit is not None:
                return found_transit

        # 3. Només resol camí físic local si l'empresa té un punt de muntatge LOCAL_FS explícit (mai Hetzner /tmp ni /data)
        mode, base_target, _ = await cls.resoldre_desti_disc_empresa(db, empresa_id)
        if mode != "LOCAL_FS":
            return None

        candidate_roots = [Path(base_target)]

        for root in candidate_roots:
            if not root or not root.exists():
                continue
            candidates = [
                root / rel_path,
                root / "05_planols" / "arxius_base" / filename,
                root / "05_planols" / filename,
                root / filename,
            ]
            for cand in candidates:
                if cand.is_file():
                    return cand.resolve()

            # Recerca superficial si la carpeta 05_planols existeix
            planols_dir = root / "05_planols"
            if planols_dir.is_dir():
                found = list(planols_dir.glob(f"**/{filename}"))
                if found and found[0].is_file():
                    return found[0].resolve()

        return None

    @classmethod
    async def servir_fitxer(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        fitxer_path: str,
        media_type: str = "application/octet-stream",
        disposition: str = "inline",
    ) -> Response:
        """Serveix un fitxer des del disc dur del client cap a la PWA (Streaming Zero-Copy)."""
        transit_bin = cls._trobar_fitxer_transit(empresa_id, fitxer_path)
        if transit_bin and transit_bin.is_file():
            raw_bytes, fname = await cls.obtenir_bytes_fitxer(db, empresa_id, fitxer_path)
            return Response(
                content=raw_bytes,
                media_type=media_type,
                headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
            )

        real_path = await cls.resoldre_fitxer_real_path(db, empresa_id, fitxer_path)
        if real_path and real_path.is_file():
            return FileResponse(
                path=str(real_path),
                filename=real_path.name,
                media_type=media_type,
                content_disposition_type=disposition,
            )

        # Si no s'ha trobat localment (o el paquet transit:// ja ha estat drenat cap al PC via WSS)
        if fitxer_path.startswith("vault://") or fitxer_path.startswith("transit://"):
            mode, base_target, _ = await cls.resoldre_desti_disc_empresa(db, empresa_id)
            if mode == "WSS_TUNNEL":
                rel_path = fitxer_path.replace("vault://", "").replace("transit://", "").lstrip("/")
                if rel_path.startswith(str(empresa_id) + "/"):
                    rel_path = rel_path[len(str(empresa_id)) + 1 :]
                try:
                    raw_bytes, filename = await vault_tunnel_broker.file_get(
                        base_target, rel_path=rel_path, timeout=30.0
                    )
                except VaultTunnelRemoteError as exc:
                    raise HTTPException(
                        status_code=404 if exc.status_code == 404 else exc.status_code,
                        detail="Fitxer no trobat al disc del client.",
                    ) from exc
                except (VaultTunnelOfflineError, VaultTunnelTimeoutError) as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={
                            "code": "NODE_EMPRESA_OFFLINE",
                            "message": "El disc dur dedicat de l'empresa no està connectat al túnel WSS.",
                        },
                    ) from exc
                return Response(
                    content=raw_bytes,
                    media_type=media_type,
                    headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
                )

        raise HTTPException(
            status_code=404, detail="Fitxer no trobat al disc dur de l'empresa."
        )

    @classmethod
    async def inicialitzar_dades_onboarding_empresa(
        cls,
        db: AsyncSession,
        empresa: Empresa,
        boss: Optional[Any] = None,
        *,
        dades_empresa_reals: Optional[Dict[str, Any]] = None,
        dades_boss_reals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Bolca la fitxa d'identitat camaleònica i la fitxa del Boss al disc del client."""
        rutes: Dict[str, str] = {}
        reals_emp = dades_empresa_reals or {}
        dades_empresa: Dict[str, Any] = {
            "id": str(empresa.id),
            "nom": reals_emp.get("nom", empresa.nom),
            "nif": reals_emp.get("nif", empresa.nif),
            "adreca": reals_emp.get("adreca", empresa.adreca),
            "subdomini": reals_emp.get("subdomini", empresa.subdomini),
            "domini_custom": reals_emp.get("domini_custom", empresa.domini_custom),
            "vertical": reals_emp.get("vertical", empresa.vertical),
            "pla_subscripcio": reals_emp.get("pla_subscripcio", empresa.pla_subscripcio),
            "primari_hsl": reals_emp.get("primari_hsl", empresa.primari_hsl),
            "secundari_hsl": reals_emp.get("secundari_hsl", empresa.secundari_hsl),
            "accent_hsl": reals_emp.get("accent_hsl", empresa.accent_hsl),
            "logotip_path": reals_emp.get("logotip_path", empresa.logotip_path),
            "node_ia_url": reals_emp.get("node_ia_url", empresa.node_ia_url),
            "disc_dur_url": reals_emp.get("disc_dur_url", getattr(empresa, "disc_dur_url", None)),
            "vault_token": reals_emp.get("vault_token", getattr(empresa, "vault_token", None)),
            "node_ia_actiu": bool(reals_emp.get("node_ia_actiu", getattr(empresa, "node_ia_actiu", False))),
            "feature_copilot_ia": bool(
                reals_emp.get("feature_copilot_ia", getattr(empresa, "feature_copilot_ia", False))
            ),
        }
        if "magatzem_families_default" in reals_emp:
            dades_empresa["magatzem_families_default"] = reals_emp["magatzem_families_default"]
        rutes["empresa_json"] = await cls.desar_entitat_json(
            db=db,
            empresa_id=empresa.id,
            categoria="configuracio",
            item_id="empresa",
            dades=dades_empresa,
        )
        if boss is not None or dades_boss_reals is not None:
            reals_boss = dades_boss_reals or {}
            boss_id_str = str(reals_boss.get("id") or (boss.id if boss is not None else uuid.uuid4()))
            boss_payload: Dict[str, Any] = {
                "id": boss_id_str,
                "nom": reals_boss.get("nom", getattr(boss, "nom", "Usuari")),
                "cognoms": reals_boss.get("cognoms", getattr(boss, "cognoms", "")),
                "nif": reals_boss.get("nif", getattr(boss, "nif", "")),
                "email": reals_boss.get("email", getattr(boss, "email", None)),
                "telefon": reals_boss.get("telefon", getattr(boss, "telefon", None)),
                "rol": reals_boss.get("rol", getattr(boss, "rol", "BOSS")),
            }
            rutes["boss_json"] = await cls.desar_entitat_json(
                db=db,
                empresa_id=empresa.id,
                categoria="operaris",
                item_id=boss_id_str,
                dades=boss_payload,
            )
            try:
                await cls.desar_entitat_json(
                    db=db,
                    empresa_id=empresa.id,
                    categoria="configuracio",
                    item_id="boss",
                    dades=boss_payload,
                )
            except Exception:
                pass
        return rutes

    @classmethod
    async def sincronitzar_vincle_client_vault_empresa(
        cls,
        db: AsyncSession,
        empresa: Empresa,
        *,
        dades_extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Persistència Sobirana Doble (Superadmin Disk + Empresa Exclusive Disk):
        1. Actualitza la fitxa B2B al Disc Dur de Superadmin (01_tenants_b2b/fitxes_empreses/<id>.json)
           amb node_ia_url, disc_dur_url, vault_token, node_ia_actiu i feature_copilot_ia.
        2. Escriu empresa.json a la carpeta 11_configuracio_i_backups
           del Disc Dur Exclusiu de l'Empresa i drena la cua de trànsit pendent.
        """
        emp_id_str = str(empresa.id)
        extra = dades_extra or {}
        fitxa_existent = await cls.recuperar_fitxa_superadmin_empresa(empresa.id)

        nom_real = str(
            extra.get("nom")
            or extra.get("rao_social")
            or fitxa_existent.get("rao_social")
            or fitxa_existent.get("nom")
            or empresa.nom
        )
        nif_real = str(extra.get("nif") or fitxa_existent.get("nif") or empresa.nif)
        adreca_real = extra.get("adreca", fitxa_existent.get("adreca", empresa.adreca))

        fitxa_superadmin: Dict[str, Any] = {
            **fitxa_existent,
            "id": emp_id_str,
            "empresa_id": emp_id_str,
            "nom": nom_real,
            "rao_social": nom_real,
            "nif": nif_real,
            "adreca": adreca_real,
            "subdomini": empresa.subdomini,
            "domini_custom": empresa.domini_custom,
            "vertical": empresa.vertical,
            "pla_subscripcio": empresa.pla_subscripcio,
            "estat_pagament": empresa.estat_pagament,
            "node_ia_url": empresa.node_ia_url,
            "disc_dur_url": getattr(empresa, "disc_dur_url", None),
            "vault_token": getattr(empresa, "vault_token", None),
            "node_ia_actiu": bool(getattr(empresa, "node_ia_actiu", False)),
            "feature_copilot_ia": bool(getattr(empresa, "feature_copilot_ia", False)),
            "feature_flota": bool(getattr(empresa, "feature_flota", True)),
            "feature_planols": bool(getattr(empresa, "feature_planols", False)),
            "feature_telegram": bool(getattr(empresa, "feature_telegram", True)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        fitxa_superadmin.pop("agent_prompt_system", None)
        if "created_at" not in fitxa_superadmin:
            fitxa_superadmin["created_at"] = datetime.now(timezone.utc).isoformat()

        superadmin_path: Optional[str] = None
        try:
            superadmin_path = await SuperadminStorageGateway.desar_entitat_json(
                "tenants_fitxes", emp_id_str, fitxa_superadmin
            )
        except Exception as exc:
            logger.warning(
                "No s'ha pogut sincronitzar fitxa de %s al Disc de Superadmin: %s",
                emp_id_str,
                exc,
            )

        empresa_rutes: Dict[str, str] = {}
        try:
            empresa_rutes = await cls.inicialitzar_dades_onboarding_empresa(
                db=db,
                empresa=empresa,
                dades_empresa_reals={
                    "nom": nom_real,
                    "nif": nif_real,
                    "adreca": adreca_real,
                    "node_ia_url": empresa.node_ia_url,
                    "disc_dur_url": getattr(empresa, "disc_dur_url", None),
                    "vault_token": getattr(empresa, "vault_token", None),
                    "node_ia_actiu": bool(getattr(empresa, "node_ia_actiu", False)),
                    "feature_copilot_ia": bool(getattr(empresa, "feature_copilot_ia", False)),
                },
            )
            await cls.drenar_cua_transit_empresa(db, empresa.id)
        except Exception as exc:
            logger.warning(
                "No s'ha pogut sincronitzar empresa.json al disc exclusiu de %s: %s",
                emp_id_str,
                exc,
            )

        return {
            "superadmin_fitxa": superadmin_path,
            "empresa_files": empresa_rutes,
        }

    @classmethod
    async def reanomenar_fitxer_binari(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        old_path: Optional[str],
        new_filename: str,
        categoria: str = "tiquets_despesa",
        content_type: str = "image/webp",
    ) -> str:
        """
        Reanomena de forma segura un fitxer binari al disc sobirà del tenant sense sortir del seu root.
        Suporta LOCAL_FS, cua transit:// i HTTP_VAULT.
        """
        nom_net = sanititzar_nom(new_filename)
        if not old_path:
            raise HTTPException(status_code=400, detail="Ruta d'origen del fitxer buida.")

        transit_bin = cls._trobar_fitxer_transit(empresa_id, old_path)
        if transit_bin and transit_bin.is_file():
            raw_bytes = cls._decrypt_transit_payload(empresa_id, transit_bin.read_bytes())
            nova_ruta = await cls.pujar_fitxer_binari(
                db=db,
                empresa_id=empresa_id,
                categoria=categoria,
                nom_fitxer=nom_net,
                content=raw_bytes,
                content_type=content_type,
            )
            if str(transit_bin.resolve()) != str(nova_ruta) and transit_bin.exists():
                transit_bin.unlink(missing_ok=True)
            return nova_ruta

        real_old = await cls.resoldre_fitxer_real_path(db, empresa_id, old_path)
        mode, base_target, _ = await cls.resoldre_desti_disc_empresa(db, empresa_id)

        if real_old and real_old.is_file() and mode == "LOCAL_FS":
            subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
            base_resolved = Path(base_target).resolve()
            dest_folder = (base_resolved / subcarpeta).resolve()
            if not str(dest_folder).startswith(str(base_resolved)):
                raise HTTPException(status_code=400, detail="Ruta de destí fora del disc del tenant.")
            dest_folder.mkdir(parents=True, exist_ok=True)
            dest_file = (dest_folder / nom_net).resolve()
            if not str(dest_file).startswith(str(dest_folder)):
                raise HTTPException(status_code=400, detail="Nom de fitxer invàlid.")
            if real_old.resolve() != dest_file:
                real_old.replace(dest_file)
            return str(dest_file)

        if mode == "WSS_TUNNEL" and old_path.startswith("vault://"):
            subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
            old_rel = old_path.replace("vault://", "").lstrip("/")
            try:
                res = await vault_tunnel_broker.file_rename(
                    base_target,
                    old_rel_path=old_rel,
                    new_subcarpeta=subcarpeta,
                    new_filename=nom_net,
                    timeout=15.0,
                )
                return f"vault://{res.get('rel_path') or f'{subcarpeta}/{nom_net}'}"
            except VaultTunnelError:
                pass

        raw_bytes, _ = await cls.obtenir_bytes_fitxer(db, empresa_id, old_path)
        return await cls.pujar_fitxer_binari(
            db=db,
            empresa_id=empresa_id,
            categoria=categoria,
            nom_fitxer=nom_net,
            content=raw_bytes,
            content_type=content_type,
        )

    @classmethod
    async def esborrar_fitxer_binari(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        fitxer_path: str,
    ) -> bool:
        """Elimina un fitxer binari del disc dur del client (WSS_TUNNEL o cua transit://)."""
        if not fitxer_path:
            return False
        transit_bin = cls._trobar_fitxer_transit(empresa_id, fitxer_path)
        if transit_bin and transit_bin.is_file():
            meta_file = transit_bin.with_name(transit_bin.name.replace(".bin", ".meta.json"))
            transit_bin.unlink(missing_ok=True)
            meta_file.unlink(missing_ok=True)
            return True

        mode, base_target, _ = await cls.resoldre_desti_disc_empresa(db, empresa_id)
        if mode == "LOCAL_FS":
            real_p = await cls.resoldre_fitxer_real_path(db, empresa_id, fitxer_path)
            if real_p and real_p.is_file() and real_p.is_relative_to(Path(base_target).resolve()):
                real_p.unlink()
                return True
            return False

        if mode == "WSS_TUNNEL":
            rel_path = fitxer_path.replace("vault://", "").replace("transit://", "").lstrip("/")
            if rel_path.startswith(str(empresa_id) + "/"):
                rel_path = rel_path[len(str(empresa_id)) + 1 :]
            try:
                return await vault_tunnel_broker.file_delete(base_target, rel_path=rel_path, timeout=10.0)
            except VaultTunnelError:
                return False
        return False


class SuperadminStorageGateway:
    """Passarel·la exclusiva del propietari SaaS cap al seu disc dur dedicat via Túnel WSS Únic (ADR-001)."""

    MAX_UPLOAD_BYTES = 50 * 1024 * 1024

    @staticmethod
    def _resoldre_carpeta_local(base_target: str, subcarpeta: str) -> Path:
        base_resolved = Path(base_target).resolve()
        folder = (base_resolved / subcarpeta).resolve()
        if not folder.is_relative_to(base_resolved) or folder == base_resolved:
            raise HTTPException(status_code=400, detail="Ruta de carpeta Superadmin invàlida.")
        return folder

    @staticmethod
    async def _resolve_target() -> Tuple[str, str]:
        """Resol el destí del Disc Superadmin: sempre `WSS_TUNNEL` (`superadmin`) en producció."""
        if await vault_tunnel_broker.is_online(SUPERADMIN_TARGET_KEY):
            return ("WSS_TUNNEL", SUPERADMIN_TARGET_KEY)

        # Només en entorn de tests unitaris (TESTING=1 fora de Docker) permet carpeta temporal local
        if os.getenv("TESTING") == "1" and not os.path.exists("/.dockerenv"):
            test_path = os.getenv("SUPERADMIN_VAULT_URL", "").strip()
            if test_path and test_path.startswith("/"):
                return ("LOCAL_FS", str(Path(test_path).resolve()))

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "NODE_SUPERADMIN_OFFLINE",
                "message": "El Disc Dur dedicat de Superadmin no està connectat al túnel WSS de Sevalor.",
            },
        )

    @classmethod
    async def inicialitzar_rutes_superadmin(cls, ruta_personalitzada: Optional[str] = None) -> Dict[str, Any]:
        """Crea les 20 carpetes oficials del Superadmin via túnel WSS `superadmin`."""
        if (
            ruta_personalitzada
            and ruta_personalitzada.startswith("/")
            and os.getenv("TESTING") == "1"
            and not os.path.exists("/.dockerenv")
        ):
            creades = inicialitzar_arbre_carpetes_superadmin(ruta_personalitzada)
            return {
                "mode": "LOCAL_FS",
                "vault_root": str(Path(ruta_personalitzada).resolve()),
                "carpetes_count": len(creades),
                "carpetes": creades,
            }

        mode, base_target = await cls._resolve_target()
        if mode == "LOCAL_FS":
            creades = inicialitzar_arbre_carpetes_superadmin(base_target)
            return {
                "mode": "LOCAL_FS",
                "vault_root": base_target,
                "carpetes_count": len(creades),
                "carpetes": creades,
            }

        try:
            res = await vault_tunnel_broker.init_folders(base_target, timeout=15.0)
            return {"mode": "WSS_TUNNEL", **res}
        except VaultTunnelError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.detail},
            ) from exc

    @classmethod
    async def desar_entitat_json(
        cls,
        categoria: str,
        item_id: str | uuid.UUID,
        dades: Dict[str, Any],
    ) -> str:
        """Desa un registre JSON (CRM, Rascador, Facturació SaaS B2B, Fitxes Tenants) al Disc del Superadmin."""
        subcarpeta = MAPA_CARPETES_SUPERADMIN.get(categoria, categoria)
        id_net = sanititzar_nom(str(item_id))
        mode, base_target = await cls._resolve_target()

        payload_complet: Dict[str, Any] = {
            **dades,
            "_superadmin_meta": {
                "scope": "SUPERADMIN",
                "categoria": categoria,
                "subcarpeta": subcarpeta,
                "item_id": id_net,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        if mode == "LOCAL_FS":
            folder = cls._resoldre_carpeta_local(base_target, subcarpeta)
            folder.mkdir(parents=True, exist_ok=True)
            file_path = (folder / f"{id_net}.json").resolve()
            if not file_path.is_relative_to(folder):
                raise HTTPException(status_code=400, detail="Identificador d'entitat invàlid.")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload_complet, f, ensure_ascii=False, indent=2, default=str)
            return str(file_path)

        try:
            await vault_tunnel_broker.json_put(
                base_target, subcarpeta=subcarpeta, item_id=id_net, content=payload_complet, timeout=10.0
            )
            return f"superadmin-vault://{subcarpeta}/{id_net}.json"
        except VaultTunnelError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.detail},
            ) from exc

    @classmethod
    async def llegir_entitats_json(cls, categoria: str) -> List[Dict[str, Any]]:
        """Llegeix totes les fitxes JSON d'una carpeta del Disc del Superadmin."""
        subcarpeta = MAPA_CARPETES_SUPERADMIN.get(categoria, categoria)
        mode, base_target = await cls._resolve_target()

        if mode == "LOCAL_FS":
            folder = cls._resoldre_carpeta_local(base_target, subcarpeta)
            if not folder.exists() or not folder.is_dir():
                return []
            registres: List[Dict[str, Any]] = []
            for fp in sorted(folder.glob("*.json"), key=os.path.getmtime, reverse=True):
                resolved_fp = fp.resolve()
                if not resolved_fp.is_relative_to(folder) or not resolved_fp.is_file():
                    continue
                try:
                    with open(resolved_fp, "r", encoding="utf-8") as f:
                        registres.append(json.load(f))
                except Exception:
                    continue
            return registres

        try:
            return await vault_tunnel_broker.json_get_list(base_target, subcarpeta=subcarpeta, timeout=12.0)
        except VaultTunnelError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": "NODE_SUPERADMIN_OFFLINE" if exc.status_code == 503 else exc.code, "message": exc.detail},
            ) from exc

    @classmethod
    async def eliminar_entitat_json(cls, categoria: str, item_id: str | uuid.UUID) -> bool:
        """Elimina una fitxa JSON del Disc del Superadmin amb validació estricta de ruta."""
        subcarpeta = MAPA_CARPETES_SUPERADMIN.get(categoria, categoria)
        id_net = sanititzar_nom(str(item_id))
        mode, base_target = await cls._resolve_target()

        if mode == "LOCAL_FS":
            folder = cls._resoldre_carpeta_local(base_target, subcarpeta)
            file_path = (folder / f"{id_net}.json").resolve()
            if file_path.is_file() and file_path.is_relative_to(folder):
                file_path.unlink()
                return True
            return False

        try:
            return await vault_tunnel_broker.json_delete(
                base_target, subcarpeta=subcarpeta, item_id=id_net, timeout=10.0
            )
        except VaultTunnelError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.detail},
            ) from exc

    @classmethod
    async def pujar_fitxer_binari(
        cls,
        categoria: str,
        nom_fitxer: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Escriu un fitxer binari (ex. PDF/XML factura SaaS B2B) al Disc del Superadmin."""
        if len(content) > cls.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="El fitxer supera el límit màxim de 50 MB.",
            )
        subcarpeta = MAPA_CARPETES_SUPERADMIN.get(categoria, categoria)
        nom_net = sanititzar_nom(nom_fitxer)
        mode, base_target = await cls._resolve_target()

        if mode == "LOCAL_FS":
            folder = cls._resoldre_carpeta_local(base_target, subcarpeta)
            folder.mkdir(parents=True, exist_ok=True)
            dest_file = (folder / nom_net).resolve()
            if not dest_file.is_relative_to(folder):
                raise HTTPException(status_code=400, detail="Nom de fitxer invàlid.")
            dest_file.write_bytes(content)
            return str(dest_file)

        try:
            await vault_tunnel_broker.file_put(
                base_target,
                subcarpeta=subcarpeta,
                filename=nom_net,
                content_bytes=content,
                content_type=content_type,
                timeout=30.0,
            )
            return f"superadmin-vault://{subcarpeta}/{nom_net}"
        except VaultTunnelError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.detail},
            ) from exc

    @classmethod
    async def obtenir_bytes_fitxer(cls, fitxer_path: str) -> Tuple[bytes, str]:
        """Recupera els bytes d'un fitxer emmagatzemat al Disc del Superadmin."""
        if not fitxer_path:
            raise HTTPException(status_code=404, detail="Ruta de fitxer Superadmin buida.")
        mode, base_target = await cls._resolve_target()

        clean = fitxer_path.replace("superadmin-vault://", "").replace("file://", "").strip()
        if mode == "LOCAL_FS":
            base_resolved = Path(base_target).resolve()
            cand = Path(clean)
            target = cand.resolve() if cand.is_absolute() else (base_resolved / clean.lstrip("/")).resolve()
            if not target.is_relative_to(base_resolved) or target == base_resolved or not target.is_file():
                raise HTTPException(status_code=404, detail="Fitxer no trobat al Disc del Superadmin.")
            return target.read_bytes(), target.name

        rel_path = clean.lstrip("/")
        try:
            return await vault_tunnel_broker.file_get(base_target, rel_path=rel_path, timeout=30.0)
        except VaultTunnelRemoteError as exc:
            if exc.status_code == 404:
                raise HTTPException(status_code=404, detail="Fitxer no trobat al Disc del Superadmin.") from exc
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        except VaultTunnelError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": "NODE_SUPERADMIN_OFFLINE", "message": exc.detail},
            ) from exc
