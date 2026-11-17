"""
Motor de Passarel·la d'Emmagatzematge Sobirà (Zero-Storage Gateway).

Garanteix que totes les dades i fitxers de cada empresa es guardin exclusivament
al seu propi disc dur (`disc_dur_url`), ordenats per carpetes temàtiques:
clients, proveïdors, magatzem, factures, plànols, ordres_treball, incidències,
flota_i_operaris, copilot_ia (amb autoaprenentatge) i protocols_i_manuals.
"""

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
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, cast

import httpx
from fastapi import HTTPException, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.network_utils import get_candidate_node_urls, resolve_effective_node_url
from app.models.models import Empresa

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
    async def resoldre_desti_disc_empresa(
        db: Optional[AsyncSession], empresa_id: str | uuid.UUID
    ) -> Tuple[str, str, Optional[str]]:
        """
        Obté la destinació del disc dur configurat per a l'empresa.
        Retorna: (mode: 'LOCAL_FS' | 'HTTP_VAULT', base_target: str, secret: Optional[str])
        """
        emp_uuid = uuid.UUID(str(empresa_id))
        emp = None
        if db is not None:
            res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
            emp = res.scalars().first()

        base_vaults = os.getenv("CLIENT_DISKS_MOUNT_ROOT")
        if not base_vaults:
            if os.path.exists("/data") and os.access("/data", os.W_OK):
                base_vaults = "/data"
            else:
                base_vaults = os.getenv("CLIENT_DISKS_MOUNT_ROOT", "/tmp/sevalor_client_disks")

        if not emp:
            raw_disc = os.path.join(base_vaults, f"disc_{emp_uuid}")
            inicialitzar_arbre_carpetes_disc(raw_disc)
            return ("LOCAL_FS", str(Path(raw_disc).resolve()), None)

        raw_disc = (getattr(emp, "disc_dur_url", None) or "").strip()
        if raw_disc.startswith("Carpeta Local:"):
            raw_disc = ""

        # Només descartem si apunta directament al port per defecte de LM Studio (:1234) sense Agent Vault (:9001 o túnel)
        if ":1234" in raw_disc:
            raw_disc = ""

        if not raw_disc:
            raw_disc = os.path.join(base_vaults, f"disc_{emp.subdomini or str(emp.id)}")

        if raw_disc.startswith("http://") or raw_disc.startswith("https://"):
            effective = resolve_effective_node_url(raw_disc) or raw_disc
            vault_tok = getattr(emp, "vault_token", None)
            legacy_tg_tok = getattr(emp, "telegram_webhook_secret", None)
            secret = (
                vault_tok
                or (
                    legacy_tg_tok
                    if legacy_tg_tok and str(legacy_tg_tok).startswith("svlt_")
                    else None
                )
                or os.getenv("SEVALOR_VAULT_SECRET", "sevalor-vault-secret-token")
            )
            return ("HTTP_VAULT", effective.rstrip("/"), secret)

        inicialitzar_arbre_carpetes_disc(raw_disc)
        return ("LOCAL_FS", str(Path(raw_disc).resolve()), None)

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
        cls, db: AsyncSession, empresa_id: str | uuid.UUID
    ) -> Dict[str, int]:
        """Envia tots els paquets retinguts a l'Agent HTTP del client i els esborra immediatament d'Hetzner."""
        emp_dir = (cls._get_transit_queue_dir() / str(empresa_id)).resolve()
        if not emp_dir.exists():
            return {"enviats": 0, "pendents": 0}

        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)
        if mode != "HTTP_VAULT":
            return {"enviats": 0, "pendents": 0}

        enviats = 0
        pendents = 0
        async with httpx.AsyncClient(timeout=10.0) as client:
            for meta_file in sorted(emp_dir.glob("*.meta.json")):
                bin_file = emp_dir / meta_file.name.replace(".meta.json", ".bin")
                if not bin_file.exists():
                    meta_file.unlink(missing_ok=True)
                    continue
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                raw_bytes = cls._decrypt_transit_payload(empresa_id, bin_file.read_bytes())
                try:
                    if meta["tipus"] == "JSON":
                        url = f"{base_target}/entitats/{meta['subcarpeta']}/{meta['identificador']}"
                        resp = await client.put(
                            url,
                            content=raw_bytes,
                            headers={
                                "Content-Type": "application/json",
                                "X-Vault-Token": secret or "",
                            },
                        )
                    else:
                        url = f"{base_target}/fitxers/{meta['subcarpeta']}"
                        resp = await client.post(
                            url,
                            files={"fitxer": (meta["identificador"], raw_bytes, meta["content_type"])},
                            data={"nom_desti": meta["identificador"]},
                            headers={"X-Vault-Token": secret or ""},
                        )
                    if resp.status_code < 400:
                        # Auto-purga immediata al servidor Hetzner
                        bin_file.unlink(missing_ok=True)
                        meta_file.unlink(missing_ok=True)
                        enviats += 1
                    else:
                        logger.warning(
                            "Rebutjat drenatge de trànsit per %s (%s): HTTP %s - %s",
                            empresa_id,
                            meta.get("identificador"),
                            resp.status_code,
                            resp.text[:200],
                        )
                        pendents += 1
                except httpx.RequestError:
                    pendents += 1
                    break

        if emp_dir.exists() and not any(emp_dir.iterdir()):
            emp_dir.rmdir()
        return {"enviats": enviats, "pendents": pendents}

    @classmethod
    async def drenar_totes_cues_transit(cls, db: AsyncSession) -> Dict[str, int]:
        """Recorre totes les empreses amb paquets pendents en cua de trànsit i els sincronitza."""
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

    @staticmethod
    async def verificar_roundtrip_http_vault(base_url: str, secret: Optional[str]) -> Dict[str, Any]:
        """Comprova salut, proxy IA opcional i prova real d'escriptura->lectura->esborrat contra client_vault_agent.py."""
        probe_id = f"_healthcheck_{uuid.uuid4().hex[:8]}"
        headers = {"X-Vault-Token": secret or ""}
        ia_proxy_ok = False
        async with httpx.AsyncClient(timeout=5.0) as client:
            health_resp = await client.get(f"{base_url}/health")
            if health_resp.status_code != 200:
                return {
                    "ok": False,
                    "motiu": "ENDPOINT_NO_TROBAT" if health_resp.status_code == 404 else "HTTP_ERROR",
                    "codi_http": health_resp.status_code,
                    "missatge": f"L'agent del disc ha respost HTTP {health_resp.status_code} a /health.",
                }
            try:
                health_json = health_resp.json()
            except Exception:
                health_json = {}

            try:
                ia_resp = await client.get(f"{base_url}/v1/models", headers=headers)
                ia_proxy_ok = ia_resp.status_code == 200
            except Exception:
                ia_proxy_ok = False

            put_url = f"{base_url}/entitats/11_configuracio_i_backups/identitat_camaleo/{probe_id}"
            put_resp = await client.put(
                put_url,
                json={"probe": True, "ts": datetime.now(timezone.utc).isoformat()},
                headers=headers,
            )
            if put_resp.status_code in (401, 403):
                return {
                    "ok": False,
                    "motiu": "TOKEN_INVALID",
                    "codi_http": put_resp.status_code,
                    "missatge": (
                        "L'agent de disc dur ha rebutjat el Token Vault (HTTP 403). "
                        "Assegura't que SEVALOR_VAULT_SECRET a l'ordinador del client coincideixi amb el vault_token de l'empresa."
                    ),
                }
            if put_resp.status_code == 404:
                return {
                    "ok": False,
                    "motiu": "ENDPOINT_NO_TROBAT",
                    "codi_http": 404,
                    "missatge": "La URL respon a /health però no implementa /entitats (no és client_vault_agent.py v2).",
                }
            if put_resp.status_code >= 400:
                return {
                    "ok": False,
                    "motiu": "ERROR_ESCRIPTURA_DISC",
                    "codi_http": put_resp.status_code,
                    "missatge": f"Error escrivint prova al disc del client: HTTP {put_resp.status_code} ({put_resp.text[:160]}).",
                }

            list_resp = await client.get(
                f"{base_url}/entitats/11_configuracio_i_backups/identitat_camaleo",
                headers=headers,
            )
            readable = list_resp.status_code == 200
            await client.delete(put_url, headers=headers)
            if not readable:
                return {
                    "ok": False,
                    "motiu": "ERROR_LECTURA_DISC",
                    "codi_http": list_resp.status_code,
                    "missatge": f"S'ha pogut escriure però no llegir el fitxer de prova (HTTP {list_resp.status_code}).",
                }
            return {
                "ok": True,
                "codi_http": 200,
                "ia_proxy_ok": ia_proxy_ok,
                "vault_root": health_json.get("vault_root"),
                "disc_a_lliure_gb": health_json.get("disc_a_lliure_gb"),
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

        # Mode HTTP_VAULT (Túnel cap a l'Agent Local del Client)
        url = f"{base_target}/entitats/{subcarpeta}/{id_net}"
        payload_bytes = json.dumps(payload_complet, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.put(
                    url,
                    content=payload_bytes,
                    headers={
                        "Content-Type": "application/json",
                        "X-Vault-Token": secret or "",
                    },
                )
                if resp.status_code in (401, 403):
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail="Token Vault rebutjat per l'agent del disc dur (HTTP 403). Verifica SEVALOR_VAULT_SECRET.",
                    )
                if resp.status_code >= 400:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                return f"vault://{subcarpeta}/{id_net}.json"
        except httpx.RequestError as exc:
            logger.warning(
                "Disc dur remot de %s desconnectat (%s). Encurant a cua de trànsit temporal...",
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

    @classmethod
    async def llegir_entitats_json(
        cls,
        db: AsyncSession,
        empresa_id: str | uuid.UUID,
        categoria: str,
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

        url = f"{base_target}/entitats/{subcarpeta}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers={"X-Vault-Token": secret or ""})
                if resp.status_code in (401, 403):
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail="Token Vault rebutjat per l'agent del disc dur (HTTP 403).",
                    )
                if resp.status_code == 200:
                    raw_data = resp.json()
                    return cls._filtrar_entitats_verificades(
                        empresa_id, categoria, subcarpeta, raw_data
                    )
                return []
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_EMPRESA_OFFLINE",
                    "message": "El disc dur dedicat de l'empresa no respon.",
                },
            )

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

        url = f"{base_target}/fitxers/{subcarpeta}/{nom_net}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers={"X-Vault-Token": secret or ""})
                if resp.status_code == 200:
                    return resp.content.decode("utf-8", errors="replace")
                return None
        except httpx.RequestError:
            return None

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

        # Mode HTTP_VAULT (Agent Local al PC del client)
        url = f"{base_target}/fitxers/{subcarpeta}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                files = {"fitxer": (nom_net, content, content_type)}
                data = {"nom_desti": nom_net}
                resp = await client.post(
                    url,
                    files=files,
                    data=data,
                    headers={"X-Vault-Token": secret or ""},
                )
                if resp.status_code in (401, 403):
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail="Token Vault rebutjat per l'agent del disc dur (HTTP 403). Verifica SEVALOR_VAULT_SECRET.",
                    )
                if resp.status_code >= 400:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                return f"vault://{subcarpeta}/{nom_net}"
        except httpx.RequestError as exc:
            logger.warning(
                "Agent HTTP del client %s desconnectat (%s). Encurant fitxer %s a cua de trànsit...",
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

        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)
        if mode == "HTTP_VAULT":
            rel_path = fitxer_path.replace("vault://", "").replace("transit://", "").lstrip("/")
            if rel_path.startswith(str(empresa_id) + "/"):
                rel_path = rel_path[len(str(empresa_id)) + 1 :]
            url = f"{base_target}/fitxers/{rel_path}"
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url, headers={"X-Vault-Token": secret or ""})
                    if resp.status_code == 200:
                        return resp.content, os.path.basename(rel_path)
            except httpx.RequestError:
                pass

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

        url = f"{base_target}/fitxers/{subcarpeta}/{nom_net}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers={"X-Vault-Token": secret or ""})
                return resp.status_code == 200
        except httpx.RequestError:
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
        emp_uuid = uuid.UUID(emp_str)
        filename = os.path.basename(raw_clean.replace("vault://", "").replace("transit://", ""))
        rel_path = raw_clean.replace("vault://", "").lstrip("/")

        # 2. Cua de trànsit temporal transit://
        if raw_clean.startswith("transit://") or "transit" in raw_clean:
            found_transit = cls._trobar_fitxer_transit(emp_str, raw_clean)
            if found_transit is not None:
                return found_transit

        # 3. Exploració exhaustiva dels discos de l'empresa
        subdom = None
        if db is not None:
            emp_obj = (await db.execute(select(Empresa).where(Empresa.id == emp_uuid))).scalars().first()
            if emp_obj:
                subdom = emp_obj.subdomini

        mode, base_target, _ = await cls.resoldre_desti_disc_empresa(db, empresa_id)

        candidate_roots = [
            Path(base_target),
            Path(f"/data/disc_{subdom}") if subdom else None,
            Path(f"/data/disc_{emp_str}"),
            Path(f"/data/{emp_str}"),
            Path(f"/tmp/sevalor_client_disks/disc_{subdom}") if subdom else None,
            Path(f"/tmp/sevalor_client_disks/disc_{emp_str}"),
        ]

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

        # Si no s'ha trobat localment (o el paquet transit:// ja ha estat drenat cap al Vault remot)
        if fitxer_path.startswith("vault://") or fitxer_path.startswith("transit://"):
            mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)
            if mode == "HTTP_VAULT":
                rel_path = fitxer_path.replace("vault://", "").replace("transit://", "").lstrip("/")
                if rel_path.startswith(str(empresa_id) + "/"):
                    rel_path = rel_path[len(str(empresa_id)) + 1 :]
                url = f"{base_target}/fitxers/{rel_path}"

                async def _streamer() -> AsyncGenerator[bytes, None]:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        async with client.stream(
                            "GET", url, headers={"X-Vault-Token": secret or ""}
                        ) as resp:
                            if resp.status_code >= 400:
                                raise HTTPException(
                                    status_code=404, detail="Fitxer no trobat al disc del client."
                                )
                            async for chunk in resp.aiter_bytes(chunk_size=65536):
                                yield chunk

                filename = os.path.basename(rel_path)
                return StreamingResponse(
                    _streamer(),
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
        agent_prompt_system: Optional[str] = None,
    ) -> Dict[str, str]:
        """Bolca la fitxa d'identitat camaleònica, la fitxa del Boss i el system_prompt.txt al disc del client."""
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
            "disc_dur_url": reals_emp.get("disc_dur_url", empresa.disc_dur_url),
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
        prompt_final = (
            agent_prompt_system
            if agent_prompt_system is not None
            else empresa.agent_prompt_system
        )
        if prompt_final:
            rutes["system_prompt"] = await cls.pujar_fitxer_binari(
                db=db,
                empresa_id=empresa.id,
                categoria="copilot_prompt",
                nom_fitxer="system_prompt.txt",
                content=prompt_final.encode("utf-8"),
                content_type="text/plain; charset=utf-8",
            )
        return rutes

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

        raw_bytes, _ = await cls.obtenir_bytes_fitxer(db, empresa_id, old_path)
        return await cls.pujar_fitxer_binari(
            db=db,
            empresa_id=empresa_id,
            categoria=categoria,
            nom_fitxer=nom_net,
            content=raw_bytes,
            content_type=content_type,
        )


