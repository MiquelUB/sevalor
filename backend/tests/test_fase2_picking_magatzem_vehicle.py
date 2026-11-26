"""Tests Fase 2 — Picking/Pick-Out real sobre EstocMagatzem, MermaInventari i Magatzem de Vehicle (Furgoneta)."""

from __future__ import annotations

import asyncio
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
    EstocMagatzem,
    FullaPicking,
    LiniaPicking,
    Magatzem,
    MermaInventari,
    MovimentEstoc,
    OrdreTreball,
    Usuari,
    Vehicle,
)
from app.services.sovereign_storage import inicialitzar_arbre_carpetes_disc


def _make_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    payload: dict[str, Any] = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def _seed_tenant_picking(admin_session, disc_root: Path, label: str) -> dict[str, Any]:
    inicialitzar_arbre_carpetes_disc(disc_root)
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    veh_id = uuid.uuid4()
    mag_nau_id = uuid.uuid4()
    mag_van_id = uuid.uuid4()
    art_id = uuid.uuid4()
    ot_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Empresa Pick {label} S.L.",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini=f"f2-{label.lower()}-{uuid.uuid4().hex[:6]}",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
            node_ia_actiu=True,
        )
    )
    await admin_session.flush()

    admin_session.add(
        Magatzem(
            id=mag_nau_id,
            empresa_id=emp_id,
            nom="Nau Central",
            tipus="NAU_CENTRAL",
            actiu=True,
        )
    )
    admin_session.add(
        Vehicle(
            id=veh_id,
            empresa_id=emp_id,
            matricula=f"{uuid.uuid4().int % 9000 + 1000}ABC",
            marca="Ford",
            model="Transit",
            tipus="THERMIC",
            estat="OPERATIU",
        )
    )
    await admin_session.flush()

    admin_session.add(
        Magatzem(
            id=mag_van_id,
            empresa_id=emp_id,
            nom="Furgoneta Ford Transit",
            tipus="FURGONETA",
            vehicle_id=veh_id,
            actiu=True,
        )
    )
    admin_session.add(
        Usuari(
            id=op_id,
            empresa_id=emp_id,
            nif=f"O{op_id.hex[:7].upper()}P",
            nom="Operari",
            cognoms=label,
            email=f"op-{emp_id.hex[:6]}@sevalor.test",
            telefon="611222333",
            rol="OPERARI",
            pin_hash="fake",
            password_hash="fake",
            estat="ACTIU",
            vehicle_assignat_id=veh_id,
        )
    )
    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"CLI-{uuid.uuid4().hex[:6].upper()}",
            rao_social=f"Client {label} S.A.",
            nif="A" + uuid.uuid4().hex[:8].upper(),
            adreca_fiscal="Carrer Indústria 4, Lleida",
            actiu=True,
        )
    )
    admin_session.add(
        Article(
            id=art_id,
            empresa_id=emp_id,
            referencia_inventari=f"TUB-{uuid.uuid4().hex[:6].upper()}",
            nom="Tub PE 32mm",
            unitat_mesura="METRES_LINEALS",
            es_material_continu=True,
            preu_cost=10.0,
            preu_cost_mitja=10.0,
            pmp_actual=10.0,
            preu_venda=25.0,
            estoc_total_actual=115.0,
        )
    )
    await admin_session.flush()

    admin_session.add(
        EstocMagatzem(
            empresa_id=emp_id,
            article_id=art_id,
            magatzem_id=mag_nau_id,
            quantitat_fisica=100.0,
            quantitat_virtual_reservada=10.0,
            quantitat_cuarentena=0.0,
        )
    )
    admin_session.add(
        EstocMagatzem(
            empresa_id=emp_id,
            article_id=art_id,
            magatzem_id=mag_van_id,
            quantitat_fisica=15.0,
            quantitat_virtual_reservada=0.0,
            quantitat_cuarentena=0.0,
        )
    )
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=emp_id,
            codi=f"OT-F2-{uuid.uuid4().hex[:5].upper()}",
            client_id=cli_id,
            cap_de_colla_id=op_id,
            vehicle_id=veh_id,
            titol="Reparació reg sector nord",
            adreca="Finca Nord 1",
            estat="EN_CURS",
            data_planificacio=date.today(),
        )
    )
    await admin_session.flush()

    return {
        "empresa_id": emp_id,
        "op_id": op_id,
        "client_id": cli_id,
        "vehicle_id": veh_id,
        "mag_nau_id": mag_nau_id,
        "mag_van_id": mag_van_id,
        "article_id": art_id,
        "ot_id": ot_id,
        "headers_op": {
            "Authorization": f"Bearer {_make_token(op_id, emp_id, 'OPERARI')}",
            "X-Empresa-ID": str(emp_id),
        },
    }


