#!/usr/bin/env python3
"""
Agent Local de Disc Dur Sobirà i Proxy IA Unificat (Sevalor Vault Agent — Opció A+).
S'executa a l'ordinador dedicat de l'oficina del client:
1. Gestiona les 31 carpetes oficials sobre el Disc Primari A (SEVALOR_VAULT_PATH_A).
2. Enruta /v1/* cap al servidor local d'Ollama / LM Studio (127.0.0.1:1234).
3. Executa el backup diari al tancament de jornada alternant Disc A (dies senars) i Disc B (dies parells) amb SHA-256.
"""

import hashlib
import hmac
import json
import logging
import os
import re
import shutil
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List

import httpx
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

logger = logging.getLogger("sevalor_vault_agent")

_DEFAULT_INSECURE_SECRET = "sevalor-vault-secret-token"
VAULT_PRIMARY_A = Path(
    os.getenv("SEVALOR_VAULT_PATH_A", os.getenv("SEVALOR_VAULT_PATH", "./sevalor_vault_A"))
).resolve()
VAULT_SECONDARY_B = Path(
    os.getenv("SEVALOR_VAULT_PATH_B", "./sevalor_vault_B")
).resolve()
VAULT_SECRET = os.getenv("SEVALOR_VAULT_SECRET", _DEFAULT_INSECURE_SECRET)
LOCAL_LLM_BASE_URL = os.getenv("SEVALOR_LOCAL_LLM_URL", "http://127.0.0.1:1234").rstrip("/")

# 31 Carpetes Oficials idèntiques a MAPA_CARPETES_CLIENT (sovereign_storage.py)
CARPETES_OFICIALS: List[str] = [
    "01_clients/fitxes",
    "01_clients/finques_i_instal_lacions",
    "01_clients/contractes_manteniment",
    "02_proveidors/fitxes",
    "03_magatzem/articles_i_estoc",
    "03_magatzem/eines_custodia",
    "03_magatzem/albarans_compra",
    "03_magatzem/picking_fulles",
    "04_factures/emeses_verifactu_pdf",
    "04_factures/emeses_verifactu_xml",
    "04_factures/prefactures_i_pressupostos",
    "04_factures/factures_proveidors",
    "05_planols/arxius_base",
    "05_planols/capes_vectorials",
    "05_planols/informes_exportats",
    "06_ordres_treball/actives_buffer",
    "06_ordres_treball/historic_tancades",
    "06_ordres_treball/informes_post_obra",
    "07_incidencies/fotos_camp",
    "07_incidencies/audios_veu",
    "07_incidencies/registres",
    "08_flota_i_operaris/vehicles",
    "08_flota_i_operaris/vehicles/alertes_flota",
    "08_flota_i_operaris/operaris",
    "08_flota_i_operaris/operaris/documents_rrhh",
    "08_flota_i_operaris/operaris/alertes_rrhh",
    "08_flota_i_operaris/tiquets_despesa",
    "08_flota_i_operaris/registres_jornada",
    "09_copilot_ia/prompt_sistema",
    "09_copilot_ia/autoaprenentatge/memorandums_tecnics",
    "09_copilot_ia/autoaprenentatge/historic_preus_i_mermes",
    "09_copilot_ia/autoaprenentatge/converses_i_feedback",
    "09_copilot_ia/index_vectorial_rag",
    "10_protocols_i_manuals/procediments_interns",
    "10_protocols_i_manuals/manuals_fabricants",
    "10_protocols_i_manuals/normativa_i_prl",
    "11_configuracio_i_backups/identitat_camaleo",
    "11_configuracio_i_backups/backups_locals",
]


def inicialitzar_estructura_disc() -> None:
    """Garanteix que totes les carpetes oficials i el disc secundari B existeixin."""
    for sub in CARPETES_OFICIALS:
        (VAULT_PRIMARY_A / sub).mkdir(parents=True, exist_ok=True)
    (VAULT_SECONDARY_B / "backups_jornada").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    if not VAULT_SECRET or VAULT_SECRET == _DEFAULT_INSECURE_SECRET:
        logger.warning(
            "⚠️ SEVALOR_VAULT_SECRET utilitza el valor per defecte o és buit; configura el vault_token únic de l'empresa abans d'exposar la passarel·la."
        )
    inicialitzar_estructura_disc()
    yield


app = FastAPI(title="Sevalor Client Disk Vault Agent (Opció A+)", version="2.1.0", lifespan=_lifespan)