class SuperadminStorageGateway:
    """Passarel·la exclusiva del propietari SaaS cap al seu disc dur dedicat (/media/akaun/Project_1/Sevalor_Superadmin_docs)."""

    MAX_UPLOAD_BYTES = 50 * 1024 * 1024

    @staticmethod
    def _resoldre_carpeta_local(base_target: str, subcarpeta: str) -> Path:
        base_resolved = Path(base_target).resolve()
        folder = (base_resolved / subcarpeta).resolve()
        if not folder.is_relative_to(base_resolved) or folder == base_resolved:
            raise HTTPException(status_code=400, detail="Ruta de carpeta Superadmin invàlida.")
        return folder

    @staticmethod
    def _resolve_target() -> Tuple[str, str, Optional[str]]:
        url = os.getenv("SUPERADMIN_VAULT_URL", "http://host.docker.internal:9002").strip()
        if not url:
            url = "http://host.docker.internal:9002"
        secret = os.getenv("SUPERADMIN_VAULT_SECRET", "").strip()
        if url.startswith(("http://", "https://")):
            if not secret:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SUPERADMIN_VAULT_SECRET no configurat per accedir al túnel del Disc Superadmin.",
                )
            effective = resolve_effective_node_url(url) or url
            return ("HTTP_VAULT", effective.rstrip("/"), secret)
        if os.path.exists("/.dockerenv"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Zero-Storage: dins de Docker cal utilitzar un túnel HTTP/HTTPS cap al Disc Superadmin.",
            )
        return ("LOCAL_FS", str(Path(url).resolve()), None)

    @classmethod
    async def _http_request(
        cls,
        base_target: str,
        secret: Optional[str],
        method: str,
        rel_url: str,
        *,
        timeout: float = 8.0,
        offline_detail: Any = "El Disc Dur de Superadmin no respon.",
        **request_kwargs: Any,
    ) -> httpx.Response:
        """Executa una petició HTTP autenticada provant les URLs candidates del túnel Superadmin."""
        candidates = get_candidate_node_urls(base_target) or [base_target.rstrip("/")]
        last_exc: Optional[Exception] = None
        req_headers = {"X-Vault-Token": secret or "", **request_kwargs.pop("headers", {})}
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            for base in candidates:
                url = f"{base.rstrip('/')}/{rel_url.lstrip('/')}"
                try:
                    resp = await client.request(
                        method=method,
                        url=url,
                        headers=req_headers,
                        **request_kwargs,
                    )
                    if resp.status_code in (401, 403):
                        raise HTTPException(
                            status_code=resp.status_code,
                            detail="Token rebutjat per la passarel·la del Disc Superadmin.",
                        )
                    return resp
                except httpx.RequestError as exc:
                    last_exc = exc
                    continue

        logger.warning("Passarel·la Superadmin desconnectada (%s): %s", rel_url, last_exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=offline_detail,
        )

    @classmethod
    async def inicialitzar_rutes_superadmin(cls, ruta_personalitzada: Optional[str] = None) -> Dict[str, Any]:
        """Crea les 20 carpetes oficials del Superadmin (en LOCAL_FS fora d'Hetzner o via túnel POST /admin/inicialitzar-ruta)."""
        if ruta_personalitzada and not ruta_personalitzada.startswith(("http://", "https://")):
            if os.path.exists("/.dockerenv"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Zero-Storage: dins de Docker no es permet crear rutes locals de Superadmin sense túnel HTTP.",
                )
            creades = inicialitzar_arbre_carpetes_superadmin(ruta_personalitzada)
            return {
                "mode": "LOCAL_FS",
                "vault_root": str(Path(ruta_personalitzada).resolve()),
                "carpetes_count": len(creades),
                "carpetes": creades,
            }

        secret: Optional[str]
        if ruta_personalitzada and ruta_personalitzada.startswith(("http://", "https://")):
            secret = os.getenv("SUPERADMIN_VAULT_SECRET", "").strip()
            if not secret:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SUPERADMIN_VAULT_SECRET no configurat per connectar al túnel del Disc Superadmin.",
                )
            mode = "HTTP_VAULT"
            base_target = (resolve_effective_node_url(ruta_personalitzada) or ruta_personalitzada).rstrip("/")
        else:
            mode, base_target, secret = cls._resolve_target()

        if mode == "LOCAL_FS":
            creades = inicialitzar_arbre_carpetes_superadmin(base_target)
            return {
                "mode": "LOCAL_FS",
                "vault_root": base_target,
                "carpetes_count": len(creades),
                "carpetes": creades,
            }

        resp = await cls._http_request(
            base_target,
            secret,
            "POST",
            "/admin/inicialitzar-ruta",
            timeout=8.0,
            offline_detail="La passarel·la del Disc Dur de Superadmin no respon.",
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail="Error inicialitzant carpetes al Disc Dur de Superadmin.",
            )
        return cast(Dict[str, Any], resp.json())

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
        mode, base_target, secret = cls._resolve_target()

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

        payload_bytes = json.dumps(payload_complet, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        resp = await cls._http_request(
            base_target,
            secret,
            "PUT",
            f"/entitats/{subcarpeta}/{id_net}",
            timeout=5.0,
            headers={"Content-Type": "application/json"},
            content=payload_bytes,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail="Error escrivint al Disc Superadmin.")
        return f"superadmin-vault://{subcarpeta}/{id_net}.json"

    @classmethod
    async def llegir_entitats_json(cls, categoria: str) -> List[Dict[str, Any]]:
        """Llegeix totes les fitxes JSON d'una carpeta del Disc del Superadmin."""
        subcarpeta = MAPA_CARPETES_SUPERADMIN.get(categoria, categoria)
        mode, base_target, secret = cls._resolve_target()

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

        resp = await cls._http_request(
            base_target,
            secret,
            "GET",
            f"/entitats/{subcarpeta}",
            timeout=8.0,
            offline_detail={
                "code": "NODE_SUPERADMIN_OFFLINE",
                "message": "El disc dur dedicat del Superadmin no respon.",
            },
        )
        if resp.status_code == 200:
            raw_data = resp.json()
            return cast(List[Dict[str, Any]], raw_data) if isinstance(raw_data, list) else []
        return []

    @classmethod
    async def eliminar_entitat_json(cls, categoria: str, item_id: str | uuid.UUID) -> bool:
        """Elimina una fitxa JSON del Disc del Superadmin amb validació estricta de ruta."""
        subcarpeta = MAPA_CARPETES_SUPERADMIN.get(categoria, categoria)
        id_net = sanititzar_nom(str(item_id))
        mode, base_target, secret = cls._resolve_target()

        if mode == "LOCAL_FS":
            folder = cls._resoldre_carpeta_local(base_target, subcarpeta)
            file_path = (folder / f"{id_net}.json").resolve()
            if file_path.is_file() and file_path.is_relative_to(folder):
                file_path.unlink()
                return True
            return False

        resp = await cls._http_request(
            base_target,
            secret,
            "DELETE",
            f"/entitats/{subcarpeta}/{id_net}",
            timeout=5.0,
        )
        return resp.status_code < 400

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
        mode, base_target, secret = cls._resolve_target()

        if mode == "LOCAL_FS":
            folder = cls._resoldre_carpeta_local(base_target, subcarpeta)
            folder.mkdir(parents=True, exist_ok=True)
            dest_file = (folder / nom_net).resolve()
            if not dest_file.is_relative_to(folder):
                raise HTTPException(status_code=400, detail="Nom de fitxer invàlid.")
            dest_file.write_bytes(content)
            return str(dest_file)

        resp = await cls._http_request(
            base_target,
            secret,
            "POST",
            f"/fitxers/{subcarpeta}",
            timeout=10.0,
            files={"fitxer": (nom_net, content, content_type)},
            data={"nom_desti": nom_net},
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail="Error pujant fitxer al Disc Superadmin.")
        return f"superadmin-vault://{subcarpeta}/{nom_net}"

    @classmethod
    async def obtenir_bytes_fitxer(cls, fitxer_path: str) -> Tuple[bytes, str]:
        """Recupera els bytes d'un fitxer emmagatzemat al Disc del Superadmin."""
        if not fitxer_path:
            raise HTTPException(status_code=404, detail="Ruta de fitxer Superadmin buida.")
        mode, base_target, secret = cls._resolve_target()

        clean = fitxer_path.replace("superadmin-vault://", "").replace("file://", "").strip()
        if mode == "LOCAL_FS":
            base_resolved = Path(base_target).resolve()
            cand = Path(clean)
            target = cand.resolve() if cand.is_absolute() else (base_resolved / clean.lstrip("/")).resolve()
            if not target.is_relative_to(base_resolved) or target == base_resolved or not target.is_file():
                raise HTTPException(status_code=404, detail="Fitxer no trobat al Disc del Superadmin.")
            return target.read_bytes(), target.name

        rel_path = clean.lstrip("/")
        resp = await cls._http_request(
            base_target,
            secret,
            "GET",
            f"/fitxers/{rel_path}",
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.content, os.path.basename(rel_path)
        raise HTTPException(status_code=404, detail="Fitxer no trobat al Disc del Superadmin.")