@pytest.mark.asyncio
async def test_01_pick_in_i_pick_out_actualitza_estoc_moviments_merma_i_ot(
    admin_session, tmp_path: Path
):
    t = await _seed_tenant_picking(admin_session, tmp_path / "disc_p1", "P1")
    fp_id = uuid.uuid4()
    lin_id = uuid.uuid4()

    admin_session.add(
        FullaPicking(
            id=fp_id,
            empresa_id=t["empresa_id"],
            ordre_treball_id=t["ot_id"],
            vehicle_id=t["vehicle_id"],
            estat_picking="PENDENT",
        )
    )
    await admin_session.flush()
    admin_session.add(
        LiniaPicking(
            id=lin_id,
            empresa_id=t["empresa_id"],
            picking_id=fp_id,
            article_id=t["article_id"],
            magatzem_id=t["mag_nau_id"],
            quantitat_prevista=10.0,
            quantitat_carregada_pick_in=0.0,
            quantitat_retornada_pick_out=0.0,
            quantitat_mermada=0.0,
            origen_estoc="NAU",
            consum_aplicat_magatzem=0.0,
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Pick-In: 10 metres carregats
        r_in = await ac.put(
            f"/api/v1/operari/picking/linies/{lin_id}",
            json={"quantitat_carregada_pick_in": 10.0},
            headers=t["headers_op"],
        )
        assert r_in.status_code == 200, r_in.text
        assert r_in.json()["estoc_actualitzat"] is False

        # 2. Pick-Out: retorna 2m intactes i declara 1m de merma -> baixa física = 8m (7 instal·lats + 1 merma)
        r_out = await ac.put(
            f"/api/v1/operari/picking/linies/{lin_id}",
            json={
                "quantitat_retornada_pick_out": 2.0,
                "quantitat_mermada": 1.0,
            },
            headers=t["headers_op"],
        )
        assert r_out.status_code == 200, r_out.text
        body = r_out.json()
        assert body["consum_real"] == 8.0
        assert body["consum_aplicat_magatzem"] == 8.0
        assert body["estoc_actualitzat"] is True

    # Verificar PostgreSQL real: EstocMagatzem, MovimentEstoc, MermaInventari i OrdreTreball
    estoc_nau = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == t["empresa_id"],
                EstocMagatzem.magatzem_id == t["mag_nau_id"],
                EstocMagatzem.article_id == t["article_id"],
            )
        )
    ).scalar_one()
    assert float(estoc_nau.quantitat_virtual_reservada) == 0.0
    assert float(estoc_nau.quantitat_fisica) == 92.0  # 100 - 8
    assert float(estoc_nau.quantitat_cuarentena) == 1.0

    movs = (
        await admin_session.execute(
            select(MovimentEstoc).where(
                MovimentEstoc.empresa_id == t["empresa_id"],
                MovimentEstoc.magatzem_id == t["mag_nau_id"],
            )
        )
    ).scalars().all()
    tipus_movs = {m.tipus_moviment: float(m.quantitat) for m in movs}
    assert tipus_movs["SORTIDA"] == 8.0
    assert tipus_movs["MERMA"] == 1.0

    merma = (
        await admin_session.execute(
            select(MermaInventari).where(
                MermaInventari.empresa_id == t["empresa_id"],
                MermaInventari.ordre_treball_id == t["ot_id"],
            )
        )
    ).scalar_one()
    assert float(merma.quantitat) == 1.0
    assert float(merma.cost_total) == 10.0  # 1 * 10 PMP

    ot_db = (
        await admin_session.execute(select(OrdreTreball).where(OrdreTreball.id == t["ot_id"]))
    ).scalar_one()
    assert float(ot_db.cost_materials_pmp) == 80.0  # 8 * 10 PMP
    assert float(ot_db.pvp_materials_aplicat) == 175.0  # (8 - 1 merma) * 25 PVP