def verificar_token_passarella(x_vault_token: str = Header(default="")) -> None:
    """Seguretat Zero-Trust: valida el token de passarel·la configurat per a l'empresa."""
    if not x_vault_token or not VAULT_SECRET or not hmac.compare_digest(x_vault_token, VAULT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de passarel·la invàlid per accedir a la passarel·la local de l'empresa.",
        )


def _sanititzar_segment(segment: str) -> str:
    """Impedeix Path Traversal."""
    net = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", segment.strip())
    if not net or net in (".", ".."):
        raise HTTPException(status_code=400, detail="Nom d'arxiu o carpeta invàlid.")
    return net


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Diagnòstic complet dels 2 discos durs dedicats i del nombre de carpetes."""
    inicialitzar_estructura_disc()
    usage_a = shutil.disk_usage(VAULT_PRIMARY_A)
    usage_b = shutil.disk_usage(VAULT_SECONDARY_B)
    return {
        "status": "OK",
        "vault_root": str(VAULT_PRIMARY_A),
        "vault_secondary_b": str(VAULT_SECONDARY_B),
        "carpetes": CARPETES_OFICIALS,
        "carpetes_count": len(CARPETES_OFICIALS),
        "disc_a_lliure_gb": round(usage_a.free / (1024**3), 2),
        "disc_b_lliure_gb": round(usage_b.free / (1024**3), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/backups/tancament-jornada", dependencies=[Depends(verificar_token_passarella)])
async def executar_backup_tancament_jornada(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rep el bolcat estructurat de la BD de l'empresa al tancament de jornada,
    el desa a 11_configuracio_i_backups/backups_locals i empaqueta un ZIP verificat amb SHA-256
    al Disc A (dies senars: 1, 3, 5, 7) o al Disc B (dies parells: 2, 4, 6).
    """
    inicialitzar_estructura_disc()
    ara = datetime.now(timezone.utc)
    iso_weekday = ara.isoweekday()  # 1=Dl ... 7=Dg
    es_dia_senar = (iso_weekday % 2) == 1

    disc_desti_root = (
        VAULT_PRIMARY_A / "11_configuracio_i_backups/backups_locals"
        if es_dia_senar
        else VAULT_SECONDARY_B / "backups_jornada"
    )
    etiqueta_disc = "DISC_A_PRIMARI" if es_dia_senar else "DISC_B_MIRALL"
    disc_desti_root.mkdir(parents=True, exist_ok=True)

    data_str = ara.strftime("%Y-%m-%d_%H%M%S")
    dump_json_path = VAULT_PRIMARY_A / "11_configuracio_i_backups/backups_locals" / "ultim_dump_bd.json"
    dump_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    zip_filename = f"backup_jornada_{etiqueta_disc}_{data_str}.zip"
    zip_path = disc_desti_root / zip_filename

    total_files = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(VAULT_PRIMARY_A):
            # Evitar recursivitat d'històrics de ZIPs dins del nou ZIP
            for fname in files:
                if fname.endswith(".zip"):
                    continue
                full_p = Path(root) / fname
                rel_p = full_p.relative_to(VAULT_PRIMARY_A)
                zf.write(full_p, str(rel_p))
                total_files += 1

    sha256_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (disc_desti_root / f"{zip_filename}.sha256").write_text(
        f"{sha256_hash}  {zip_filename}\n", encoding="utf-8"
    )

    return {
        "status": "OK",
        "disc_utilitzat": etiqueta_disc,
        "dia_setmana_iso": iso_weekday,
        "zip_path": str(zip_path),
        "sha256": sha256_hash,
        "fitxers_empaquetats": total_files,
        "mida_bytes": zip_path.stat().st_size,
    }


@app.api_route(
    "/v1/{llm_path:path}",
    methods=["GET", "POST"],
    dependencies=[Depends(verificar_token_passarella)],
)
async def proxy_copilot_local(llm_path: str, request: Request) -> Response:
    """Proxy unificat cap a Ollama / LM Studio local (127.0.0.1:1234) pel mateix túnel."""
    target_url = f"{LOCAL_LLM_BASE_URL}/v1/{llm_path.lstrip('/')}"
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "x-vault-token")
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers,
                params=request.query_params,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Motor IA local ({LOCAL_LLM_BASE_URL}) no disponible: {exc}",
        )


# ---------------------------------------------------------------------------
# 1. GESTIÓ D'ENTITATS ESTRUCTURADES EN CARPETES (JSON per carpeta sobre VAULT_PRIMARY_A)
# ---------------------------------------------------------------------------

