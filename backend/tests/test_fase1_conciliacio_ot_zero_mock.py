"""Tests Fase 1 — Migració a026, ReconciliacioOTService real (Zero Mock), Barrera Econòmica i RLS."""

from __future__ import annotations

import base64
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.models import (
    Article,
    Client,
    Empresa,
    FacturaCapcalera,
    FacturaLinia,
    FullaPicking,
    Incidencia,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    TiquetDespesa,
    Usuari,
)
from app.services.sovereign_storage import inicialitzar_arbre_carpetes_disc

# Imatge PNG 1x1 vàlida (Magic Bytes reals \x89PNG\r\n\x1a\n)
PNG_1X1_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _make_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    payload: dict[str, Any] = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def _seed_tenant(admin_session, disc_root: Path, label: str) -> dict[str, Any]:
    inicialitzar_arbre_carpetes_disc(disc_root)
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    op_id = uuid.uuid4()
    cli_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Empresa {label} S.L.",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini=f"f1-{label.lower()}-{uuid.uuid4().hex[:6]}",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
            node_ia_actiu=True,
        )
    )
    await admin_session.flush()

    for uid, nom_u, rol_u, tel_u in [
        (boss_id, "Boss", "BOSS", "600111222"),
        (eng_id, "Enginyer", "ENGINYER", "600111333"),
        (op_id, "Operari", "OPERARI", "600111444"),
    ]:
        admin_session.add(
            Usuari(
                id=uid,
                empresa_id=emp_id,
                nif=f"{rol_u[0]}{uid.hex[:7].upper()}A",
                nom=nom_u,
                cognoms=label,
                email=f"{rol_u.lower()}-{emp_id.hex[:6]}-{uid.hex[:4]}@sevalor.test",
                telefon=tel_u,
                rol=rol_u,
                pin_hash="fake",
                password_hash="fake",
                estat="ACTIU",
                cost_hora_eur=25.0,
            )
        )

    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"CLI-{uuid.uuid4().hex[:6].upper()}",
            rao_social=f"Client {label} S.A.",
            nif="A" + uuid.uuid4().hex[:8].upper(),
            adreca_fiscal="Carrer Major 1, Girona",
            actiu=True,
        )
    )
    await admin_session.flush()

    return {
        "empresa_id": emp_id,
        "boss_id": boss_id,
        "eng_id": eng_id,
        "op_id": op_id,
        "client_id": cli_id,
        "disc_root": disc_root,
        "headers_boss": {
            "Authorization": f"Bearer {_make_token(boss_id, emp_id, 'BOSS')}",
            "X-Empresa-ID": str(emp_id),
        },
        "headers_eng": {
            "Authorization": f"Bearer {_make_token(eng_id, emp_id, 'ENGINYER')}",
            "X-Empresa-ID": str(emp_id),
        },
    }