@pytest.mark.asyncio
async def test_02_pick_out_idempotent_i_validacio_limits(admin_session, tmp_path: Path):
    t = await _seed_tenant_picking(admin_session, tmp_path / "disc_p2", "P2")
    fp_id = uuid.uuid4()
    lin_id = uuid.uuid4()

    admin_session.add(
        FullaPicking(
            id=fp_id,
            empresa_id=t["empresa_id"],
            ordre_treball_id=t["ot_id"],
            estat_picking="EN_CURS",
        )
    )
    await admin_session.flush()
    admin_session.add(
        LiniaPicking(
            id=lin_id,
            empresa_id=t["empresa_id"],
            picking_id=fp_id,
            article_id=t["article_id"],
            magatzem_id=t["mag_nau_id"],
            quantitat_prevista=10.0,
            quantitat_carregada_pick_in=10.0,
            quantitat_retornada_pick_out=0.0,
            quantitat_mermada=0.0,
            origen_estoc="NAU",
            consum_aplicat_magatzem=0.0,
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Rebutjar retorn + merma > carregat (422)
        r_err = await ac.put(
            f"/api/v1/operari/picking/linies/{lin_id}",
            json={"quantitat_retornada_pick_out": 8.0, "quantitat_mermada": 4.0},
            headers=t["headers_op"],
        )
        assert r_err.status_code == 422, r_err.text

        # 2. Primer Pick-Out: retorn 2m, merma 1m -> física 92m
        r1 = await ac.put(
            f"/api/v1/operari/picking/linies/{lin_id}",
            json={"quantitat_retornada_pick_out": 2.0, "quantitat_mermada": 1.0},
            headers=t["headers_op"],
        )
        assert r1.status_code == 200, r1.text

        # 3. Reenviament idèntic -> NO pot descomptar de nou!
        r2 = await ac.put(
            f"/api/v1/operari/picking/linies/{lin_id}",
            json={"quantitat_retornada_pick_out": 2.0, "quantitat_mermada": 1.0},
            headers=t["headers_op"],
        )
        assert r2.status_code == 200, r2.text

        # 4. Correcció de retorn de 2m -> 4m (delta = -2m -> retorna 2m a estoc físic = 94m)
        r3 = await ac.put(
            f"/api/v1/operari/picking/linies/{lin_id}",
            json={"quantitat_retornada_pick_out": 4.0, "quantitat_mermada": 1.0},
            headers=t["headers_op"],
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["consum_aplicat_magatzem"] == 6.0

    estoc_nau = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == t["empresa_id"],
                EstocMagatzem.magatzem_id == t["mag_nau_id"],
                EstocMagatzem.article_id == t["article_id"],
            )
        )
    ).scalar_one()
    assert float(estoc_nau.quantitat_fisica) == 94.0
    assert float(estoc_nau.quantitat_virtual_reservada) == 0.0