@app.put("/entitats/{categoria:path}/{item_id}", dependencies=[Depends(verificar_token_passarella)])
async def desar_entitat_json(categoria: str, item_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Desa o actualitza una fitxa (client, article, proveïdor, factura, OT) a la seva carpeta."""
    parts = [_sanititzar_segment(p) for p in categoria.strip("/").split("/") if p]
    folder = VAULT_PRIMARY_A.joinpath(*parts).resolve()
    if not str(folder).startswith(str(VAULT_PRIMARY_A)):
        raise HTTPException(status_code=400, detail="Ruta fora del disc autoritzat.")
    folder.mkdir(parents=True, exist_ok=True)

    id_clean = _sanititzar_segment(item_id)
    file_path = folder / f"{id_clean}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    return {"status": "SAVED", "categoria": categoria, "id": id_clean, "path": str(file_path)}


@app.get("/entitats/{categoria:path}", dependencies=[Depends(verificar_token_passarella)])
async def llistar_entitats_json(categoria: str) -> List[Dict[str, Any]]:
    """Llegeix totes les fitxes d'una carpeta (ex. tots els clients o articles del magatzem)."""
    parts = [_sanititzar_segment(p) for p in categoria.strip("/").split("/") if p]
    folder = VAULT_PRIMARY_A.joinpath(*parts).resolve()
    if not folder.exists():
        return []

    items: List[Dict[str, Any]] = []
    for fpath in sorted(folder.glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                items.append(json.load(f))
        except Exception:
            continue
    return items


@app.delete("/entitats/{categoria:path}/{item_id}", dependencies=[Depends(verificar_token_passarella)])
async def eliminar_entitat_json(categoria: str, item_id: str) -> Dict[str, Any]:
    parts = [_sanititzar_segment(p) for p in categoria.strip("/").split("/") if p]
    folder = VAULT_PRIMARY_A.joinpath(*parts).resolve()
    id_clean = _sanititzar_segment(item_id)
    file_path = (folder / f"{id_clean}.json").resolve()
    if file_path.exists() and str(file_path).startswith(str(VAULT_PRIMARY_A)):
        file_path.unlink()
    return {"status": "DELETED", "id": id_clean}


# ---------------------------------------------------------------------------
# 2. GESTIÓ D'ARXIUS BINARIS (Plànols, PDFs Factures, Fotos, Albarans, Àudios)
# ---------------------------------------------------------------------------

@app.post("/fitxers/{categoria:path}", dependencies=[Depends(verificar_token_passarella)])
async def pujar_fitxer_disc(
    categoria: str,
    fitxer: UploadFile = File(...),
    nom_desti: str = Form(...),
) -> Dict[str, Any]:
    """Escriu un fitxer físic (PDF, DXF, WebP, etc.) a la carpeta corresponent del disc dur."""
    parts = [_sanititzar_segment(p) for p in categoria.strip("/").split("/") if p]
    folder = VAULT_PRIMARY_A.joinpath(*parts).resolve()
    if not str(folder).startswith(str(VAULT_PRIMARY_A)):
        raise HTTPException(status_code=400, detail="Carpeta invàlida.")
    folder.mkdir(parents=True, exist_ok=True)

    filename_clean = _sanititzar_segment(nom_desti)
    dest_path = (folder / filename_clean).resolve()

    content = await fitxer.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    rel_path = str(dest_path.relative_to(VAULT_PRIMARY_A))
    return {
        "status": "OK",
        "rel_path": rel_path,
        "mida_bytes": len(content),
    }


@app.get("/fitxers/{rel_path:path}", dependencies=[Depends(verificar_token_passarella)])
async def descarregar_fitxer_disc(rel_path: str) -> FileResponse:
    """Serveix en streaming un fitxer des del disc dur del client cap a la passarel·la Hetzner."""
    parts = [_sanititzar_segment(p) for p in rel_path.strip("/").split("/") if p]
    target = VAULT_PRIMARY_A.joinpath(*parts).resolve()
    if not str(target).startswith(str(VAULT_PRIMARY_A)) or not target.is_file():
        raise HTTPException(status_code=404, detail="Fitxer no trobat al disc dur de l'empresa.")
    return FileResponse(target, filename=target.name)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "9001"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"🚀 Iniciant Sevalor Vault Agent a {host}:{port} sobre {VAULT_PRIMARY_A}...")
    uvicorn.run(app, host=host, port=port)
