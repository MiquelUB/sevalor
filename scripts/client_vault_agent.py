#!/usr/bin/env python3
"""
Agent Local de Disc Dur Sobirà i Proxy IA Unificat (Sevalor Vault Agent — Opció A+).
S'executa a l'ordinador dedicat de l'oficina del client (port 9001, rol EMPRESA)
o a l'ordinador del propietari del SaaS (port 9002, rol SUPERADMIN):
1. Gestiona les 38 carpetes oficials d'Empresa o les 20 de Superadmin sobre VAULT_PRIMARY_A.
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
from urllib.parse import urlparse

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
_VALID_VAULT_ROLES = ("EMPRESA", "SUPERADMIN")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB màxim per fitxer (AGENTS.md §3.4)

VAULT_ROLE = os.getenv("SEVALOR_VAULT_ROLE", "EMPRESA").strip().upper()
if VAULT_ROLE not in _VALID_VAULT_ROLES:
    raise ValueError(
        f"SEVALOR_VAULT_ROLE invàlid: {VAULT_ROLE!r}. Valors permesos: {_VALID_VAULT_ROLES}."
    )

VAULT_PRIMARY_A = Path(
    os.getenv("SEVALOR_VAULT_PATH_A", os.getenv("SEVALOR_VAULT_PATH", "./sevalor_vault_A"))
).resolve()
VAULT_SECONDARY_B = Path(
    os.getenv("SEVALOR_VAULT_PATH_B", "./sevalor_vault_B")
).resolve()
VAULT_SECRET = os.getenv("SEVALOR_VAULT_SECRET", _DEFAULT_INSECURE_SECRET)
LOCAL_LLM_BASE_URL = os.getenv("SEVALOR_LOCAL_LLM_URL", "http://127.0.0.1:1234").rstrip("/")

# 38 Carpetes Oficials idèntiques a MAPA_CARPETES_CLIENT (sovereign_storage.py)
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

# 20 Carpetes Oficials del Disc Dur Dedicat del Superadmin (idèntiques a MAPA_CARPETES_SUPERADMIN)
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


def _resolver_role() -> str:
    """Valida i retorna el rol actiu de la passarel·la (EMPRESA o SUPERADMIN)."""
    role = str(VAULT_ROLE).strip().upper()
    if role not in _VALID_VAULT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol de passarel·la invàlid.",
        )
    return role


def inicialitzar_estructura_disc() -> List[str]:
    """Crea físicament les 38 carpetes d'Empresa o les 20 de Superadmin + Disc B mirall."""
    role = _resolver_role()
    carpetes = CARPETES_SUPERADMIN if role == "SUPERADMIN" else CARPETES_OFICIALS
    root_a = VAULT_PRIMARY_A.resolve()
    root_b = VAULT_SECONDARY_B.resolve()
    for sub in carpetes:
        target = (root_a / sub).resolve()
        if not target.is_relative_to(root_a):
            raise HTTPException(status_code=400, detail="Ruta de subcarpeta fora del disc autoritzat.")
        target.mkdir(parents=True, exist_ok=True)
    (root_b / "backups_jornada").mkdir(parents=True, exist_ok=True)
    return list(carpetes)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    if not VAULT_SECRET or VAULT_SECRET == _DEFAULT_INSECURE_SECRET:
        logger.warning(
            "⚠️ SEVALOR_VAULT_SECRET utilitza el valor per defecte o és buit; configura el vault_token únic abans d'exposar la passarel·la."
        )
    inicialitzar_estructura_disc()
    yield


app = FastAPI(title="Sevalor Client Disk Vault Agent (Opció A+)", version="2.2.0", lifespan=_lifespan)


def verificar_token_passarella(x_vault_token: str = Header(default="")) -> None:
    """Seguretat Zero-Trust: valida el token de passarel·la configurat per a l'empresa o Superadmin."""
    if not x_vault_token or not VAULT_SECRET or not hmac.compare_digest(x_vault_token, VAULT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de passarel·la invàlid per accedir a la passarel·la local.",
        )


def _sanititzar_segment(segment: str) -> str:
    """Impedeix Path Traversal i segments buits."""
    raw = segment.strip()
    if not raw or raw in (".", "..") or ".." in raw or "\x00" in raw:
        raise HTTPException(status_code=400, detail="Nom d'arxiu o carpeta invàlid.")
    net = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", raw)
    if not net or net in (".", ".."):
        raise HTTPException(status_code=400, detail="Nom d'arxiu o carpeta invàlid.")
    return net


