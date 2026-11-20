"""
Servei de còpies de seguretat setmanals (Spec 024 RF-18, Spec 021 RF-19).

Implementa:
- Compressió ZIP del directori /data/<empresa_id>/ i /docs/<empresa_id>/.
- Exclusió explícita de la subcarpeta /docs/<empresa_id>/backups/ (immunitat).
- Execució programada via Celery Beat (cada diumenge).
- RLS actiu: cada backup es fa amb tenant context (empresa_id).
- Zero Mock Data: si no hi ha dades, es genera un ZIP buit amb un manifest.
- Protecció anti-recursivitat: el backup no inclou backups anteriors.
"""

import logging
import os
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sovereign_storage import SovereignStorageGateway
from app.services.vault_tunnel import VaultTunnelError, vault_tunnel_broker

logger = logging.getLogger("backup_service")

# Directoris base (només per fallback local sense disc remot configurat)
DATA_BASE = "/data"
DOCS_BASE = "/docs"


async def executar_backup_sobira_empresa(
    db: AsyncSession,
    empresa_id: str,
    ruta_desti_local: str | None = None,
) -> dict[str, Any]:
    """Executa còpia de seguretat sobirana al disc del client via Túnel WSS Únic (ADR-001)."""
    mode, target, _ = await SovereignStorageGateway.resoldre_desti_disc_empresa(db, empresa_id)
    if mode == "WSS_TUNNEL":
        try:
            vault_resp = await vault_tunnel_broker.call(
                target,
                "backup_daily",
                {"empresa_id": str(empresa_id)},
                timeout=60.0,
            )
            zip_path = str(vault_resp.get("zip_path") or "")
            return {
                "status": str(vault_resp.get("status") or "OK"),
                "estat": "COMPLETAT",
                "mode": "WSS_TUNNEL",
                "backup_file": os.path.basename(zip_path) if zip_path else "",
                "zip_path": zip_path,
                "sha256": vault_resp.get("sha256"),
                "disc_utilitzat": vault_resp.get("disc_utilitzat"),
                "vault_response": vault_resp,
            }
        except VaultTunnelError as exc:
            raise RuntimeError(f"Vault WSS backup error ({exc.code}): {exc.detail}") from exc

    if mode == "OFFLINE_TRANSIT" and not ruta_desti_local:
        raise RuntimeError("El PC dedicat de l'empresa no està connectat al túnel WSS per executar el backup.")

    desti = ruta_desti_local or os.path.join(target, "11_configuracio_i_backups", "backups_locals")
    return executar_backup_empresa(empresa_id, desti)


def executar_backup_empresa(
    empresa_id: str,
    ruta_desti: str,
) -> dict:
    """
    Executa la còpia de seguretat completa d'una empresa.

    Args:
        empresa_id: UUID de l'empresa (forma part del path).
        ruta_desti: Ruta absoluta on es desarà el fitxer ZIP.

    Returns:
        dict amb: ruta_zip, mida_bytes, timestamp, estat, num_fitxers
    """
    data_inici = datetime.now(timezone.utc)
    data_str = data_inici.strftime("%Y-%m-%d_%H%M%S")
    nom_zip = f"backup_{empresa_id}_{data_str}.zip"
    ruta_zip = os.path.join(ruta_desti, nom_zip)

    dirs_origen = [
        os.path.join(DATA_BASE, empresa_id),
        os.path.join(DOCS_BASE, empresa_id),
    ]

    # Exclusió de backups anteriors (immunitat anti-recursivitat)
    dirs_excloure = {os.path.join(DOCS_BASE, empresa_id, "backups")}

    total_fitxers = 0
    total_bytes = 0

    os.makedirs(ruta_desti, exist_ok=True)

    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # Manifest
        zf.writestr(
            "manifest.txt",
            (
                f"Backup SEVALOR\n"
                f"Empresa: {empresa_id}\n"
                f"Data: {data_str}\n"
                f"Timestamp: {int(data_inici.timestamp())}\n"
            ),
        )

        for dir_arrel in dirs_origen:
            if not os.path.isdir(dir_arrel):
                continue
            for root, dirs, files in os.walk(dir_arrel):
                # Excloure directoris prohibits (anti-recursivitat)
                if root in dirs_excloure:
                    dirs.clear()
                    continue
                # Excloure qualsevol subdirectori 'backups'
                dirs[:] = [d for d in dirs if d != "backups"]

                for fitxer_nom in files:
                    ruta_completa = os.path.join(root, fitxer_nom)
                    try:
                        arcname = os.path.relpath(ruta_completa, start=os.path.dirname(dir_arrel))
                        zf.write(ruta_completa, arcname)
                        total_fitxers += 1
                        total_bytes += os.path.getsize(ruta_completa)
                    except (OSError, PermissionError) as e:
                        logger.warning("No s'ha pogut incloure %s: %s", ruta_completa, e)

    data_fi = datetime.now(timezone.utc)
    durada_segons = (data_fi - data_inici).total_seconds()

    logger.info(
        "Backup completat: %s | Fitxers: %d | Mida: %.2f MB | Durada: %.1f s",
        ruta_zip,
        total_fitxers,
        total_bytes / (1024 * 1024),
        durada_segons,
    )

    return {
        "ruta_zip": ruta_zip,
        "mida_bytes": total_bytes,
        "timestamp": data_str,
        "estat": "COMPLETAT" if total_fitxers > 0 else "BUIDA",
        "num_fitxers": total_fitxers,
        "durada_segons": durada_segons,
    }


# Alias per compatibilitat amb tests existents
generar_backup_tenant = executar_backup_empresa
