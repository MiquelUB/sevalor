#!/usr/bin/env python3
"""
Agent Local de Disc Dur Sobirà (Sevalor Vault Agent).
S'executa a l'ordinador/servidor de cada empresa client i gestiona l'arbre de carpetes físic.
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Sevalor Client Disk Vault Agent", version="1.0.0")

# Ruta física del disc dur del client (ex: "D:/Sevalormante_Dades" o "/media/akaun/Project_1/Sevalormante_docs")
VAULT_ROOT = Path(os.getenv("SEVALOR_VAULT_PATH", "/media/akaun/Project_1/Sevalormante_docs")).resolve()
VAULT_SECRET = os.getenv("SEVALOR_VAULT_SECRET", "sevalor-vault-secret-token")

# Estructura oficial de carpetes al disc dur del client
CARPETES_OFICIALS = [
    # 01. Clients
    "01_clients/fitxes",
    "01_clients/finques_i_instal_lacions",
    "01_clients/contractes_manteniment",
    # 02. Proveïdors
    "02_proveidors/fitxes",
    # 03. Magatzem
    "03_magatzem/articles_i_estoc",
    "03_magatzem/eines_custodia",
    "03_magatzem/albarans_compra",
    "03_magatzem/picking_fulles",
    # 04. Factures i Comptabilitat
    "04_factures/emeses_verifactu_pdf",
    "04_factures/emeses_verifactu_xml",
    "04_factures/prefactures_i_pressupostos",
    "04_factures/factures_proveidors",
    # 05. Plànols
    "05_planols/arxius_base",
    "05_planols/capes_vectorials",
    "05_planols/informes_exportats",
    # 06. Ordres de Treball
    "06_ordres_treball/actives_buffer",
    "06_ordres_treball/historic_tancades",
    "06_ordres_treball/informes_post_obra",
    # 07. Incidències de Camp
    "07_incidencies/fotos_camp",
    "07_incidencies/audios_veu",
    "07_incidencies/registres",
    # 08. Flota i Operaris
    "08_flota_i_operaris/vehicles",
    "08_flota_i_operaris/tiquets_despesa",
    "08_flota_i_operaris/registres_jornada",
    # 09. Agent Copilot Dedicat i Autoaprenentatge
    "09_copilot_ia/prompt_sistema",
    "09_copilot_ia/autoaprenentatge/memorandums_tecnics",
    "09_copilot_ia/autoaprenentatge/historic_preus_i_mermes",
    "09_copilot_ia/autoaprenentatge/converses_i_feedback",
    "09_copilot_ia/index_vectorial_rag",
    # 10. Protocols de l'Empresa i Manuals Tècnics
    "10_protocols_i_manuals/procediments_interns",
    "10_protocols_i_manuals/manuals_fabricants",
    "10_protocols_i_manuals/normativa_i_prl",
    # 11. Configuració i Backups
    "11_configuracio_i_backups/identitat_camaleo",
    "11_configuracio_i_backups/backups_locals",
]


def inicialitzar_estructura_disc() -> None:
    """Garanteix que totes les carpetes ordenades existeixin al disc dur del client."""
    for sub in CARPETES_OFICIALS:
        (VAULT_ROOT / sub).mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def on_startup() -> None:
    inicialitzar_estructura_disc()


def verificar_token_passarella(x_vault_token: str = Header(default="")) -> None:
    """Seguretat Zero-Trust: Només la passarel·la Hetzner autoritzada pot llegir/escriure."""
    if x_vault_token != VAULT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de passarel·la invàlid per accedir al disc dur local.",
        )


def _sanititzar_segment(segment: str) -> str:
    """Evita atacs de Path Traversal (.. /)."""
    net = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", segment.strip())
    if not net or net in (".", ".."):
        raise HTTPException(status_code=400, detail="Nom d'arxiu o carpeta invàlid.")
    return net


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Endpoint de diagnòstic per al botó 'Provar Disc Dur Dedicat' de Superadmin."""
    inicialitzar_estructura_disc()
    usage = shutil.disk_usage(VAULT_ROOT)
    return {
        "status": "OK",
        "vault_root": str(VAULT_ROOT),
        "carpetes": CARPETES_OFICIALS,
        "disc_total_gb": round(usage.total / (1024**3), 2),
        "disc_lliure_gb": round(usage.free / (1024**3), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# 1. GESTIÓ D'ENTITATS ESTRUCTURADES EN CARPETES (JSON per carpeta)
# ---------------------------------------------------------------------------

@app.put("/entitats/{categoria:path}/{item_id}", dependencies=[Depends(verificar_token_passarella)])
async def desar_entitat_json(categoria: str, item_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Desa o actualitza una fitxa (client, article, proveïdor, factura, OT) a la seva carpeta."""
    parts = [_sanititzar_segment(p) for p in categoria.strip("/").split("/") if p]
    folder = VAULT_ROOT.joinpath(*parts).resolve()
    if not str(folder).startswith(str(VAULT_ROOT)):
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
    folder = VAULT_ROOT.joinpath(*parts).resolve()
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
    folder = VAULT_ROOT.joinpath(*parts).resolve()
    id_clean = _sanititzar_segment(item_id)
    file_path = (folder / f"{id_clean}.json").resolve()
    if file_path.exists() and str(file_path).startswith(str(VAULT_ROOT)):
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
    folder = VAULT_ROOT.joinpath(*parts).resolve()
    if not str(folder).startswith(str(VAULT_ROOT)):
        raise HTTPException(status_code=400, detail="Carpeta invàlida.")
    folder.mkdir(parents=True, exist_ok=True)

    filename_clean = _sanititzar_segment(nom_desti)
    dest_path = (folder / filename_clean).resolve()

    content = await fitxer.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    rel_path = str(dest_path.relative_to(VAULT_ROOT))
    return {
        "status": "OK",
        "rel_path": rel_path,
        "mida_bytes": len(content),
    }


@app.get("/fitxers/{rel_path:path}", dependencies=[Depends(verificar_token_passarella)])
async def descarregar_fitxer_disc(rel_path: str) -> FileResponse:
    """Serveix en streaming un fitxer des del disc dur del client cap a la passarel·la Hetzner."""
    parts = [_sanititzar_segment(p) for p in rel_path.strip("/").split("/") if p]
    target = VAULT_ROOT.joinpath(*parts).resolve()
    if not str(target).startswith(str(VAULT_ROOT)) or not target.is_file():
        raise HTTPException(status_code=404, detail="Fitxer no trobat al disc dur de l'empresa.")
    return FileResponse(target, filename=target.name)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "9001"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"🚀 Iniciant Sevalor Vault Agent a {host}:{port} sobre {VAULT_ROOT}...")
    uvicorn.run(app, host=host, port=port)