def _resoldre_carpeta_segura(categoria: str) -> Path:
    """Resol una carpeta dins VAULT_PRIMARY_A garantint arrel permesa i profunditat mínima."""
    root_a = VAULT_PRIMARY_A.resolve()
    parts = [_sanititzar_segment(p) for p in categoria.strip("/").split("/") if p]
    if not parts:
        raise HTTPException(status_code=400, detail="Cal indicar la categoria de carpeta.")
    folder = root_a.joinpath(*parts).resolve()
    if not folder.is_relative_to(root_a) or folder == root_a:
        raise HTTPException(status_code=400, detail="Ruta fora del disc autoritzat.")
    return folder


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Diagnòstic complet dels 2 discos durs dedicats i del nombre de carpetes."""
    carpetes = inicialitzar_estructura_disc()
    usage_a = shutil.disk_usage(VAULT_PRIMARY_A)
    usage_b = shutil.disk_usage(VAULT_SECONDARY_B)
    return {
        "status": "OK",
        "role": _resolver_role(),
        "vault_root": str(VAULT_PRIMARY_A),
        "vault_secondary_b": str(VAULT_SECONDARY_B),
        "carpetes": carpetes,
        "carpetes_count": len(carpetes),
        "disc_a_lliure_gb": round(usage_a.free / (1024**3), 2),
        "disc_b_lliure_gb": round(usage_b.free / (1024**3), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/admin/inicialitzar-ruta", dependencies=[Depends(verificar_token_passarella)])
async def endpoint_inicialitzar_ruta_carpetes() -> Dict[str, Any]:
    """Permet al Superadmin disparar la creació física completa de l'arbre de carpetes via túnel."""
    carpetes = inicialitzar_estructura_disc()
    return {
        "status": "OK",
        "role": _resolver_role(),
        "vault_root": str(VAULT_PRIMARY_A),
        "carpetes_count": len(carpetes),
        "carpetes": carpetes,
    }


