"""Tests Fase 3 — Renderitzat PNG de Plànols GIS a la PWA Operari, vinculació a ordre_treball_id i RLS."""

from __future__ import annotations

import base64
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.models.models import (
    CarpetaPlanol,
    Client,
    Empresa,
    OrdreTreball,
    PlanolBase,
    Usuari,
)
from app.services.sovereign_storage import (
    SovereignStorageGateway,
    inicialitzar_arbre_carpetes_disc,
)

PNG_1X1_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _make_real_2page_pdf() -> bytes:
    doc = pymupdf.open()  # type: ignore[no-untyped-call]
    p1 = doc.new_page(width=200, height=200)  # type: ignore[no-untyped-call]
    p1.insert_text((20, 40), "Planol Base Pag 1")
    p2 = doc.new_page(width=200, height=200)  # type: ignore[no-untyped-call]
    p2.insert_text((20, 40), "Planol Base Pag 2")
    raw = doc.tobytes()  # type: ignore[no-untyped-call]
    doc.close()  # type: ignore[no-untyped-call]
    return bytes(raw)


def _make_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    payload: dict[str, Any] = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def _seed_tenant_planols(admin_session, disc_root: Path, label: str) -> dict[str, Any]:
    inicialitzar_arbre_carpetes_disc(disc_root)
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    ot_id = uuid.uuid4()
    carpeta_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Empresa Planols {label} S.L.",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini=f"f3-{label.lower()}-{uuid.uuid4().hex[:6]}",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
            node_ia_actiu=True,
        )
    )
    await admin_session.flush()

    for uid, nom_u, rol_u in [(op_id, "Operari", "OPERARI"), (eng_id, "Enginyer", "ENGINYER")]:
        admin_session.add(
            Usuari(
                id=uid,
                empresa_id=emp_id,
                nif=f"{rol_u[0]}{uid.hex[:7].upper()}P",
                nom=nom_u,
                cognoms=label,
                email=f"{rol_u.lower()}-{emp_id.hex[:6]}@sevalor.test",
                telefon="622333444",
                rol=rol_u,
                pin_hash="fake",
                password_hash="fake",
                estat="ACTIU",
            )
        )

    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"CLI-{uuid.uuid4().hex[:6].upper()}",
            rao_social=f"Client {label} S.A.",
            nif="A" + uuid.uuid4().hex[:8].upper(),
            adreca_fiscal="Carrer del Plànol 10",
            actiu=True,
        )
    )
    await admin_session.flush()

    admin_session.add(
        CarpetaPlanol(
            id=carpeta_id,
            empresa_id=emp_id,
            nom=f"Carpeta {label}",
            categoria="FINQUES",
        )
    )
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=emp_id,
            codi=f"OT-F3-{uuid.uuid4().hex[:5].upper()}",
            client_id=cli_id,
            cap_de_colla_id=op_id,
            titol="Traçat As-Built canonada",
            adreca="Finca Sud 3",
            estat="EN_CURS",
            data_planificacio=date.today(),
        )
    )
    await admin_session.flush()

    return {
        "empresa_id": emp_id,
        "op_id": op_id,
        "eng_id": eng_id,
        "client_id": cli_id,
        "ot_id": ot_id,
        "carpeta_id": carpeta_id,
        "headers_op": {
            "Authorization": f"Bearer {_make_token(op_id, emp_id, 'OPERARI')}",
            "X-Empresa-ID": str(emp_id),
        },
        "headers_eng": {
            "Authorization": f"Bearer {_make_token(eng_id, emp_id, 'ENGINYER')}",
            "X-Empresa-ID": str(emp_id),
        },
    }