@pytest.mark.asyncio
async def test_01_tancar_obra_persisteix_signatura_receptor_i_disc_sobira(
    admin_session, tmp_path: Path
):
    tenant = await _seed_tenant(admin_session, tmp_path / "disc_sig", "Sig")
    ot_id = uuid.uuid4()
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=tenant["empresa_id"],
            codi=f"OT-SIG-{uuid.uuid4().hex[:5].upper()}",
            client_id=tenant["client_id"],
            titol="Revisió quadre elèctric",
            adreca="Polígon Sud 12",
            estat="EN_CURS",
            data_planificacio=date.today(),
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Rebutjar SVG maliciós (XSS) amb 422
        svg_b64 = "data:image/svg+xml;base64," + base64.b64encode(b"<svg onload=alert(1)/>").decode()
        r_bad = await ac.put(
            f"/api/v1/gestio/feines/{ot_id}/tancar-obra",
            json={
                "signatura_base64": svg_b64,
                "conformitat_client": True,
                "nom_receptor": "Pere Client",
                "dni_receptor": "12345678z",
            },
            headers=tenant["headers_boss"],
        )
        assert r_bad.status_code == 422, r_bad.text

        # 2. Tancament vàlid amb PNG real, nom/DNI receptor i observacions
        r_ok = await ac.put(
            f"/api/v1/gestio/feines/{ot_id}/tancar-obra",
            json={
                "signatura_base64": PNG_1X1_B64,
                "conformitat_client": True,
                "nom_receptor": "Pere Client",
                "dni_receptor": "12345678z",
                "observacions": "Instal·lació revisada i conforme",
            },
            headers=tenant["headers_boss"],
        )
        assert r_ok.status_code == 200, r_ok.text
        body = r_ok.json()
        assert body["status"] == "TANCADA"
        assert body["signatura_registrada"] is True
        assert body["nom_receptor"] == "Pere Client"
        assert body["dni_receptor"] == "12345678Z"
        assert body["observacions_tancament"] == "Instal·lació revisada i conforme"
        assert body["signatura_client_path"]

    # Verificar persistència real a PostgreSQL
    ot_db = (
        await admin_session.execute(select(OrdreTreball).where(OrdreTreball.id == ot_id))
    ).scalar_one()
    assert ot_db.signatura_client_path is not None
    assert ot_db.nom_receptor == "Pere Client"
    assert ot_db.dni_receptor == "12345678Z"
    assert ot_db.observacions_tancament == "Instal·lació revisada i conforme"
    assert ot_db.data_signatura is not None

    # Verificar fitxer PNG binari real al disc sobirà
    sig_file = (
        tenant["disc_root"]
        / "06_ordres_treball"
        / "historic_tancades"
        / f"ot_{ot_id}_signatura_client.png"
    )
    assert sig_file.is_file(), f"Signatura no trobada al disc sobirà: {sig_file}"
    assert sig_file.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_02_reconciliacio_dia_zero_sense_constants_hardcodejades(
    admin_session, tmp_path: Path
):
    tenant = await _seed_tenant(admin_session, tmp_path / "disc_d0", "DiaZero")
    ot_id = uuid.uuid4()
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=tenant["empresa_id"],
            codi=f"OT-D0-{uuid.uuid4().hex[:5].upper()}",
            client_id=tenant["client_id"],
            titol="OT Dia Zero neta",
            adreca="Carrer Nou 5",
            estat="PENDENT",
            data_planificacio=date.today(),
            import_pressupostat=0.0,
            preu_venda_hora_aplicat=0.0,
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_feina = await ac.post(
            f"/api/v1/gestio/feines/{ot_id}/reconciliacio-post-obra",
            headers=tenant["headers_boss"],
        )
        assert r_feina.status_code == 200, r_feina.text
        d_f = r_feina.json()
        assert d_f["previst"]["import_pressupostat"] == 0.0
        assert d_f["previst"]["cost_materials"] == 0.0
        assert d_f["real"]["cost_materials"] == 0.0
        assert d_f["real"]["cost_total"] == 0.0
        assert d_f["marge_real"] == 0.0
        assert d_f["marge_percentatge"] == 0.0
        assert d_f["conciliacio"]["disclaimer"]["codi"] == "NO_CONCLOSA"

        r_cop = await ac.post(
            "/api/v1/gestio/copilot/reconciliacio/post-obra",
            json={"ordre_treball_id": str(ot_id)},
            headers=tenant["headers_boss"],
        )
        assert r_cop.status_code == 200, r_cop.text
        d_c = r_cop.json()
        prop = d_c["pressupost_corregit_proposta"]
        # Zero Mock Data: cap constant 1200.00, 145.00, 35.0 ni marge 30.0
        assert prop["partides_inicials"] == 0.0
        assert prop["desviacio_materials_import"] == 0.0
        assert prop["desviacio_ma_obra_import"] == 0.0
        assert prop["total_proposat_corregit"] == 0.0
        assert d_c["marge_previst_percentatge"] == 0.0
        assert d_c["marge_real_liquidat_percentatge"] == 0.0