@app.post("/backups/tancament-jornada", dependencies=[Depends(verificar_token_passarella)])
async def executar_backup_tancament_jornada(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rep el bolcat estructurat al tancament de jornada, el desa a la carpeta de backups locals
    i empaqueta un ZIP verificat amb SHA-256 al Disc A (dies senars) o Disc B (dies parells).
    """
    role = _resolver_role()
    inicialitzar_estructura_disc()
    ara = datetime.now(timezone.utc)
    iso_weekday = ara.isoweekday()  # 1=Dl ... 7=Dg
    es_dia_senar = (iso_weekday % 2) == 1

    root_a = VAULT_PRIMARY_A.resolve()
    root_b = VAULT_SECONDARY_B.resolve()
    backups_rel = (
        "08_backups_superadmin/backups_locals"
        if role == "SUPERADMIN"
        else "11_configuracio_i_backups/backups_locals"
    )
    disc_desti_root = (root_a / backups_rel) if es_dia_senar else (root_b / "backups_jornada")
    etiqueta_disc = "DISC_A_PRIMARI" if es_dia_senar else "DISC_B_MIRALL"
    disc_desti_root.mkdir(parents=True, exist_ok=True)

    data_str = ara.strftime("%Y-%m-%d_%H%M%S")
    dump_json_path = root_a / backups_rel / "ultim_dump_bd.json"
    dump_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    zip_filename = f"backup_jornada_{etiqueta_disc}_{data_str}.zip"
    zip_path = disc_desti_root / zip_filename

    total_files = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(root_a, followlinks=False):
            # Evitar recursivitat d'històrics de ZIPs dins del nou ZIP i no sortir de root_a via symlinks
            for fname in files:
                if fname.endswith(".zip"):
                    continue
                full_p = (Path(root) / fname).resolve()
                if not full_p.is_relative_to(root_a) or not full_p.is_file():
                    continue
                rel_p = full_p.relative_to(root_a)
                zf.write(full_p, str(rel_p))
                total_files += 1

    sha256_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (disc_desti_root / f"{zip_filename}.sha256").write_text(
        f"{sha256_hash}  {zip_filename}\n", encoding="utf-8"
    )

    return {
        "status": "OK",
        "role": role,
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
    parsed_llm = urlparse(LOCAL_LLM_BASE_URL)
    if parsed_llm.scheme not in ("http", "https") or not parsed_llm.netloc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuració del motor IA local invàlida.",
        )

    clean_path = llm_path.lstrip("/")
    if ".." in clean_path or any(c in clean_path for c in ("\r", "\n", "\x00")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ruta IA invàlida.")

    target_url = f"{LOCAL_LLM_BASE_URL}/v1/{clean_path}"
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "x-vault-token")
    }
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
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
        logger.warning("Error connectant amb motor IA local (%s): %s", target_url, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor IA local temporalment no disponible.",
        )


# ---------------------------------------------------------------------------
# 1. GESTIÓ D'ENTITATS ESTRUCTURADES EN CARPETES (JSON per carpeta sobre VAULT_PRIMARY_A)
# ---------------------------------------------------------------------------

@app.put("/entitats/{categoria:path}/{item_id}", dependencies=[Depends(verificar_token_passarella)])
async def desar_entitat_json(categoria: str, item_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Desa o actualitza una fitxa (client, article, proveïdor, factura, OT) a la seva carpeta."""
    folder = _resoldre_carpeta_segura(categoria)
    folder.mkdir(parents=True, exist_ok=True)

    id_clean = _sanititzar_segment(item_id)
    file_path = (folder / f"{id_clean}.json").resolve()
    if not file_path.is_relative_to(folder):
        raise HTTPException(status_code=400, detail="Identificador d'entitat invàlid.")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    return {"status": "SAVED", "categoria": categoria, "id": id_clean, "path": str(file_path)}


@app.get("/entitats/{categoria:path}", dependencies=[Depends(verificar_token_passarella)])
async def llistar_entitats_json(categoria: str) -> List[Dict[str, Any]]:
    """Llegeix totes les fitxes d'una carpeta (ex. tots els clients o articles del magatzem)."""
    folder = _resoldre_carpeta_segura(categoria)
    if not folder.exists() or not folder.is_dir():
        return []

    items: List[Dict[str, Any]] = []
    for fpath in sorted(folder.glob("*.json"), key=os.path.getmtime, reverse=True):
        resolved_f = fpath.resolve()
        if not resolved_f.is_relative_to(folder) or not resolved_f.is_file():
            continue
        try:
            with open(resolved_f, "r", encoding="utf-8") as f:
                items.append(json.load(f))
        except Exception:
            continue
    return items


@app.delete("/entitats/{categoria:path}/{item_id}", dependencies=[Depends(verificar_token_passarella)])
async def eliminar_entitat_json(categoria: str, item_id: str) -> Dict[str, Any]:
    """Elimina un registre JSON dins d'una carpeta verificada del disc sobirà."""
    folder = _resoldre_carpeta_segura(categoria)
    id_clean = _sanititzar_segment(item_id)
    file_path = (folder / f"{id_clean}.json").resolve()
    if file_path.is_file() and file_path.is_relative_to(folder) and file_path != VAULT_PRIMARY_A.resolve():
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
    folder = _resoldre_carpeta_segura(categoria)
    folder.mkdir(parents=True, exist_ok=True)

    filename_clean = _sanititzar_segment(nom_desti)
    dest_path = (folder / filename_clean).resolve()
    if not dest_path.is_relative_to(folder):
        raise HTTPException(status_code=400, detail="Nom de fitxer invàlid.")

    content = await fitxer.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El fitxer supera el límit màxim autoritzat de 50 MB.",
        )

    with open(dest_path, "wb") as f:
        f.write(content)

    rel_path = str(dest_path.relative_to(VAULT_PRIMARY_A.resolve()))
    return {
        "status": "OK",
        "rel_path": rel_path,
        "mida_bytes": len(content),
    }


@app.get("/fitxers/{rel_path:path}", dependencies=[Depends(verificar_token_passarella)])
async def descarregar_fitxer_disc(rel_path: str) -> FileResponse:
    """Serveix en streaming un fitxer des del disc dur del client cap a la passarel·la Hetzner."""
    root_a = VAULT_PRIMARY_A.resolve()
    parts = [_sanititzar_segment(p) for p in rel_path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Ruta de fitxer invàlida.")
    target = root_a.joinpath(*parts).resolve()
    if not target.is_relative_to(root_a) or not target.is_file():
        raise HTTPException(status_code=404, detail="Fitxer no trobat al disc dur.")
    return FileResponse(target, filename=target.name)


if __name__ == "__main__":
    import uvicorn

    role_exec = _resolver_role()
    default_port = "9002" if role_exec == "SUPERADMIN" else "9001"
    port = int(os.getenv("PORT", default_port))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"🚀 Iniciant Sevalor Vault Agent ({role_exec}) a {host}:{port} sobre {VAULT_PRIMARY_A}...")
    uvicorn.run(app, host=host, port=port)