@pytest.mark.asyncio
async def test_03_consum_magatzem_furgoneta_i_comptabilitzacio_ot(
    admin_session, tmp_path: Path
):
    t = await _seed_tenant_picking(admin_session, tmp_path / "disc_van", "Van")
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Consultar estoc real del vehicle assignat a l'OT
        r_stock = await ac.get(
            f"/api/v1/operari/picking/vehicle-stock?ordre_treball_id={t['ot_id']}",
            headers=t["headers_op"],
        )
        assert r_stock.status_code == 200, r_stock.text
        st = r_stock.json()
        assert st["magatzem_id"] == str(t["mag_van_id"])
        assert len(st["items"]) == 1
        assert st["items"][0]["quantitat_disponible"] == 15.0

        # 2. Agafar 4m de la furgoneta (0.5m merma)
        r_use = await ac.post(
            "/api/v1/operari/picking/consum-vehicle",
            json={
                "ordre_treball_id": str(t["ot_id"]),
                "article_id": str(t["article_id"]),
                "quantitat": 4.0,
                "quantitat_mermada": 0.5,
                "notes": "Tram addicional arqueta 3",
            },
            headers=t["headers_op"],
        )
        assert r_use.status_code == 201, r_use.text
        u = r_use.json()
        assert u["origen_estoc"] == "FURGONETA"
        assert u["quantitat_consumida"] == 4.0
        assert u["estoc_restant_furgoneta"] == 11.0
        # Zero exposició de preus/costos a l'operari
        assert "pvp_materials_ot" not in u
        assert "cost_materials_pmp_ot" not in u

        # 3. Intentar agafar més del disponible (20 > 11) -> 422
        r_over = await ac.post(
            "/api/v1/operari/picking/consum-vehicle",
            json={
                "ordre_treball_id": str(t["ot_id"]),
                "article_id": str(t["article_id"]),
                "quantitat": 20.0,
            },
            headers=t["headers_op"],
        )
        assert r_over.status_code == 422, r_over.text

    # Comprovar BD: estoc furgoneta, LiniaPicking FURGONETA i totals de l'OT
    estoc_van = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == t["empresa_id"],
                EstocMagatzem.magatzem_id == t["mag_van_id"],
                EstocMagatzem.article_id == t["article_id"],
            )
        )
    ).scalar_one()
    assert float(estoc_van.quantitat_fisica) == 11.0
    assert float(estoc_van.quantitat_cuarentena) == 0.5

    linia_van = (
        await admin_session.execute(
            select(LiniaPicking).where(
                LiniaPicking.empresa_id == t["empresa_id"],
                LiniaPicking.origen_estoc == "FURGONETA",
            )
        )
    ).scalar_one()
    assert float(linia_van.quantitat_prevista) == 0.0
    assert float(linia_van.quantitat_carregada_pick_in) == 4.0
    assert float(linia_van.consum_aplicat_magatzem) == 4.0

    ot_db = (
        await admin_session.execute(select(OrdreTreball).where(OrdreTreball.id == t["ot_id"]))
    ).scalar_one()
    assert float(ot_db.cost_materials_pmp) == 40.0  # 4.0 * 10 PMP
    assert float(ot_db.pvp_materials_aplicat) == 87.5  # (4.0 - 0.5 merma) * 25 PVP


@pytest.mark.asyncio
async def test_04_offline_sync_use_material_from_van(admin_session, tmp_path: Path):
    t = await _seed_tenant_picking(admin_session, tmp_path / "disc_sync", "Sync")
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_sync = await ac.post(
            "/api/v1/sync/push",
            json={
                "accions": [
                    {
                        "id": f"act-{uuid.uuid4().hex[:6]}",
                        "accio": "USE_MATERIAL_FROM_VAN",
                        "payload": {
                            "ordre_treball_id": str(t["ot_id"]),
                            "article_id": str(t["article_id"]),
                            "quantitat": 3.0,
                            "magatzem_id": str(t["mag_van_id"]),
                            "notes": "Consum offline zona blanca",
                        },
                    }
                ]
            },
            headers=t["headers_op"],
        )
        assert r_sync.status_code == 200, r_sync.text
        data = r_sync.json()
        assert data["processades"] == 1
        assert data["errors"] == []

    estoc_van = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == t["empresa_id"],
                EstocMagatzem.magatzem_id == t["mag_van_id"],
                EstocMagatzem.article_id == t["article_id"],
            )
        )
    ).scalar_one()
    assert float(estoc_van.quantitat_fisica) == 12.0  # 15 - 3