@pytest.mark.asyncio
async def test_01_render_pdf_i_png_operari_des_del_disc_sobira(admin_session, tmp_path: Path):
    t = await _seed_tenant_planols(admin_session, tmp_path / "disc_f3_1", "Render")
    emp_id = t["empresa_id"]

    pdf_bytes = _make_real_2page_pdf()
    pdf_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=admin_session,
        empresa_id=emp_id,
        categoria="planols",
        nom_fitxer="finca_sector_a.pdf",
        content=pdf_bytes,
        content_type="application/pdf",
    )
    png_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=admin_session,
        empresa_id=emp_id,
        categoria="planols",
        nom_fitxer="esquema_valvula.png",
        content=PNG_1X1_BYTES,
        content_type="image/png",
    )

    planol_pdf_id = uuid.uuid4()
    planol_png_id = uuid.uuid4()
    admin_session.add(
        PlanolBase(
            id=planol_pdf_id,
            empresa_id=emp_id,
            carpeta_id=t["carpeta_id"],
            titol="Plànol Sector A (2 pàgines)",
            codi_referencia=f"PLN-PDF-{uuid.uuid4().hex[:5].upper()}",
            tipus_fitxer="PDF",
            fitxer_path=pdf_path,
            mida_bytes=len(pdf_bytes),
        )
    )
    admin_session.add(
        PlanolBase(
            id=planol_png_id,
            empresa_id=emp_id,
            carpeta_id=t["carpeta_id"],
            titol="Esquema Vàlvula PNG",
            codi_referencia=f"PLN-PNG-{uuid.uuid4().hex[:5].upper()}",
            tipus_fitxer="PNG",
            fitxer_path=png_path,
            mida_bytes=len(PNG_1X1_BYTES),
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. PDF pàgina 0 -> PNG renderitzat + X-Total-Pages = 2
        r_pdf0 = await ac.get(
            f"/api/v1/operari/planols/{planol_pdf_id}/render?pagina=0",
            headers=t["headers_op"],
        )
        assert r_pdf0.status_code == 200, r_pdf0.text
        assert r_pdf0.headers["content-type"].startswith("image/png")
        assert r_pdf0.headers["x-total-pages"] == "2"
        assert r_pdf0.content.startswith(b"\x89PNG\r\n\x1a\n")

        # 2. PDF pàgina 1 + HEAD
        r_pdf1 = await ac.get(
            f"/api/v1/operari/planols/{planol_pdf_id}/render?pagina=1",
            headers=t["headers_op"],
        )
        assert r_pdf1.status_code == 200
        assert r_pdf1.content.startswith(b"\x89PNG\r\n\x1a\n")

        r_head = await ac.head(
            f"/api/v1/operari/planols/{planol_pdf_id}/render",
            headers=t["headers_op"],
        )
        assert r_head.status_code == 200
        assert r_head.headers["x-total-pages"] == "2"

        # 3. PNG directe -> pass-through 200 image/png
        r_png = await ac.get(
            f"/api/v1/operari/planols/{planol_png_id}/render",
            headers=t["headers_op"],
        )
        assert r_png.status_code == 200
        assert r_png.headers["content-type"].startswith("image/png")
        assert r_png.headers["x-total-pages"] == "1"
        assert r_png.content == PNG_1X1_BYTES


@pytest.mark.asyncio
async def test_02_crear_capa_asbuilt_amb_ordre_treball_id_i_conciliacio(
    admin_session, tmp_path: Path
):
    t = await _seed_tenant_planols(admin_session, tmp_path / "disc_f3_2", "AsBuilt")
    emp_id = t["empresa_id"]
    planol_id = uuid.uuid4()

    png_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=admin_session,
        empresa_id=emp_id,
        categoria="planols",
        nom_fitxer="base_ot.png",
        content=PNG_1X1_BYTES,
        content_type="image/png",
    )
    admin_session.add(
        PlanolBase(
            id=planol_id,
            empresa_id=emp_id,
            carpeta_id=t["carpeta_id"],
            titol="Plànol Base OT",
            codi_referencia=f"PLN-OT-{uuid.uuid4().hex[:5].upper()}",
            tipus_fitxer="PNG",
            fitxer_path=png_path,
            mida_bytes=len(PNG_1X1_BYTES),
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Crear capa As-Built vinculada a ordre_treball_id online
        r_capa = await ac.post(
            f"/api/v1/operari/planols/{planol_id}/capes",
            json={
                "nom": "Canonada PE32 Instal·lada",
                "disciplina": "AIGUA_REG",
                "color_hex": "#0284c7",
                "ordre_treball_id": str(t["ot_id"]),
                "dades_geojson": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "LineString", "coordinates": [[10, 10], [80, 50]]},
                            "properties": {"nom": "Tram Nord"},
                        }
                    ],
                },
            },
            headers=t["headers_op"],
        )
        assert r_capa.status_code == 201, r_capa.text
        assert r_capa.json()["ordre_treball_id"] == str(t["ot_id"])

        # 2. Crear segona capa via Sync Offline (POST_PLANOL_CAPA) amb ordre_treball_id
        r_sync = await ac.post(
            "/api/v1/sync/push",
            json={
                "accions": [
                    {
                        "id": f"capa-sync-{uuid.uuid4().hex[:6]}",
                        "accio": "POST_PLANOL_CAPA",
                        "payload": {
                            "planol_id": str(planol_id),
                            "ordre_treball_id": str(t["ot_id"]),
                            "capa": {
                                "nom": "Vàlvula Offline",
                                "disciplina": "AIGUA_REG",
                                "geometries_geojson": {
                                    "type": "FeatureCollection",
                                    "features": [
                                        {
                                            "type": "Feature",
                                            "geometry": {"type": "Point", "coordinates": [45, 55]},
                                            "properties": {"nom": "Vàlvula 1"},
                                        }
                                    ],
                                },
                            },
                        },
                    }
                ]
            },
            headers=t["headers_op"],
        )
        assert r_sync.status_code == 200, r_sync.text
        assert r_sync.json()["processades"] == 1

        # 3. Verificar que les 2 capes apareixen a la conciliació de l'OT per a l'Enginyer
        r_conc = await ac.post(
            f"/api/v1/gestio/feines/{t['ot_id']}/reconciliacio-post-obra",
            headers=t["headers_eng"],
        )
        assert r_conc.status_code == 200, r_conc.text
        capes_gis = r_conc.json()["conciliacio"]["capes_gis"]
        noms_capes = {c["nom"] for c in capes_gis}
        assert "Canonada PE32 Instal·lada" in noms_capes
        assert "Vàlvula Offline" in noms_capes