@pytest.mark.asyncio
async def test_03_reconciliacio_real_i_barrera_economica_enginyer_vs_boss(
    admin_session, tmp_path: Path
):
    tenant = await _seed_tenant(admin_session, tmp_path / "disc_rbac", "Rbac")
    emp_id = tenant["empresa_id"]
    ot_id = uuid.uuid4()
    mag_id = uuid.uuid4()
    art_id = uuid.uuid4()
    fp_id = uuid.uuid4()
    fact_id = uuid.uuid4()

    admin_session.add(
        Magatzem(
            id=mag_id,
            empresa_id=emp_id,
            nom="Furgoneta 1234-ABC",
            tipus="FURGONETA",
            actiu=True,
        )
    )
    admin_session.add(
        Article(
            id=art_id,
            empresa_id=emp_id,
            referencia_inventari=f"REF-{uuid.uuid4().hex[:6].upper()}",
            nom="Tub PE 32mm",
            unitat_mesura="METRES",
            preu_cost=20.0,
            preu_cost_mitja=20.0,
            preu_venda=40.0,
        )
    )
    admin_session.add(
        FacturaCapcalera(
            id=fact_id,
            empresa_id=emp_id,
            numero_factura=901,
            serie="PRE",
            client_id=tenant["client_id"],
            base_imposable=600.0,
            quota_iva=126.0,
            liquid_exigible=726.0,
            estat_document="ESBORRANY_PREFACTURA",
            estat_cobrament="PENDENT",
            hash_sha256="a" * 64,
        )
    )
    await admin_session.flush()

    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=emp_id,
            codi=f"OT-REAL-{uuid.uuid4().hex[:5].upper()}",
            client_id=tenant["client_id"],
            cap_de_colla_id=tenant["op_id"],
            titol="Muntatge reg degoteig",
            adreca="Camí del Mas 8",
            estat="COMPLERT",
            data_planificacio=date.today(),
            data_finalitzacio_camp=date.today(),
            import_pressupostat=1000.0,
            preu_venda_hora_aplicat=50.0,
            hores_imputades_facturables=4.0,
            cost_ma_obra_real=100.0,
            km_imputats=40,
            factura_id=fact_id,
        )
    )
    await admin_session.flush()

    admin_session.add(
        FacturaLinia(
            empresa_id=emp_id,
            factura_id=fact_id,
            obra_id=ot_id,
            article_id=art_id,
            concepte="Mà d'obra i tub PE",
            quantitat=1.0,
            preu_venda_unitari=600.0,
            tipus_iva=21.0,
            subtotal=600.0,
            cost_unitari_historic=200.0,
        )
    )
    admin_session.add(
        FullaPicking(
            id=fp_id,
            empresa_id=emp_id,
            ordre_treball_id=ot_id,
            estat_picking="TANCAT",
        )
    )
    await admin_session.flush()
    admin_session.add(
        LiniaPicking(
            empresa_id=emp_id,
            picking_id=fp_id,
            article_id=art_id,
            magatzem_id=mag_id,
            quantitat_prevista=10.0,
            quantitat_carregada_pick_in=12.0,
            quantitat_retornada_pick_out=2.0,
            quantitat_mermada=1.0,
            origen_estoc="FURGONETA",
            consum_aplicat_magatzem=11.0,
        )
    )
    admin_session.add(
        TiquetDespesa(
            empresa_id=emp_id,
            categoria="FERRETERIA",
            usuari_id=tenant["op_id"],
            ordre_treball_id=ot_id,
            data_tiquet=date.today(),
            rao_social="Ferreteria Local SL",
            base_imposable=24.79,
            iva_pct=21.0,
            quota_iva=5.21,
            import_total=30.0,
            subcompte_pgc="629000",
        )
    )
    admin_session.add(
        Incidencia(
            empresa_id=emp_id,
            ordre_treball_id=ot_id,
            operari_id=tenant["op_id"],
            ambit="TASCA",
            estat="VERMELL",
            text_observacions="Arqueta obstruïda",
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. ENGINYER: veu dades tècniques + dades comercials client (pressupost, PVP, factura), MAI costos interns ni marges
        r_eng = await ac.post(
            f"/api/v1/gestio/feines/{ot_id}/reconciliacio-post-obra",
            headers=tenant["headers_eng"],
        )
        assert r_eng.status_code == 200, r_eng.text
        d_eng = r_eng.json()
        assert d_eng["previst"]["import_pressupostat"] == 1000.0
        assert d_eng["real"]["hores"] == 4.0
        assert d_eng["real"]["valor_ma_obra_pvp"] == 200.0
        assert d_eng["real"]["valor_materials_pvp"] == 400.0  # (12 - 2) * 40 PVP
        assert d_eng["real"]["total_valorat_pvp"] == 600.0
        assert d_eng["conciliacio"]["factura"]["liquid_exigible"] == 726.0
        assert d_eng["conciliacio"]["materials"]["linies"][0]["origen_estoc"] == "FURGONETA"
        assert d_eng["conciliacio"]["materials"]["linies"][0]["consum_real"] == 10.0
        assert d_eng["conciliacio"]["materials"]["linies"][0]["preu_cost_pmp"] is None
        assert d_eng["conciliacio"]["incidencies"]["total"] == 1
        assert d_eng["conciliacio"]["tiquets"]["total"] == 1
        assert "subcompte_pgc" not in d_eng["conciliacio"]["tiquets"]["items"][0]
        # Barrera Econòmica interna infranquejable
        assert d_eng["previst"]["cost_materials"] is None
        assert d_eng["real"]["cost_materials"] is None
        assert d_eng["real"]["cost_ma_obra"] is None
        assert d_eng["real"]["cost_total"] is None
        assert d_eng["marge_real"] is None
        assert d_eng["marge_percentatge"] is None
        assert d_eng["bloqueig_facturacio_directa"] is None

        # 2. BOSS: veu costos reals (PMP + merma + mà d'obra + tiquets) i marge real
        r_boss = await ac.post(
            f"/api/v1/gestio/feines/{ot_id}/reconciliacio-post-obra",
            headers=tenant["headers_boss"],
        )
        assert r_boss.status_code == 200, r_boss.text
        d_boss = r_boss.json()
        assert d_boss["real"]["cost_materials"] == 200.0  # 10 * 20 PMP
        assert d_boss["real"]["cost_ma_obra"] == 100.0
        assert d_boss["conciliacio"]["resum_intern"]["cost_mermes_pmp"] == 20.0  # 1 * 20 PMP
        assert d_boss["real"]["cost_total"] == 350.0  # 200 + 20 + 100 + 30
        assert d_boss["marge_real"] == 250.0  # 600 base factura - 350 cost total
        assert d_boss["marge_percentatge"] == pytest.approx(41.67, abs=0.01)
        assert d_boss["bloqueig_facturacio_directa"] is False

        # 3. Copilot reconciliacio/post-obra respecta Barrera Econòmica per ENGINYER i dades reals per BOSS
        r_cop_eng = await ac.post(
            "/api/v1/gestio/copilot/reconciliacio/post-obra",
            json={"ordre_treball_id": str(ot_id)},
            headers=tenant["headers_eng"],
        )
        assert r_cop_eng.status_code == 200, r_cop_eng.text
        assert r_cop_eng.json()["marge_previst_percentatge"] is None
        assert r_cop_eng.json()["marge_real_liquidat_percentatge"] is None
        assert r_cop_eng.json()["pressupost_corregit_proposta"]["partides_inicials"] == 1000.0

        r_cop_boss = await ac.post(
            "/api/v1/gestio/copilot/reconciliacio/post-obra",
            json={"ordre_treball_id": str(ot_id)},
            headers=tenant["headers_boss"],
        )
        assert r_cop_boss.status_code == 200, r_cop_boss.text
        assert r_cop_boss.json()["marge_previst_percentatge"] == 80.0  # (1000 - 200) / 1000
        assert r_cop_boss.json()["marge_real_liquidat_percentatge"] == 65.0  # (1000 - 350) / 1000


@pytest.mark.asyncio
async def test_04_rls_multi_tenant_aillament_conciliacio_i_tancar_obra(
    admin_session, tmp_path: Path
):
    tenant_a = await _seed_tenant(admin_session, tmp_path / "disc_rls_a", "RlsA")
    tenant_b = await _seed_tenant(admin_session, tmp_path / "disc_rls_b", "RlsB")

    ot_a_id = uuid.uuid4()
    admin_session.add(
        OrdreTreball(
            id=ot_a_id,
            empresa_id=tenant_a["empresa_id"],
            codi=f"OT-RLSA-{uuid.uuid4().hex[:5].upper()}",
            client_id=tenant_a["client_id"],
            titol="OT Confidencial A",
            adreca="Carrer Secret 1",
            estat="COMPLERT",
            data_planificacio=date.today(),
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r1 = await ac.post(
            f"/api/v1/gestio/feines/{ot_a_id}/reconciliacio-post-obra",
            headers=tenant_b["headers_boss"],
        )
        assert r1.status_code == 404, r1.text

        r2 = await ac.put(
            f"/api/v1/gestio/feines/{ot_a_id}/tancar-obra",
            json={"signatura_base64": PNG_1X1_B64, "conformitat_client": True},
            headers=tenant_b["headers_boss"],
        )
        assert r2.status_code == 404, r2.text

        r3 = await ac.post(
            "/api/v1/gestio/copilot/reconciliacio/post-obra",
            json={"ordre_treball_id": str(ot_a_id)},
            headers=tenant_b["headers_boss"],
        )
        assert r3.status_code == 404, r3.text
