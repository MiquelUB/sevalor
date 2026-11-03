"""
Motor de Passarel·la d'Emmagatzematge Sobirà (Zero-Storage Gateway).

Garanteix que totes les dades i fitxers de cada empresa es guardin exclusivament
al seu propi disc dur (`disc_dur_url`), ordenats per carpetes temàtiques:
clients, proveïdors, magatzem, factures, plànols, ordres_treball, incidències,
flota_i_operaris, copilot_ia (amb autoaprenentatge) i protocols_i_manuals.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    @staticmethod
    async def resoldre_desti_disc_empresa(
        db: AsyncSession, empresa_id: str | uuid.UUID
    ) -> Tuple[str, str, Optional[str]]:
        """
        Obté la destinació del disc dur configurat per a l'empresa.
        Retorna: (mode: 'LOCAL_FS' | 'HTTP_VAULT', base_target: str, secret: Optional[str])
        """
        emp_uuid = uuid.UUID(str(empresa_id))
        res = await db.execute(select(Empresa).where(Empresa.id == emp_uuid))
        emp = res.scalars().first()
        if not emp:
            raise HTTPException(status_code=404, detail="Empresa no trobada.")

        raw_disc = (getattr(emp, "disc_dur_url", None) or "").strip()

        # Si el camp està buit en entorn de test o desenvolupament local, o si és Sevalormante:
        if not raw_disc or raw_disc.startswith("Carpeta Local:"):
            sub = (emp.subdomini or "").lower()
            if "sevalormante" in sub or "sevalormante" in (emp.nom or "").lower():
                default_sevalormante = "/media/akaun/Project_1/Sevalormante_docs"
                if os.path.exists("/media/akaun/Project_1"):
                    raw_disc = default_sevalormante
            if not raw_disc or raw_disc.startswith("Carpeta Local:"):
                # En entorn de test o quan es configura una ruta base de discos de clients
                base_vaults = os.getenv("CLIENT_DISKS_MOUNT_ROOT", "/tmp/sevalor_client_disks")
                raw_disc = os.path.join(base_vaults, f"disc_{emp.subdomini or str(emp.id)}")

        if raw_disc.startswith("http://") or raw_disc.startswith("https://"):
            effective = resolve_effective_node_url(raw_disc) or raw_disc
            secret = getattr(emp, "telegram_webhook_secret", None) or os.getenv(
                "SEVALOR_VAULT_SECRET", "sevalor-vault-secret-token"
            )
            return ("HTTP_VAULT", effective.rstrip("/"), secret)

        # Mode sistema de fitxers físic (disc dur muntat o directori dedicat del client)
        inicialitzar_arbre_carpetes_disc(raw_disc)
        return ("LOCAL_FS", str(Path(raw_disc).resolve()), None)

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
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.put(
                    url,
                    json=payload_complet,
                    headers={"X-Vault-Token": secret or ""},
                )
                if resp.status_code >= 400:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                return f"vault://{subcarpeta}/{id_net}.json"
        except httpx.RequestError as exc:
            logger.error("Disc dur remot de %s desconnectat: %s", empresa_id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_EMPRESA_OFFLINE",
                    "message": "El disc dur dedicat de l'empresa està apagat o desconnectat.",
                },
            )

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
                    return resp.json()
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
        Escriu un fitxer binari (PDF, DXF, WebP, Àudio) exclusivament al disc dur del client.
        Zero emmagatzematge al servidor central d'Hetzner.
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
            with open(dest_file, "wb") as f:
                f.write(content)
            return str(dest_file)

        url = f"{base_target}/fitxers/{subcarpeta}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                files = {"fitxer": (nom_net, content, content_type)}
                data = {"nom_desti": nom_net}
                resp = await client.post(
                    url,
                    files=files,
                    data=data,
                    headers={"X-Vault-Token": secret or ""},
                )
                if resp.status_code >= 400:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                return f"vault://{subcarpeta}/{nom_net}"
        except httpx.RequestError as exc:
            logger.error("Error enviant fitxer al disc dur de %s: %s", empresa_id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "NODE_EMPRESA_OFFLINE",
                    "message": "No s'ha pogut guardar el fitxer perquè el disc dur del client està desconnectat.",
                },
            )

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
        if fitxer_path.startswith("vault://"):
            _, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)
            rel_path = fitxer_path.replace("vault://", "").lstrip("/")
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

        # Si és ruta física al disc dur muntat del client
        fpath = os.path.abspath(fitxer_path)
        if not os.path.exists(fpath):
            raise HTTPException(
                status_code=404, detail="Fitxer no trobat al disc dur de l'empresa."
            )
        return FileResponse(
            path=fpath,
            filename=os.path.basename(fpath),
            media_type=media_type,
            content_disposition_type=disposition,
        )