@pytest.mark.asyncio
async def test_03_rls_aillament_render_i_capes_planols_operari(admin_session, tmp_path: Path):
    ta = await _seed_tenant_planols(admin_session, tmp_path / "disc_f3_rlsa", "RlsA")
    tb = await _seed_tenant_planols(admin_session, tmp_path / "disc_f3_rlsb", "RlsB")

    planol_a_id = uuid.uuid4()
    png_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=admin_session,
        empresa_id=ta["empresa_id"],
        categoria="planols",
        nom_fitxer="secret_a.png",
        content=PNG_1X1_BYTES,
        content_type="image/png",
    )
    admin_session.add(
        PlanolBase(
            id=planol_a_id,
            empresa_id=ta["empresa_id"],
            carpeta_id=ta["carpeta_id"],
            titol="Plànol Confidencial A",
            codi_referencia=f"PLN-SECA-{uuid.uuid4().hex[:5].upper()}",
            tipus_fitxer="PNG",
            fitxer_path=png_path,
            mida_bytes=len(PNG_1X1_BYTES),
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_ren = await ac.get(
            f"/api/v1/operari/planols/{planol_a_id}/render",
            headers=tb["headers_op"],
        )
        assert r_ren.status_code == 404

        r_fit = await ac.get(
            f"/api/v1/operari/planols/{planol_a_id}/fitxer",
            headers=tb["headers_op"],
        )
        assert r_fit.status_code == 404

        r_cap = await ac.post(
            f"/api/v1/operari/planols/{planol_a_id}/capes",
            json={"nom": "Intrusió B", "ordre_treball_id": str(ta["ot_id"])},
            headers=tb["headers_op"],
        )
        assert r_cap.status_code == 404

        r_capes_a = await ac.get(
            f"/api/v1/operari/planols/{planol_a_id}/capes",
            headers=ta["headers_op"],
        )
        assert r_capes_a.status_code == 200
        assert len(r_capes_a.json()) == 0
