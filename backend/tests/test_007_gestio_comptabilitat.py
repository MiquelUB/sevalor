import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.models import Client, Empresa


@pytest_asyncio.fixture
async def setup_comptabilitat_test(admin_session):
    empresa_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    nif_rand = "NIF-" + str(uuid.uuid4())[:5]
    sub_rand = "comp-" + str(uuid.uuid4())[:5]

    admin_session.add(Empresa(
        id=uuid.UUID(empresa_id), nom='Test Comp', nif=nif_rand, subdomini=sub_rand, pla_subscripcio='STARTER', estat_pagament='ACTIU'
    ))
    await admin_session.flush()
    admin_session.add(Client(
        id=uuid.UUID(client_id), empresa_id=uuid.UUID(empresa_id), codi='CLI-1', rao_social='C', nif='B12345678'
    ))
    await admin_session.flush()
    await admin_session.flush()

    return {"empresa_id": empresa_id, "client_id": client_id}

@pytest.mark.asyncio
async def test_alta_factura_verifactu(setup_comptabilitat_test, headers):
    data = setup_comptabilitat_test
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.core.config import settings

    # Boss token
    payload = {
        "sub": str(uuid.uuid4()),
        "rol": "BOSS",
        "empresa_id": data["empresa_id"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60)
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        fac_payload = {
            "numero_factura": 1,
            "serie": "2026",
            "client_id": data["client_id"],
            "base_imposable": 100.00,
            "quota_iva": 21.00,
            "liquid_exigible": 121.00
        }
        res_fac = await ac.post("/api/v1/gestio/comptabilitat/factures", json=fac_payload, headers=headers)
        assert res_fac.status_code == 201
        factura = res_fac.json()
        assert factura["numero_factura"] == 1
        assert factura["hash_sha256"] is not None
        assert len(factura["hash_sha256"]) == 64  # Hash SHA-256 for VeriFactu

        # Test duplicat de sèrie i número
        res_dup = await ac.post("/api/v1/gestio/comptabilitat/factures", json=fac_payload, headers=headers)
        assert res_dup.status_code == 400


@pytest.mark.asyncio
async def test_spec007_v5_suite_completa_i_veto_enginyer(setup_comptabilitat_test, admin_session):
    from datetime import date, datetime, timedelta, timezone
    from decimal import Decimal

    import jwt
    from sqlalchemy import text

    from app.core.config import settings
    from app.models.models import ContracteMantenimentMRR, OrdreTreball, TiquetDespesa, Usuari

    data = setup_comptabilitat_test
    empresa_uuid = uuid.UUID(data["empresa_id"])
    client_uuid = uuid.UUID(data["client_id"])
    boss_id = uuid.uuid4()
    enginyer_id = uuid.uuid4()
    operari_id = uuid.uuid4()

    admin_session.add(
        Usuari(
            id=boss_id,
            empresa_id=empresa_uuid,
            nif="BOSS-001",
            nom="Director",
            rol="BOSS",
            es_alta_direccio=True,
            salari_mensual_brut=4000.00,
            cost_ss_mensual=1200.00,
        )
    )
    admin_session.add(
        Usuari(
            id=operari_id,
            empresa_id=empresa_uuid,
            nif="OP-001",
            nom="Operari",
            rol="OPERARI",
            salari_mensual_brut=1800.00,
            cost_ss_mensual=540.00,
        )
    )
    await admin_session.flush()
    ot_wip_id = uuid.uuid4()
    admin_session.add(
        OrdreTreball(
            id=ot_wip_id,
            empresa_id=empresa_uuid,
            codi="OT-WIP-01",
            client_id=client_uuid,
            titol="Instal·lació Reg",
            adreca="Finca Nord",
            estat="ALBARA_SIGNAT",
            data_finalitzacio_camp=date.today() - timedelta(days=10),
            hores_imputades_facturables=10.0,
            preu_venda_hora_aplicat=50.0,
            cost_materials_pmp=100.0,
            pvp_materials_aplicat=200.0,
        )
    )
    contracte_id = uuid.uuid4()
    admin_session.add(
        ContracteMantenimentMRR(
            id=contracte_id,
            empresa_id=empresa_uuid,
            client_id=client_uuid,
            codi_contracte="MRR-001",
            quota_mensual_mrr=500.00,
            data_inici=date.today() - timedelta(days=30),
        )
    )
    admin_session.add(
        OrdreTreball(
            id=uuid.uuid4(),
            empresa_id=empresa_uuid,
            codi="OT-MRR-DEF",
            client_id=client_uuid,
            contracte_mrr_id=contracte_id,
            titol="Avaria Contracte",
            adreca="Finca Nord",
            estat="FACTURADA",
            hores_imputades_facturables=20.0,
            cost_materials_pmp=200.0,
            km_imputats=100,
        )
    )
    tiquet_id = uuid.uuid4()
    admin_session.add(
        TiquetDespesa(
            id=tiquet_id,
            empresa_id=empresa_uuid,
            categoria="DIETES",
            usuari_id=operari_id,
            data_tiquet=date.today(),
            nif_emissor=None,
            base_imposable=120.00,
            iva_pct=0.00,
            quota_iva=0.00,
            import_total=120.00,
            requereix_aprovacio_boss=True,
        )
    )
    await admin_session.flush()

    def make_headers(uid: uuid.UUID, rol: str) -> dict:
        tok = jwt.encode(
            {
                "sub": str(uid),
                "rol": rol,
                "empresa_id": data["empresa_id"],
                "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return {"Authorization": f"Bearer {tok}"}

    h_boss = make_headers(boss_id, "BOSS")
    h_sec = make_headers(uuid.uuid4(), "SECRETARIA")
    h_eng = make_headers(enginyer_id, "ENGINYER")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Veto 403 a Enginyer (RF-05) i accés sanititzat (RF-05.4)
        res_403 = await ac.get("/api/v1/gestio/comptabilitat/dashboard-economic", headers=h_eng)
        assert res_403.status_code == 403
        res_san = await ac.get(
            f"/api/v1/gestio/operativa-financera/client/{client_uuid}/estat-risc",
            headers=h_eng,
        )
        assert res_san.status_code == 200
        assert res_san.json()["pot_obrir_ot_i_picking"] is True
        assert "liquid_exigible" not in res_san.json()

        # 2. Dashboard econòmic Dia 0 + MRR deficitari + WIP envellit >7d
        res_dash = await ac.get("/api/v1/gestio/comptabilitat/dashboard-economic", headers=h_boss)
        assert res_dash.status_code == 200
        assert Decimal(str(res_dash.json()["mrr_mensual_actiu"])) == Decimal("500.00")

        res_wip = await ac.get("/api/v1/gestio/comptabilitat/wip-control", headers=h_boss)
        assert res_wip.status_code == 200
        assert res_wip.json()["nombre_ots_envellides_critiques"] == 1

        res_mrr = await ac.get("/api/v1/gestio/comptabilitat/contractes-mrr-auditoria", headers=h_boss)
        assert res_mrr.status_code == 200
        assert res_mrr.json()[0]["semafor"] == "DEFICITARI_CRITIC"

        # 3. Ofuscació Alta Direcció per a Secretaria (RF-18) i EDGE-03 div/0
        res_ops = await ac.get("/api/v1/gestio/comptabilitat/operaris-cost-efectiu", headers=h_sec)
        assert res_ops.status_code == 200
        boss_row = next(o for o in res_ops.json() if o["usuari_id"] == str(boss_id))
        assert boss_row["salari_brut_i_ss_visible"] == "***"
        assert boss_row["cost_hora_efectiu_mensual"] is None

        # 4. Tiquet >100€ bloquejat per a Secretaria i aprovat pel BOSS sense NIF -> PENDENT_BESCANVI
        res_tiq_sec = await ac.post(
            f"/api/v1/gestio/comptabilitat/tiquets/{tiquet_id}/auditar",
            json={"accio": "APROVAT"},
            headers=h_sec,
        )
        assert res_tiq_sec.status_code == 403
        res_tiq_boss = await ac.post(
            f"/api/v1/gestio/comptabilitat/tiquets/{tiquet_id}/auditar",
            json={"accio": "APROVAT", "custodia_paper_confirmada": True},
            headers=h_boss,
        )
        assert res_tiq_boss.status_code == 200
        assert res_tiq_boss.json()["estat_fiscal"] == "PENDENT_BESCANVI"

        # 5. Emissió Veri*factu amb Retenció 4308 (5%) + Norma 43 idempotent
        res_em = await ac.post(
            "/api/v1/gestio/comptabilitat/factures/emetre",
            json={
                "client_id": str(client_uuid),
                "serie": "F",
                "data_emissio": date.today().isoformat(),
                "data_venciment": date.today().isoformat(),
                "retencio_garantia_pct": 5.0,
                "linies": [
                    {
                        "obra_id": str(ot_wip_id),
                        "concepte": "Obra Reg",
                        "quantitat": 1,
                        "preu_venda_unitari": 1000.0,
                        "tipus_iva_pct": 21.0,
                    }
                ],
            },
            headers=h_boss,
        )
        assert res_em.status_code == 201
        assert Decimal(str(res_em.json()["liquid_exigible"])) == Decimal("1160.00")

        res_c43_1 = await ac.post(
            "/api/v1/gestio/comptabilitat/norma43/conciliar",
            json={"contingut_c43": f"{date.today().isoformat()}|Cobrament|1160.00|5000.00", "confirmar_conciliacio_hitl": True},
            headers=h_sec,
        )
        assert res_c43_1.status_code == 200
        assert res_c43_1.json()[0]["duplicat_rebutjat"] is False

        res_c43_2 = await ac.post(
            "/api/v1/gestio/comptabilitat/norma43/conciliar",
            json={"contingut_c43": f"{date.today().isoformat()}|Cobrament|1160.00|5000.00", "confirmar_conciliacio_hitl": True},
            headers=h_sec,
        )
        assert res_c43_2.status_code == 200
        assert res_c43_2.json()[0]["duplicat_rebutjat"] is True

    # 6. Trigger SIF Append-Only (EDGE-10)
    from app.models.models import RegistreEsdevenimentsSIF

    await admin_session.execute(
        text(f"SET LOCAL app.current_empresa_id = '{empresa_uuid}';")
    )
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))
    sif_row = RegistreEsdevenimentsSIF(
        empresa_id=empresa_uuid,
        codi_esdeveniment="EV-TEST",
        usuari_id=boss_id,
        descripcio="Registre immutable",
        hash_sello="a" * 64,
    )
    admin_session.add(sif_row)
    await admin_session.flush()

    with pytest.raises(Exception, match="SIF_IMMUTABLE_VIOLATION"):
        await admin_session.execute(
            text("UPDATE registre_esdeveniments_sif SET descripcio = 'MUTAT' WHERE id = :sid"),
            {"sid": sif_row.id},
        )
        await admin_session.flush()
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_spec007_v5_risc_art80_erosio_marge_i_worker(admin_session):
    from datetime import date, datetime, timedelta, timezone
    from decimal import Decimal

    import jwt
    from sqlalchemy import text

    from app.core.config import settings
    from app.models.models import (
        Article,
        FacturaCapcalera,
        RetencioGarantia,
        Usuari,
    )
    from app.workers.comptabilitat_tasks import executar_auditoria_diaria_financera_tenant_async

    empresa_uuid = uuid.uuid4()
    client_ret_id = uuid.uuid4()
    client_mora_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    sec_id = uuid.uuid4()
    eng_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=empresa_uuid,
            nom="Suite Risc & Art80",
            nif="B" + str(uuid.uuid4())[:8],
            subdomini="risc-" + str(uuid.uuid4())[:6],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()

    await admin_session.execute(
        text(f"SET LOCAL app.current_empresa_id = '{empresa_uuid}';")
    )
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))

    admin_session.add_all(
        [
            Usuari(
                id=boss_id,
                empresa_id=empresa_uuid,
                nif="BOSS-RISC",
                nom="Boss Risc",
                rol="BOSS",
                telefon="+34611000101",
                email=f"boss-{boss_id}@test.com",
                password_hash="x",
                es_alta_direccio=True,
            ),
            Usuari(
                id=sec_id,
                empresa_id=empresa_uuid,
                nif="SEC-RISC",
                nom="Sec Risc",
                rol="SECRETARIA",
                telefon="+34611000102",
                email=f"sec-{sec_id}@test.com",
                password_hash="x",
            ),
            Usuari(
                id=eng_id,
                empresa_id=empresa_uuid,
                nif="ENG-RISC",
                nom="Eng Risc",
                rol="ENGINYER",
                telefon="+34611000103",
                email=f"eng-{eng_id}@test.com",
                password_hash="x",
            ),
            Client(
                id=client_ret_id,
                empresa_id=empresa_uuid,
                codi="C-RET",
                rao_social="Constructora Retencio SL",
                nif="B11223344",
                limit_risc_credit=Decimal("10000.00"),
            ),
            Client(
                id=client_mora_id,
                empresa_id=empresa_uuid,
                codi="C-MORA",
                rao_social="Morositat SL",
                nif="B55667788",
                limit_risc_credit=Decimal("10000.00"),
            ),
        ]
    )
    await admin_session.flush()

    avui = date.today()
    # Factura cobrada amb retencio 4308 de fa 200 dies (EDGE-07: NO ha de bloquejar el client)
    fact_ret_id = uuid.uuid4()
    admin_session.add(
        FacturaCapcalera(
            id=fact_ret_id,
            empresa_id=empresa_uuid,
            client_id=client_ret_id,
            serie="A",
            numero_factura=1,
            data_emissio=datetime.now(timezone.utc) - timedelta(days=230),
            data_venciment=avui - timedelta(days=200),
            base_imposable=10000.00,
            quota_iva=2100.00,
            import_retencio_garantia_4308=500.00,
            liquid_exigible=11600.00,
            estat_document="EMESA",
            estat_cobrament="COBRADA",
            import_cobrat=11600.00,
            hash_sha256="1" * 64,
        )
    )
    await admin_session.flush()
    admin_session.add(
        RetencioGarantia(
            empresa_id=empresa_uuid,
            tipus="CLIENT_4308",
            client_id=client_ret_id,
            factura_client_id=fact_ret_id,
            import_retingut=500.00,
            percentatge_aplicat=5.00,
            data_retencio=avui - timedelta(days=230),
            data_venciment_garantia=avui - timedelta(days=10),
            estat="RETINGUDA",
        )
    )

    # Factura ordinaria impagada > 90 dies (100d), factura 195d Art.80 i factura 285d Art.80 expirada
    fact_100_id = uuid.uuid4()
    fact_195_id = uuid.uuid4()
    fact_285_id = uuid.uuid4()
    admin_session.add_all(
        [
            FacturaCapcalera(
                id=fact_100_id,
                empresa_id=empresa_uuid,
                client_id=client_mora_id,
                serie="A",
                numero_factura=2,
                data_emissio=datetime.now(timezone.utc) - timedelta(days=130),
                data_venciment=avui - timedelta(days=100),
                base_imposable=1000.00,
                quota_iva=210.00,
                liquid_exigible=1210.00,
                estat_document="EMESA",
                estat_cobrament="PENDENT",
                hash_sha256="2" * 64,
            ),
            FacturaCapcalera(
                id=fact_195_id,
                empresa_id=empresa_uuid,
                client_id=client_mora_id,
                serie="A",
                numero_factura=3,
                data_emissio=datetime.now(timezone.utc) - timedelta(days=225),
                data_venciment=avui - timedelta(days=195),
                base_imposable=2000.00,
                quota_iva=420.00,
                liquid_exigible=2420.00,
                estat_document="EMESA",
                estat_cobrament="IMPAGADA",
                hash_sha256="3" * 64,
            ),
            FacturaCapcalera(
                id=fact_285_id,
                empresa_id=empresa_uuid,
                client_id=client_mora_id,
                serie="A",
                numero_factura=4,
                data_emissio=datetime.now(timezone.utc) - timedelta(days=315),
                data_venciment=avui - timedelta(days=285),
                base_imposable=500.00,
                quota_iva=105.00,
                liquid_exigible=605.00,
                estat_document="EMESA",
                estat_cobrament="IMPAGADA",
                hash_sha256="4" * 64,
            ),
        ]
    )

    # Article amb erosio de marge i immobilitzat > 90 dies
    admin_session.add(
        Article(
            empresa_id=empresa_uuid,
            referencia_inventari="ART-ERO-1",
            nom="Valvula Bronce DN50",
            unitat_mesura="u",
            preu_cost=Decimal("80.00"),
            preu_cost_ultim=Decimal("92.00"),
            preu_cost_mitja=Decimal("80.00"),
            preu_venda=Decimal("100.00"),
            llindar_marge_minim_pct=Decimal("25.00"),
            estoc_optim=10,
            darrer_moviment_sortida=avui - timedelta(days=120),
            actiu=True,
        )
    )
    await admin_session.commit()

    def _tok(uid, role):
        return {
            "Authorization": "Bearer "
            + jwt.encode(
                {
                    "sub": str(uid),
                    "empresa_id": str(empresa_uuid),
                    "rol": role,
                    "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
                },
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            )
        }

    h_boss = _tok(boss_id, "BOSS")
    h_sec = _tok(sec_id, "SECRETARIA")
    h_eng = _tok(eng_id, "ENGINYER")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. EDGE-07: avaluem risc amb BOSS; client amb nomes retencio 4308 es APTE
        r_eval_ret = await ac.post(
            f"/api/v1/gestio/comptabilitat/clients/{client_ret_id}/evaluar-risc",
            headers=h_boss,
        )
        assert r_eval_ret.status_code == 200
        assert r_eval_ret.json()["estat_risc_operatiu"] == "APTE"

        r_ret = await ac.post(
            f"/api/v1/gestio/operativa-financera/validar-operacio/{client_ret_id}",
            headers=h_eng,
        )
        assert r_ret.status_code == 200
        assert r_ret.json()["estat_risc_operatiu"] == "APTE"

        # 2. Client moros > 90d -> avaluat per BOSS com a BLOQUEJAT_RISC -> HTTP 423 Locked per ENGINYER
        r_eval_mora = await ac.post(
            f"/api/v1/gestio/comptabilitat/clients/{client_mora_id}/evaluar-risc",
            headers=h_boss,
        )
        assert r_eval_mora.status_code == 200
        assert r_eval_mora.json()["estat_risc_operatiu"] == "BLOQUEJAT_RISC"

        r_lock = await ac.post(
            f"/api/v1/gestio/operativa-financera/validar-operacio/{client_mora_id}",
            headers=h_eng,
        )
        assert r_lock.status_code == 423, r_lock.json()

        # 3. Override nomes BOSS (SECRETARIA -> 403)
        r_ov_sec = await ac.post(
            f"/api/v1/gestio/comptabilitat/clients/{client_mora_id}/override-risc",
            json={"motiu": "No autoritzat"},
            headers=h_sec,
        )
        assert r_ov_sec.status_code == 403

        r_ov_boss = await ac.post(
            f"/api/v1/gestio/comptabilitat/clients/{client_mora_id}/override-risc",
            json={"motiu": "Pagare confirmat amb gerencia"},
            headers=h_boss,
        )
        assert r_ov_boss.status_code == 200
        assert r_ov_boss.json()["estat_risc_operatiu"] == "OVERRIDE_BOSS"

        r_unlock = await ac.post(
            f"/api/v1/gestio/operativa-financera/validar-operacio/{client_mora_id}",
            headers=h_eng,
        )
        assert r_unlock.status_code == 200
        assert r_unlock.json()["pot_obrir_ot_i_picking"] is True

        # 4. Art. 80 LIVA: 195d -> 201 rectificativa R; 285d -> 400 FINESTRA_ART80_EXPIRADA
        r_art80_ok = await ac.post(
            f"/api/v1/gestio/comptabilitat/art80-incobrables/{fact_195_id}/rectificar",
            json={"justificant_notarial_path": "/vault/req_notarial_195.pdf"},
            headers=h_boss,
        )
        assert r_art80_ok.status_code == 201, r_art80_ok.json()
        assert r_art80_ok.json()["serie"] == "R"

        r_art80_exp = await ac.post(
            f"/api/v1/gestio/comptabilitat/art80-incobrables/{fact_285_id}/rectificar",
            json={"justificant_notarial_path": "/vault/req_notarial_285.pdf"},
            headers=h_boss,
        )
        assert r_art80_exp.status_code == 400
        assert "FINESTRA_ART80_EXPIRADA" in r_art80_exp.json()["detail"]

        # 5. Erosio de marge i capital immobilitzat > 90d al dashboard
        r_dash = await ac.get("/api/v1/gestio/comptabilitat/dashboard-economic", headers=h_boss)
        assert r_dash.status_code == 200
        dash = r_dash.json()
        assert len(dash["alertes_erosio_marge"]) == 1
        assert Decimal(str(dash["alertes_erosio_marge"][0]["marge_actual_pct"])) == Decimal("8.00")
        assert Decimal(str(dash["capital_immobilitzat_90d_eur"])) == Decimal("800.00")

    # 6. Worker d'auditoria diària amb sessió RLS
    await admin_session.execute(
        text(f"SET LOCAL app.current_empresa_id = '{empresa_uuid}';")
    )
    await admin_session.execute(text("SET LOCAL app.current_user_role = 'BOSS';"))
    worker_res = await executar_auditoria_diaria_financera_tenant_async(admin_session, empresa_uuid)
    assert worker_res["retencions_pendents_reclamacio"] >= 1
    assert worker_res["art80_finestres_expirades"] >= 1

