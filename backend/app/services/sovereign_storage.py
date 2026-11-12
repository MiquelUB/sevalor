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
from typing import Any, Dict, List, Optional, Tuple, cast

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

    TRANSIT_QUEUE_DIR = Path(os.getenv("SOVEREIGN_TRANSIT_QUEUE_DIR", "/tmp/sevalor_transit_queue"))

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

        base_vaults = os.getenv("CLIENT_DISKS_MOUNT_ROOT", "/tmp/sevalor_client_disks")
        if not emp:
            raw_disc = os.path.join(base_vaults, f"disc_{emp_uuid}")
            inicialitzar_arbre_carpetes_disc(raw_disc)
            return ("LOCAL_FS", str(Path(raw_disc).resolve()), None)

        raw_disc = (getattr(emp, "disc_dur_url", None) or getattr(emp, "node_ia_url", None) or "").strip()
        if raw_disc.startswith("Carpeta Local:"):
            raw_disc = ""

        if not raw_disc:
            raw_disc = os.path.join(base_vaults, f"disc_{emp.subdomini or str(emp.id)}")

        if raw_disc.startswith("http://") or raw_disc.startswith("https://"):
            effective = resolve_effective_node_url(raw_disc) or raw_disc
            secret = getattr(emp, "telegram_webhook_secret", None) or os.getenv(
                "SEVALOR_VAULT_SECRET", "sevalor-vault-secret-token"
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
        """Guarda temporalment en cua de trànsit quan l'ordinador del client està apagat."""
        emp_dir = (cls.TRANSIT_QUEUE_DIR / str(empresa_id)).resolve()
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
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        data_path.write_bytes(payload_bytes)
        return f"transit://{empresa_id}/{subcarpeta}/{identificador}"

    @classmethod
    async def drenar_cua_transit_empresa(
        cls, db: AsyncSession, empresa_id: str | uuid.UUID
    ) -> Dict[str, int]:
        """Envia tots els paquets retinguts a l'Agent HTTP del client i els esborra immediatament d'Hetzner."""
        emp_dir = (cls.TRANSIT_QUEUE_DIR / str(empresa_id)).resolve()
        if not emp_dir.exists():
            return {"enviats": 0, "pendents": 0}

        mode, base_target, secret = await cls.resoldre_desti_disc_empresa(db, empresa_id)
        if mode != "HTTP_VAULT":
            return {"enviats": 0, "pendents": 0}

        enviats = 0
        pendents = 0
        async with httpx.AsyncClient(timeout=5.0) as client:
            for meta_file in sorted(emp_dir.glob("*.meta.json")):
                bin_file = emp_dir / meta_file.name.replace(".meta.json", ".bin")
                if not bin_file.exists():
                    meta_file.unlink(missing_ok=True)
                    continue
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                raw_bytes = bin_file.read_bytes()
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
                        pendents += 1
                except httpx.RequestError:
                    pendents += 1
                    break

        if emp_dir.exists() and not any(emp_dir.iterdir()):
            emp_dir.rmdir()
        return {"enviats": enviats, "pendents": pendents}

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
            async with httpx.AsyncClient(timeout=3.0) as client:
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
            logger.warning(
                "Error enviant fitxer al disc dur de %s (%s). Encurant a cua de trànsit temporal...",
                empresa_id,
                exc,
            )
            transit_ref = cls._encuar_paquet_transit(
                empresa_id=empresa_id,
                tipus="BINARI",
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
