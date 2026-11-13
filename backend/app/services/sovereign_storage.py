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
from typing import Any, Dict, List, Optional, Tuple, cast

import httpx
from fastapi import HTTPException, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.network_utils import resolve_effective_node_url
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
        folder = base / sub
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

        payload_complet = {
            **dades,
            "_sovereign_meta": {
                "empresa_id": str(empresa_id),
                "categoria": categoria,
                "subcarpeta": subcarpeta,
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
                from app.workers.tasks import drenar_cua_transit_task  # type: ignore

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
        """Llegeix totes les fitxes JSON d'una carpeta del disc dur del client."""
        subcarpeta = MAPA_CARPETES_CLIENT.get(categoria, categoria)
        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)

        if mode == "LOCAL_FS":
            folder = (Path(base_target) / subcarpeta).resolve()
            if not folder.exists():
                return []
            registres: List[Dict[str, Any]] = []
            for fp in sorted(folder.glob("*.json"), key=os.path.getmtime, reverse=True):
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        registres.append(json.load(f))
                except Exception:
                    continue
            return registres

        url = f"{base_target}/entitats/{subcarpeta}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers={"X-Vault-Token": secret or ""})
                if resp.status_code == 200:
                    raw_data = resp.json()
                    return cast(list[dict[str, Any]], raw_data) if isinstance(raw_data, list) else []
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
                from app.workers.tasks import drenar_cua_transit_task  # type: ignore

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

                async def _streamer():
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
    ) -> Dict[str, str]:
        """Bolca la fitxa d'identitat camaleònica, la fitxa del Boss i el system_prompt.txt al disc del client."""
        rutes: Dict[str, str] = {}
        dades_empresa = {
            "id": str(empresa.id),
            "nom": empresa.nom,
            "nif": empresa.nif,
            "adreca": empresa.adreca,
            "subdomini": empresa.subdomini,
            "domini_custom": empresa.domini_custom,
            "vertical": empresa.vertical,
            "pla_subscripcio": empresa.pla_subscripcio,
            "primari_hsl": empresa.primari_hsl,
            "secundari_hsl": empresa.secundari_hsl,
            "accent_hsl": empresa.accent_hsl,
            "logotip_path": empresa.logotip_path,
            "node_ia_url": empresa.node_ia_url,
            "disc_dur_url": empresa.disc_dur_url,
        }
        rutes["empresa_json"] = await cls.desar_entitat_json(
            db=db,
            empresa_id=empresa.id,
            categoria="configuracio",
            item_id="empresa",
            dades=dades_empresa,
        )
        if boss is not None:
            rutes["boss_json"] = await cls.desar_entitat_json(
                db=db,
                empresa_id=empresa.id,
                categoria="operaris",
                item_id=str(boss.id),
                dades={
                    "id": str(boss.id),
                    "nom": boss.nom,
                    "cognoms": boss.cognoms,
                    "nif": boss.nif,
                    "email": boss.email,
                    "telefon": boss.telefon,
                    "rol": boss.rol,
                },
            )
            try:
                await cls.desar_entitat_json(
                    db=db,
                    empresa_id=empresa.id,
                    categoria="configuracio",
                    item_id="boss",
                    dades={
                        "id": str(boss.id),
                        "nom": boss.nom,
                        "cognoms": boss.cognoms,
                        "nif": boss.nif,
                        "email": boss.email,
                        "telefon": boss.telefon,
                        "rol": boss.rol,
                    },
                )
            except Exception:
                pass
        if empresa.agent_prompt_system:
            rutes["system_prompt"] = await cls.pujar_fitxer_binari(
                db=db,
                empresa_id=empresa.id,
                categoria="copilot_prompt",
                nom_fitxer="system_prompt.txt",
                content=empresa.agent_prompt_system.encode("utf-8"),
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