@pytest.mark.asyncio
async def test_05_rls_aillament_estoc_furgoneta_i_picking(admin_session, tmp_path: Path):
    ta = await _seed_tenant_picking(admin_session, tmp_path / "disc_rls_f2_a", "RlsA")
    tb = await _seed_tenant_picking(admin_session, tmp_path / "disc_rls_f2_b", "RlsB")

    fp_a = uuid.uuid4()
    lin_a = uuid.uuid4()
    admin_session.add(
        FullaPicking(
            id=fp_a,
            empresa_id=ta["empresa_id"],
            ordre_treball_id=ta["ot_id"],
            estat_picking="PENDENT",
        )
    )
    await admin_session.flush()
    admin_session.add(
        LiniaPicking(
            id=lin_a,
            empresa_id=ta["empresa_id"],
            picking_id=fp_a,
            article_id=ta["article_id"],
            magatzem_id=ta["mag_nau_id"],
            quantitat_prevista=5.0,
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Tenant B intenta modificar línia de picking de Tenant A -> 404
        r_lin = await ac.put(
            f"/api/v1/operari/picking/linies/{lin_a}",
            json={"quantitat_carregada_pick_in": 5.0, "quantitat_retornada_pick_out": 0.0},
            headers=tb["headers_op"],
        )
        assert r_lin.status_code == 404, r_lin.text

        # Tenant B intenta agafar material de la furgoneta d'una OT de Tenant A -> 404
        r_van = await ac.post(
            "/api/v1/operari/picking/consum-vehicle",
            json={
                "ordre_treball_id": str(ta["ot_id"]),
                "article_id": str(ta["article_id"]),
                "quantitat": 2.0,
            },
            headers=tb["headers_op"],
        )
        assert r_van.status_code == 404, r_van.text

        # Estoc furgoneta de Tenant A intacte (15.0)
        r_stock_a = await ac.get(
            f"/api/v1/operari/picking/vehicle-stock?ordre_treball_id={ta['ot_id']}",
            headers=ta["headers_op"],
        )
        assert r_stock_a.status_code == 200, r_stock_a.text
        assert r_stock_a.json()["items"][0]["quantitat_disponible"] == 15.0


@pytest.mark.asyncio
async def test_06_pick_in_i_pick_out_concurrents_sense_stale_data_error(tmp_path: Path):
    """Dues peticions PUT simultànies (en dues connexions reals de PostgreSQL) sobre la mateixa OT
    amb optimistic locking (`OrdreTreball.versio`) han de serialitzar-se netament sense StaleDataError."""
    from sqlalchemy import text

    from app.core.db import AsyncSessionLocal

    emp_id: uuid.UUID | None = None
    saved_overrides = dict(app.dependency_overrides)
    try:
        async with AsyncSessionLocal() as s_seed:
            await s_seed.execute(text("RESET ROLE;"))
            t = await _seed_tenant_picking(s_seed, tmp_path / "disc_conc", "Conc")
            emp_id = t["empresa_id"]
            art2_id = uuid.uuid4()
            fp_id = uuid.uuid4()
            lin1_id = uuid.uuid4()
            lin2_id = uuid.uuid4()

            # Forçar estoc_minim elevat perquè també s'executi avaluar_i_sincronitzar_alertes_recompra
            art1 = (
                await s_seed.execute(select(Article).where(Article.id == t["article_id"]))
            ).scalar_one()
            art1.estoc_minim = 200.0

            s_seed.add(
                Article(
                    id=art2_id,
                    empresa_id=t["empresa_id"],
                    referencia_inventari=f"VALV-{uuid.uuid4().hex[:6].upper()}",
                    nom="Vàlvula esfera 32mm",
                    unitat_mesura="UNITAT",
                    es_material_continu=False,
                    preu_cost=12.0,
                    preu_cost_mitja=12.0,
                    pmp_actual=12.0,
                    preu_venda=30.0,
                    estoc_minim=50.0,
                    estoc_total_actual=20.0,
                )
            )
            await s_seed.flush()
            s_seed.add(
                EstocMagatzem(
                    empresa_id=t["empresa_id"],
                    article_id=art2_id,
                    magatzem_id=t["mag_nau_id"],
                    quantitat_fisica=20.0,
                    quantitat_virtual_reservada=4.0,
                    quantitat_cuarentena=0.0,
                )
            )
            s_seed.add(
                FullaPicking(
                    id=fp_id,
                    empresa_id=t["empresa_id"],
                    ordre_treball_id=t["ot_id"],
                    vehicle_id=t["vehicle_id"],
                    estat_picking="PENDENT",
                )
            )
            await s_seed.flush()
            s_seed.add(
                LiniaPicking(
                    id=lin1_id,
                    empresa_id=t["empresa_id"],
                    picking_id=fp_id,
                    article_id=t["article_id"],
                    magatzem_id=t["mag_nau_id"],
                    quantitat_prevista=6.0,
                )
            )
            s_seed.add(
                LiniaPicking(
                    id=lin2_id,
                    empresa_id=t["empresa_id"],
                    picking_id=fp_id,
                    article_id=art2_id,
                    magatzem_id=t["mag_nau_id"],
                    quantitat_prevista=4.0,
                )
            )
            await s_seed.commit()

        # Usar sessions reals independents per petició (igual que en producció)
        app.dependency_overrides.clear()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r1, r2 = await asyncio.gather(
                ac.put(
                    f"/api/v1/operari/picking/linies/{lin1_id}",
                    json={"quantitat_carregada_pick_in": 6.0},
                    headers=t["headers_op"],
                ),
                ac.put(
                    f"/api/v1/operari/picking/linies/{lin2_id}",
                    json={"quantitat_carregada_pick_in": 4.0},
                    headers=t["headers_op"],
                ),
            )
            assert r1.status_code == 200, r1.text
            assert r2.status_code == 200, r2.text

            # Verificar que GET /operari/materials retorna tots 2 confirmats realment a BD
            r_mat = await ac.get(
                f"/api/v1/operari/materials?ordre_treball_id={t['ot_id']}",
                headers=t["headers_op"],
            )
            assert r_mat.status_code == 200, r_mat.text
            mats = r_mat.json()
            assert len(mats) == 2
            assert all(m["carregat_pick_in"] is True for m in mats)

            # També Pick-Out concurrent de totes dues línies sense StaleDataError
            o1, o2 = await asyncio.gather(
                ac.put(
                    f"/api/v1/operari/picking/linies/{lin1_id}",
                    json={
                        "quantitat_carregada_pick_in": 6.0,
                        "quantitat_retornada_pick_out": 1.0,
                        "quantitat_mermada": 0.0,
                    },
                    headers=t["headers_op"],
                ),
                ac.put(
                    f"/api/v1/operari/picking/linies/{lin2_id}",
                    json={
                        "quantitat_carregada_pick_in": 4.0,
                        "quantitat_retornada_pick_out": 1.0,
                        "quantitat_mermada": 0.0,
                    },
                    headers=t["headers_op"],
                ),
            )
            assert o1.status_code == 200, o1.text
            assert o2.status_code == 200, o2.text

        # Comprovar totals reals recalculats a l'OT: (5*10 + 3*12 = 86 PMP; 5*25 + 3*30 = 215 PVP)
        async with AsyncSessionLocal() as s_chk:
            await s_chk.execute(text("RESET ROLE;"))
            ot_db = (
                await s_chk.execute(select(OrdreTreball).where(OrdreTreball.id == t["ot_id"]))
            ).scalar_one()
            assert float(ot_db.cost_materials_pmp) == 86.0
            assert float(ot_db.pvp_materials_aplicat) == 215.0
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved_overrides)
        if emp_id is not None:
            async with AsyncSessionLocal() as s_del:
                await s_del.execute(text("RESET ROLE;"))
                await s_del.execute(text("DELETE FROM empreses WHERE id = :id"), {"id": emp_id})
                await s_del.commit()


@pytest.mark.asyncio
async def test_07_batch_picking_atomic_rollback_i_rls(admin_session, tmp_path: Path):
    """PUT /operari/picking/linies/batch és atòmic (tot o res) i aplica aïllament RLS estricte."""
    ta = await _seed_tenant_picking(admin_session, tmp_path / "disc_batch_a", "BatchA")
    tb = await _seed_tenant_picking(admin_session, tmp_path / "disc_batch_b", "BatchB")

    art2_id = uuid.uuid4()
    fp_id = uuid.uuid4()
    lin1_id = uuid.uuid4()
    lin2_id = uuid.uuid4()

    admin_session.add(
        Article(
            id=art2_id,
            empresa_id=ta["empresa_id"],
            referencia_inventari=f"COLZ-{uuid.uuid4().hex[:6].upper()}",
            nom="Colze 90º PE 32mm",
            unitat_mesura="UNITAT",
            preu_cost=4.0,
            preu_cost_mitja=4.0,
            pmp_actual=4.0,
            preu_venda=9.0,
            estoc_total_actual=30.0,
        )
    )
    await admin_session.flush()
    admin_session.add(
        EstocMagatzem(
            empresa_id=ta["empresa_id"],
            article_id=art2_id,
            magatzem_id=ta["mag_nau_id"],
            quantitat_fisica=30.0,
            quantitat_virtual_reservada=5.0,
            quantitat_cuarentena=0.0,
        )
    )
    admin_session.add(
        FullaPicking(
            id=fp_id,
            empresa_id=ta["empresa_id"],
            ordre_treball_id=ta["ot_id"],
            vehicle_id=ta["vehicle_id"],
            estat_picking="PENDENT",
        )
    )
    await admin_session.flush()
    admin_session.add(
        LiniaPicking(
            id=lin1_id,
            empresa_id=ta["empresa_id"],
            picking_id=fp_id,
            article_id=ta["article_id"],
            magatzem_id=ta["mag_nau_id"],
            quantitat_prevista=10.0,
        )
    )
    admin_session.add(
        LiniaPicking(
            id=lin2_id,
            empresa_id=ta["empresa_id"],
            picking_id=fp_id,
            article_id=art2_id,
            magatzem_id=ta["mag_nau_id"],
            quantitat_prevista=5.0,
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Batch Pick-In vàlid de 2 línies en una sola transacció
        r_in = await ac.put(
            "/api/v1/operari/picking/linies/batch",
            json={
                "items": [
                    {"linia_id": str(lin1_id), "quantitat_carregada_pick_in": 10.0},
                    {"linia_id": str(lin2_id), "quantitat_carregada_pick_in": 5.0},
                ]
            },
            headers=ta["headers_op"],
        )
        assert r_in.status_code == 200, r_in.text
        assert r_in.json()["total_confirmades"] == 2

        # 2. Batch Pick-Out amb 2a línia invàlida (retorn + merma > carregat) -> 422 i ROLLBACK TOTAL
        r_bad = await ac.put(
            "/api/v1/operari/picking/linies/batch",
            json={
                "items": [
                    {
                        "linia_id": str(lin1_id),
                        "quantitat_carregada_pick_in": 10.0,
                        "quantitat_retornada_pick_out": 2.0,
                        "quantitat_mermada": 0.0,
                    },
                    {
                        "linia_id": str(lin2_id),
                        "quantitat_carregada_pick_in": 5.0,
                        "quantitat_retornada_pick_out": 4.0,
                        "quantitat_mermada": 3.0,  # 7 > 5 -> invàlid!
                    },
                ]
            },
            headers=ta["headers_op"],
        )
        assert r_bad.status_code == 422, r_bad.text

        # Comprovar que la línia 1 tampoc s'ha tocat (zero desat parcial!)
        admin_session.expire_all()
        l1_db = (
            await admin_session.execute(select(LiniaPicking).where(LiniaPicking.id == lin1_id))
        ).scalar_one()
        assert float(l1_db.quantitat_retornada_pick_out) == 0.0
        assert float(l1_db.consum_aplicat_magatzem) == 0.0

        # 3. Tenant B intenta fer batch sobre línies de Tenant A -> 404 (RLS)
        r_rls = await ac.put(
            "/api/v1/operari/picking/linies/batch",
            json={"items": [{"linia_id": str(lin1_id), "quantitat_carregada_pick_in": 10.0}]},
            headers=tb["headers_op"],
        )
        assert r_rls.status_code == 404, r_rls.text

        # 4. Batch Pick-Out vàlid -> 200 i estoc actualitzat d'ambdues línies
        r_out = await ac.put(
            "/api/v1/operari/picking/linies/batch",
            json={
                "items": [
                    {
                        "linia_id": str(lin1_id),
                        "quantitat_carregada_pick_in": 10.0,
                        "quantitat_retornada_pick_out": 2.0,
                        "quantitat_mermada": 0.0,
                    },
                    {
                        "linia_id": str(lin2_id),
                        "quantitat_carregada_pick_in": 5.0,
                        "quantitat_retornada_pick_out": 1.0,
                        "quantitat_mermada": 0.0,
                    },
                ]
            },
            headers=ta["headers_op"],
        )
        assert r_out.status_code == 200, r_out.text
        assert r_out.json()["total_confirmades"] == 2

    admin_session.expire_all()
    e1 = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == ta["empresa_id"],
                EstocMagatzem.magatzem_id == ta["mag_nau_id"],
                EstocMagatzem.article_id == ta["article_id"],
            )
        )
    ).scalar_one()
    e2 = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == ta["empresa_id"],
                EstocMagatzem.magatzem_id == ta["mag_nau_id"],
                EstocMagatzem.article_id == art2_id,
            )
        )
    ).scalar_one()
    assert float(e1.quantitat_fisica) == 92.0  # 100 - 8
    assert float(e2.quantitat_fisica) == 26.0  # 30 - 4
