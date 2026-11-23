"""Tests Fase 4 — Tancament integral PWA: Fotos QA reals, Signatura PNG, Receptor, Tiquets i Offline Sync."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1.operari_auth import create_access_token
from app.core.db import set_tenant_context
from app.main import app
from app.models.models import (
    Client,
    Empresa,
    OrdreTreball,
    TiquetDespesa,
    Usuari,
)
from app.services.reconciliacio_ot_service import ReconciliacioOTService
from app.services.sovereign_storage import inicialitzar_arbre_carpetes_disc

VALID_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 30
VALID_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
VALID_PNG_BYTES = base64.b64decode(VALID_PNG_B64)
VALID_PNG_DATA_URI = f"data:image/png;base64,{VALID_PNG_B64}"


@pytest_asyncio.fixture
async def setup_fase4_tenants(admin_session, tmp_path: Path):
    """Prepara dos tenants amb disc sobirà propi, operaris i ordres de treball sobre SAVEPOINT."""
    emp_a_id = uuid.uuid4()
    emp_b_id = uuid.uuid4()
    disc_a = tmp_path / f"disc_f4_a_{emp_a_id.hex[:6]}"
    disc_b = tmp_path / f"disc_f4_b_{emp_b_id.hex[:6]}"
    inicialitzar_arbre_carpetes_disc(disc_a)
    inicialitzar_arbre_carpetes_disc(disc_b)

    emp_a = Empresa(
        id=emp_a_id,
        nom="Sevalor Fase 4 A SL",
        nif=f"B{emp_a_id.hex[:8].upper()}",
        subdomini=f"f4a-{emp_a_id.hex[:6]}",
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
        disc_dur_url=str(disc_a),
        node_ia_actiu=True,
    )
    emp_b = Empresa(
        id=emp_b_id,
        nom="Sevalor Fase 4 B SL",
        nif=f"B{emp_b_id.hex[:8].upper()}",
        subdomini=f"f4b-{emp_b_id.hex[:6]}",
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
        disc_dur_url=str(disc_b),
        node_ia_actiu=True,
    )
    admin_session.add_all([emp_a, emp_b])
    await admin_session.flush()

    op_a = Usuari(
        id=uuid.uuid4(),
        empresa_id=emp_a_id,
        nom="Marc",
        cognoms="Operari F4",
        email=f"op_f4a_{emp_a_id.hex[:6]}@sevalor.cat",
        nif=f"F4A{emp_a_id.hex[:6].upper()}",
        telefon="600111222",
        rol="OPERARI",
        pin_hash="fake",
        password_hash="fake",
        estat="ACTIU",
    )
    eng_a = Usuari(
        id=uuid.uuid4(),
        empresa_id=emp_a_id,
        nom="Laia",
        cognoms="Enginyera F4",
        email=f"eng_f4a_{emp_a_id.hex[:6]}@sevalor.cat",
        nif=f"F4E{emp_a_id.hex[:6].upper()}",
        telefon="600111223",
        rol="ENGINYER",
        pin_hash="fake",
        password_hash="fake",
        estat="ACTIU",
    )
    op_b = Usuari(
        id=uuid.uuid4(),
        empresa_id=emp_b_id,
        nom="Joan",
        cognoms="Operari B",
        email=f"op_f4b_{emp_b_id.hex[:6]}@sevalor.cat",
        nif=f"F4B{emp_b_id.hex[:6].upper()}",
        telefon="600111224",
        rol="OPERARI",
        pin_hash="fake",
        password_hash="fake",
        estat="ACTIU",
    )
    cli_a = Client(
        id=uuid.uuid4(),
        empresa_id=emp_a_id,
        codi=f"CLI-F4-{emp_a_id.hex[:5].upper()}",
        rao_social="Agrícola Ponent SA",
        nif=f"A{emp_a_id.hex[:8].upper()}",
        adreca_fiscal="Camí del Reg 12",
        actiu=True,
    )
    admin_session.add_all([op_a, eng_a, op_b, cli_a])
    await admin_session.flush()

    ot_a = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_a_id,
        client_id=cli_a.id,
        cap_de_colla_id=op_a.id,
        codi=f"OT-F4-{emp_a_id.hex[:5].upper()}",
        titol="Instal·lació bomba immersa Pou Nord",
        adreca="Finca Pou Nord, 1",
        estat="PAUSADA",
        data_planificacio=date.today(),
        hores_imputades_facturables=2.5,
        hora_inici_real=datetime.now(timezone.utc),
    )
    ot_a_offline = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_a_id,
        client_id=cli_a.id,
        cap_de_colla_id=op_a.id,
        codi=f"OT-F4OFF-{emp_a_id.hex[:5].upper()}",
        titol="Manteniment vàlvules sector 4",
        adreca="Finca Sector 4, 2",
        estat="EN_CURS",
        data_planificacio=date.today(),
    )
    admin_session.add_all([ot_a, ot_a_offline])
    await admin_session.commit()

    token_op_a = create_access_token(
        str(op_a.id), "OPERARI", str(emp_a_id), timedelta(minutes=30)
    )
    token_op_b = create_access_token(
        str(op_b.id), "OPERARI", str(emp_b_id), timedelta(minutes=30)
    )

    return {
        "emp_a_id": emp_a_id,
        "emp_b_id": emp_b_id,
        "disc_a": disc_a,
        "op_a_id": op_a.id,
        "eng_a_id": eng_a.id,
        "ot_a_id": ot_a.id,
        "ot_a_offline_id": ot_a_offline.id,
        "headers_op_a": {
            "Authorization": f"Bearer {token_op_a}",
            "X-Empresa-ID": str(emp_a_id),
        },
        "headers_op_b": {
            "Authorization": f"Bearer {token_op_b}",
            "X-Empresa-ID": str(emp_b_id),
        },
    }


@pytest.mark.asyncio
async def test_f4_01_fotos_qa_magic_bytes_reals_i_rebuig_422(setup_fase4_tenants: Dict[str, Any]):
    """ZERO-MOCK: Rebutja fotos buides, absents o falses amb 422 i desa fotos reals al disc sobirà."""
    ctx = setup_fase4_tenants
    ot_id = ctx["ot_a_id"]
    headers = ctx["headers_op_a"]
    disc_a: Path = ctx["disc_a"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # 1. Sense fitxer -> 422 (prohibit WEBP_EVIDENCE_PLACEHOLDER)
        res_missing = await ac.post(
            f"/operari/feines/{ot_id}/fotos",
            data={"tipus": "INICIAL"},
            headers=headers,
        )
        assert res_missing.status_code == 422

        # 2. Fitxer buit -> 422
        res_empty = await ac.post(
            f"/operari/feines/{ot_id}/fotos",
            data={"tipus": "INICIAL"},
            files={"foto": ("empty.webp", b"", "image/webp")},
            headers=headers,
        )
        assert res_empty.status_code == 422

        # 3. Fitxer falsificat (text/SVG amb extensió .webp) -> 422 Magic Bytes
        res_spoof = await ac.post(
            f"/operari/feines/{ot_id}/fotos",
            data={"tipus": "INICIAL"},
            files={
                "foto": (
                    "xss.webp",
                    b"<svg onload=alert(1)></svg>",
                    "image/webp",
                )
            },
            headers=headers,
        )
        assert res_spoof.status_code == 422
        assert "magic bytes" in res_spoof.json()["detail"].lower()

        # 4. Pujar les 3 fotos amb Magic Bytes reals (WebP i PNG)
        for tipus, payload_bytes, mime in [
            ("INICIAL", VALID_WEBP_BYTES, "image/webp"),
            ("INTERMEDIA", VALID_PNG_BYTES, "image/png"),
            ("FINAL", VALID_WEBP_BYTES, "image/webp"),
        ]:
            res_ok = await ac.post(
                f"/operari/feines/{ot_id}/fotos",
                data={"tipus": tipus},
                files={"foto": (f"{tipus.lower()}.webp", payload_bytes, mime)},
                headers=headers,
            )
            assert res_ok.status_code == 200, res_ok.text
            assert res_ok.json()["mida_bytes"] == len(payload_bytes)

        # 5. Verificar protocol complet i persistència física al disc sobirà
        res_status = await ac.get(f"/operari/feines/{ot_id}/fotos", headers=headers)
        assert res_status.status_code == 200
        assert res_status.json()["protocol_complet"] is True

        buffer_dir = disc_a / "06_ordres_treball" / "actives_buffer"
        assert (buffer_dir / f"ot_{ot_id}_foto_inicial.webp").read_bytes() == VALID_WEBP_BYTES
        assert (buffer_dir / f"ot_{ot_id}_foto_intermedia.webp").read_bytes() == VALID_PNG_BYTES
        assert (buffer_dir / f"ot_{ot_id}_foto_final.webp").read_bytes() == VALID_WEBP_BYTES


@pytest.mark.asyncio
async def test_f4_02_finalitzar_feina_signatura_receptor_observacions_i_reconciliacio(
    setup_fase4_tenants: Dict[str, Any],
    admin_session,
):
    """PUT /operari/feines/{id}/finalitzar valida Magic Bytes PNG, desa signatura + receptor + observacions."""
    ctx = setup_fase4_tenants
    ot_id = ctx["ot_a_id"]
    headers = ctx["headers_op_a"]
    disc_a: Path = ctx["disc_a"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        for tipus in ("INICIAL", "INTERMEDIA", "FINAL"):
            r = await ac.post(
                f"/operari/feines/{ot_id}/fotos",
                data={"tipus": tipus},
                files={"foto": (f"{tipus.lower()}.webp", VALID_WEBP_BYTES, "image/webp")},
                headers=headers,
            )
            assert r.status_code == 200

        # 1. Signatura base64 sense Magic Bytes reals -> 422
        bad_b64 = base64.b64encode(b"NOT_A_PNG_FILE").decode("ascii")
        res_bad_sig = await ac.put(
            f"/operari/feines/{ot_id}/finalitzar",
            json={
                "signatura_base64": f"data:image/png;base64,{bad_b64}",
                "nom_receptor": "Pere Puig",
                "dni_receptor": "45678912b",
            },
            headers=headers,
        )
        assert res_bad_sig.status_code == 422

        # 2. Signatura SVG XSS -> 422
        svg_b64 = base64.b64encode(b"<svg onload=alert(1)/>").decode("ascii")
        res_svg = await ac.put(
            f"/operari/feines/{ot_id}/finalitzar",
            json={"signatura_base64": f"data:image/svg+xml;base64,{svg_b64}"},
            headers=headers,
        )
        assert res_svg.status_code == 422

        # 3. Tancament vàlid amb PNG real, nom/DNI receptor i observacions tècniques
        res_ok = await ac.put(
            f"/operari/feines/{ot_id}/finalitzar",
            json={
                "signatura_base64": VALID_PNG_DATA_URI,
                "nom_receptor": "  Pere Puig Soler  ",
                "dni_receptor": " 45678912b ",
                "observacions": "Bomba purgada i provada a 4,2 bar sense fuites.",
                "hores": 2.5,
            },
            headers=headers,
        )
        assert res_ok.status_code == 200, res_ok.text
        body = res_ok.json()
        assert body["estat"] == "COMPLERT"
        assert body["nom_receptor"] == "Pere Puig Soler"
        assert body["dni_receptor"] == "45678912B"
        assert body["observacions_tancament"] == "Bomba purgada i provada a 4,2 bar sense fuites."
        assert body["signatura_client_path"] is not None
        assert body["data_signatura"] is not None

    # 4. Verificar fitxer físic PNG i JSON històric al disc sobirà
    sig_file = disc_a / "06_ordres_treball" / "historic_tancades" / f"ot_{ot_id}_signatura_client.png"
    assert sig_file.exists(), f"Signatura PNG no trobada a {sig_file}"
    assert sig_file.read_bytes() == VALID_PNG_BYTES

    hist_json_file = disc_a / "06_ordres_treball" / "historic_tancades" / f"{ot_id}.json"
    assert hist_json_file.exists()
    hist_data = json.loads(hist_json_file.read_text(encoding="utf-8"))
    assert hist_data["signatura_present"] is True
    assert hist_data["nom_receptor"] == "Pere Puig Soler"
    assert hist_data["dni_receptor"] == "45678912B"
    assert hist_data["observacions"] == "Bomba purgada i provada a 4,2 bar sense fuites."

    # 5. Verificar que ReconciliacioOTService recull totes les evidències per a la Fulla 360°
    await set_tenant_context(admin_session, str(ctx["emp_a_id"]), role="ENGINYER")
    conc = await ReconciliacioOTService.obtenir_conciliacio_completa(
        db=admin_session,
        empresa_id=ctx["emp_a_id"],
        ordre_treball_id=ot_id,
        rol_usuari="ENGINYER",
    )
    assert conc["fotos_qa"]["protocol_complet"] is True
    assert conc["signatura"]["present"] is True
    assert conc["signatura"]["nom_receptor"] == "Pere Puig Soler"
    assert conc["signatura"]["dni_receptor"] == "45678912B"
    assert conc["signatura"]["observacions_tancament"] == "Bomba purgada i provada a 4,2 bar sense fuites."
    assert conc["disclaimer"]["codi"] == "CONCLOSA_PENDENT_VALIDACIO"


@pytest.mark.asyncio
async def test_f4_03_offline_sync_tancar_ordre_persisteix_signatura_i_receptor(
    setup_fase4_tenants: Dict[str, Any],
    admin_session,
):
    """POST /operari_pwa/sync/push amb TANCAR_ORDRE desa signatura PNG, receptor i observacions."""
    ctx = setup_fase4_tenants
    ot_off_id = ctx["ot_a_offline_id"]
    headers = ctx["headers_op_a"]
    disc_a: Path = ctx["disc_a"]

    sync_payload = {
        "accions": [
            {
                "id": str(uuid.uuid4()),
                "accio": "TANCAR_ORDRE",
                "payload": {
                    "ordre_id": str(ot_off_id),
                    "signatura_base64": VALID_PNG_DATA_URI,
                    "nom_receptor": "Marta Serra",
                    "dni_receptor": "39123456z",
                    "observacions": "Tancament offline a finca sense cobertura.",
                    "hores": 1.75,
                },
            }
        ]
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        res = await ac.post("/operari_pwa/sync/push", json=sync_payload, headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["processades"] == 1
        assert data["errors"] == []

    # Verificar persistència física i BD
    sig_file = disc_a / "06_ordres_treball" / "historic_tancades" / f"ot_{ot_off_id}_signatura_client.png"
    assert sig_file.exists()
    assert sig_file.read_bytes() == VALID_PNG_BYTES

    await set_tenant_context(admin_session, str(ctx["emp_a_id"]), role="BOSS")
    ot_row = (
        await admin_session.execute(select(OrdreTreball).where(OrdreTreball.id == ot_off_id))
    ).scalar_one()
    assert ot_row.estat == "COMPLERT"
    assert ot_row.nom_receptor == "Marta Serra"
    assert ot_row.dni_receptor == "39123456Z"
    assert ot_row.observacions_tancament == "Tancament offline a finca sense cobertura."
    assert ot_row.signatura_client_path is not None
    assert ot_row.data_signatura is not None
    assert float(ot_row.hores_imputades_facturables or 0) == pytest.approx(1.75)


@pytest.mark.asyncio
async def test_f4_04_tiquet_captura_rapida_vinculat_ot_i_conciliacio(
    setup_fase4_tenants: Dict[str, Any],
    admin_session,
):
    """POST /operari/tiquets/captura-rapida amb ordre_treball_id vincula el tiquet a la conciliació."""
    ctx = setup_fase4_tenants
    ot_id = ctx["ot_a_id"]
    headers = ctx["headers_op_a"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        res = await ac.post(
            "/operari/tiquets/captura-rapida",
            data={
                "categoria": "FERRETERIA",
                "ordre_treball_id": str(ot_id),
            },
            files={"foto_tiquet": ("tiquet_ferreteria.webp", VALID_WEBP_BYTES, "image/webp")},
            headers=headers,
        )
        assert res.status_code == 201, res.text
        tiq_json = res.json()
        assert tiq_json["ordre_treball_id"] == str(ot_id)
        assert tiq_json["categoria"] == "FERRETERIA"

        # També comprovar sincronització offline CREAR_TIQUET vinculat a ordre_treball_id
        sync_tiq = {
            "accions": [
                {
                    "id": str(uuid.uuid4()),
                    "accio": "CREAR_TIQUET",
                    "payload": {
                        "categoria": "PEATGES",
                        "ordre_treball_id": str(ot_id),
                        "nom_fitxer": "peatge_offline.webp",
                    },
                }
            ]
        }
        res_sync = await ac.post("/operari_pwa/sync/push", json=sync_tiq, headers=headers)
        assert res_sync.status_code == 200, res_sync.text
        assert res_sync.json()["errors"] == []

    await set_tenant_context(admin_session, str(ctx["emp_a_id"]), role="BOSS")
    tiquets_ot = (
        await admin_session.execute(
            select(TiquetDespesa).where(TiquetDespesa.ordre_treball_id == ot_id)
        )
    ).scalars().all()
    assert len(tiquets_ot) == 2
    assert {t.categoria for t in tiquets_ot} == {"FERRETERIA", "PEATGES"}

    conc = await ReconciliacioOTService.obtenir_conciliacio_completa(
        db=admin_session,
        empresa_id=ctx["emp_a_id"],
        ordre_treball_id=ot_id,
        rol_usuari="BOSS",
    )
    assert conc["tiquets"]["total"] == 2
    assert len(conc["tiquets"]["items"]) == 2


@pytest.mark.asyncio
async def test_f4_05_aillament_rls_cross_tenant_tancament_fotos_i_tiquets(
    setup_fase4_tenants: Dict[str, Any],
):
    """RLS: Un operari del Tenant B no pot pujar fotos, tancar ni vincular tiquets a una OT del Tenant A."""
    ctx = setup_fase4_tenants
    ot_a_id = ctx["ot_a_id"]
    headers_b = ctx["headers_op_b"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        res_foto_b = await ac.post(
            f"/operari/feines/{ot_a_id}/fotos",
            data={"tipus": "INICIAL"},
            files={"foto": ("inicial.webp", VALID_WEBP_BYTES, "image/webp")},
            headers=headers_b,
        )
        assert res_foto_b.status_code == 404

        res_fin_b = await ac.put(
            f"/operari/feines/{ot_a_id}/finalitzar",
            json={"signatura_base64": VALID_PNG_DATA_URI, "nom_receptor": "Intrús"},
            headers=headers_b,
        )
        assert res_fin_b.status_code == 404

        res_tiq_b = await ac.post(
            "/operari/tiquets/captura-rapida",
            data={"categoria": "FERRETERIA", "ordre_treball_id": str(ot_a_id)},
            files={"foto_tiquet": ("tiquet.webp", VALID_WEBP_BYTES, "image/webp")},
            headers=headers_b,
        )
        assert res_tiq_b.status_code == 404
