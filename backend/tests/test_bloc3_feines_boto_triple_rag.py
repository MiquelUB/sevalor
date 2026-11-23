"""Tests del BLOC 3 — Feines (alta atòmica, picking multi-magatzem, BLOQUEJAT_RISC, FR-012, veto ENGINYER), Botó Triple (Pressupostos IA) i RAG."""

import json
import uuid
from datetime import datetime, timedelta, timezone
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
    Finca,
    FullaPicking,
    Magatzem,
    OrdreTreball,
    Usuari,
    Vehicle,
)
from app.services.sovereign_storage import (
    SovereignStorageGateway,
    inicialitzar_arbre_carpetes_disc,
)


def _make_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    payload: dict[str, Any] = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_bloc3_client_bloquejat_risc_retorna_423_sense_ot_orfena(
    admin_session, headers, boss_token, tmp_path: Path
):
    """Client amb estat_risc_operatiu='BLOQUEJAT_RISC' ha de bloquejar l'alta d'OT amb HTTP 423."""
    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    disc_root = tmp_path / "disc_423"
    inicialitzar_arbre_carpetes_disc(disc_root)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Risc Operatiu",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="risc-" + uuid.uuid4().hex[:5],
            pla_subscripcio="STARTER",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
        )
    )
    await admin_session.flush()
    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_uuid,
            codi="CLI-RISC",
            rao_social="Client Morositat Crítica S.L.",
            nif="B11223344",
            estat_risc_operatiu="BLOQUEJAT_RISC",
        )
    )
    await admin_session.commit()

    payload = {
        "codi": "OT-RISC-423",
        "client_id": str(client_id),
        "titol": "Instal·lació bloquejada",
        "adreca": "Av. Diagonal 10, Lleida",
        "estat": "PENDENT",
        "data_planificacio": "2027-04-01",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/gestio/feines", json=payload, headers=headers)
        assert res.status_code == 423, res.text

    ot_db = (
        await admin_session.execute(
            select(OrdreTreball).where(
                OrdreTreball.empresa_id == emp_uuid,
                OrdreTreball.codi == "OT-RISC-423",
            )
        )
    ).scalars().first()
    assert ot_db is None


@pytest.mark.asyncio
async def test_bloc3_alta_feina_picking_atomic_rollback_i_sync_disc(
    admin_session, headers, boss_token, tmp_path: Path
):
    """
    Verifica:
    1) Picking amb quantitat > estoc al magatzem seleccionat -> HTTP 422 i rollback atòmic (0 OTs òrfenes).
    2) Picking vàlid amb cap_de_colla_id=None i magatzem_id específic -> HTTP 201, reserva estoc i JSON a actives_buffer + picking.
    3) Tancament d'obra -> sincronitza JSON a historic_tancades.
    """
    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    disc_root = tmp_path / "disc_picking_atomic"
    inicialitzar_arbre_carpetes_disc(disc_root)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Atomic Picking",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="atomic-" + uuid.uuid4().hex[:5],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
        )
    )
    await admin_session.flush()
    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_uuid,
            codi="CLI-ATOM",
            rao_social="Client Atòmic S.A.",
            nif="A88776655",
            estat_risc_operatiu="NORMAL",
        )
    )
    mag_a, mag_b = uuid.uuid4(), uuid.uuid4()
    admin_session.add_all(
        [
            Magatzem(id=mag_a, empresa_id=emp_uuid, nom="Magatzem Central", tipus="NAU_CENTRAL"),
            Magatzem(id=mag_b, empresa_id=emp_uuid, nom="Magatzem Delegació", tipus="NAU_CENTRAL"),
        ]
    )
    art_id = uuid.uuid4()
    admin_session.add(
        Article(
            id=art_id,
            empresa_id=emp_uuid,
            referencia_inventari="TUB-PE-32",
            nom="Canonada Polietilè 32mm",
            unitat_mesura="METRE",
            preu_cost=1.8,
            preu_venda=3.5,
        )
    )
    await admin_session.flush()
    estoc_a = EstocMagatzem(
        empresa_id=emp_uuid,
        article_id=art_id,
        magatzem_id=mag_a,
        quantitat_fisica=10.0,
        quantitat_virtual_reservada=0.0,
    )
    estoc_b = EstocMagatzem(
        empresa_id=emp_uuid,
        article_id=art_id,
        magatzem_id=mag_b,
        quantitat_fisica=1.0,
        quantitat_virtual_reservada=0.0,
    )
    admin_session.add_all([estoc_a, estoc_b])
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Intent amb excés d'estoc a mag_b -> 422 i 0 OTs òrfenes
        res_fail = await ac.post(
            "/api/v1/gestio/feines",
            json={
                "codi": "OT-ATOM-FAIL",
                "client_id": str(client_id),
                "titol": "Obra sense prou estoc",
                "adreca": "Camí dels Horts 1, Girona",
                "estat": "PENDENT",
                "data_planificacio": "2027-04-10",
                "magatzem_id": str(mag_b),
                "linies_picking": [{"article_id": str(art_id), "quantitat_prevista": 4.0}],
            },
            headers=headers,
        )
        assert res_fail.status_code == 422, res_fail.text

        ot_orphan = (
            await admin_session.execute(
                select(OrdreTreball).where(OrdreTreball.codi == "OT-ATOM-FAIL")
            )
        ).scalars().first()
        assert ot_orphan is None
        pick_orphan = (
            await admin_session.execute(
                select(FullaPicking).where(FullaPicking.empresa_id == emp_uuid)
            )
        ).scalars().first()
        assert pick_orphan is None

        # 2. Alta vàlida a mag_a amb cap_de_colla_id=None
        res_ok = await ac.post(
            "/api/v1/gestio/feines",
            json={
                "codi": "OT-ATOM-OK",
                "client_id": str(client_id),
                "titol": "Sector Reg Goters Nord",
                "adreca": "Ctra. Taialà 12, Girona",
                "estat": "PENDENT",
                "data_planificacio": "2027-04-12",
                "cap_de_colla_id": None,
                "magatzem_id": str(mag_a),
                "linies_picking": [{"article_id": str(art_id), "quantitat_prevista": 4.0}],
            },
            headers=headers,
        )
        assert res_ok.status_code == 201, res_ok.text
        created = res_ok.json()
        ot_id = created["id"]
        assert created["cap_de_colla_id"] is None
        assert len(created["linies_picking"]) == 1
        assert created["linies_picking"][0]["quantitat_prevista"] == 4.0

        estoc_a_db = (
            await admin_session.execute(
                select(EstocMagatzem).where(EstocMagatzem.id == estoc_a.id)
            )
        ).scalar_one()
        estoc_b_db = (
            await admin_session.execute(
                select(EstocMagatzem).where(EstocMagatzem.id == estoc_b.id)
            )
        ).scalar_one()
        assert float(estoc_a_db.quantitat_virtual_reservada) == 4.0
        assert float(estoc_b_db.quantitat_virtual_reservada) == 0.0

        # Verificar JSON fisic a 06_ordres_treball/actives_buffer/{ot_id}.json i picking
        active_file = disc_root / "06_ordres_treball" / "actives_buffer" / f"{ot_id}.json"
        picking_file = disc_root / "03_magatzem" / "picking_fulles" / f"picking_{ot_id}.json"
        assert active_file.is_file()
        assert picking_file.is_file()
        assert json.loads(active_file.read_text(encoding="utf-8"))["codi"] == "OT-ATOM-OK"

        # 3. Tancar obra -> escriu a historic_tancades
        res_close = await ac.put(
            f"/api/v1/gestio/feines/{ot_id}/tancar-obra",
            json={
                "signatura_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
                "conformitat_client": True,
                "observacions": "Tancament verificat",
            },
            headers=headers,
        )
        assert res_close.status_code == 200, res_close.text
        hist_file = disc_root / "06_ordres_treball" / "historic_tancades" / f"{ot_id}.json"
        assert hist_file.is_file()
        assert json.loads(hist_file.read_text(encoding="utf-8"))["estat"] == "TANCADA"


@pytest.mark.asyncio
async def test_bloc3_fr012_permis_conduir_i_enginyer_veto_tarifa(
    admin_session, headers, boss_token, tmp_path: Path
):
    """Verifica guarda FR-012 (422 si carnet insuficient) i ocultació tarifa hora per ENGINYER."""
    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    disc_root = tmp_path / "disc_fr012"
    inicialitzar_arbre_carpetes_disc(disc_root)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Flota & Rols",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="fr012-" + uuid.uuid4().hex[:5],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
        )
    )
    await admin_session.flush()
    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_uuid,
            codi="CLI-FLT",
            rao_social="Client Flota",
            nif="B44556677",
        )
    )
    op_b_id, op_c_id, eng_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    admin_session.add_all(
        [
            Usuari(
                id=op_b_id,
                empresa_id=emp_uuid,
                nif="OP-CARNET-B",
                nom="Joan",
                cognoms="Només B",
                rol="OPERARI",
                estat="ACTIU",
                carnet_conduir="B",
            ),
            Usuari(
                id=op_c_id,
                empresa_id=emp_uuid,
                nif="OP-CARNET-C",
                nom="Marc",
                cognoms="Camió C",
                rol="OPERARI",
                estat="ACTIU",
                carnet_conduir="C",
            ),
            Usuari(
                id=eng_id,
                empresa_id=emp_uuid,
                nif="ENG-VETO-1",
                nom="Laura",
                cognoms="Enginyera",
                rol="ENGINYER",
                estat="ACTIU",
            ),
        ]
    )
    veh_c_id = uuid.uuid4()
    admin_session.add(
        Vehicle(
            id=veh_c_id,
            empresa_id=emp_uuid,
            matricula="9988-FRX",
            marca="Iveco",
            model="Eurocargo",
            carnet_necessari="C",
            requereix_cap=False,
        )
    )
    await admin_session.commit()

    eng_headers = {
        "Authorization": f"Bearer {_make_token(eng_id, emp_uuid, 'ENGINYER')}",
        "X-Empresa-ID": empresa_id,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Vehicle carnet C + Operari B -> 422 FR-012
        res_422 = await ac.post(
            "/api/v1/gestio/feines",
            json={
                "codi": "OT-FR012-FAIL",
                "client_id": str(client_id),
                "titol": "Transport Camió Pesant",
                "adreca": "Polígon Sud, Reus",
                "data_planificacio": "2027-04-15",
                "cap_de_colla_id": str(op_b_id),
                "vehicle_id": str(veh_c_id),
            },
            headers=headers,
        )
        assert res_422.status_code == 422, res_422.text
        assert "FR-012" in res_422.text or "permís" in res_422.text

        # 2. Operari C + CAP -> 201 OK
        res_ok = await ac.post(
            "/api/v1/gestio/feines",
            json={
                "codi": "OT-FR012-OK",
                "client_id": str(client_id),
                "titol": "Transport Autoritzat",
                "adreca": "Polígon Sud 2, Reus",
                "data_planificacio": "2027-04-16",
                "cap_de_colla_id": str(op_c_id),
                "vehicle_id": str(veh_c_id),
            },
            headers=headers,
        )
        assert res_ok.status_code == 201, res_ok.text
        ot_id = res_ok.json()["id"]
        assert res_ok.json()["preu_venda_hora_aplicat"] is not None

        # 3. Rol ENGINYER veu tarifa comercial PVP/h de la feina (sense costos interns ni marges)
        res_list_eng = await ac.get("/api/v1/gestio/feines", headers=eng_headers)
        assert res_list_eng.status_code == 200
        assert res_list_eng.json()[0]["preu_venda_hora_aplicat"] is not None

        res_det_eng = await ac.get(f"/api/v1/gestio/feines/{ot_id}", headers=eng_headers)
        assert res_det_eng.status_code == 200
        assert res_det_eng.json()["preu_venda_hora_aplicat"] is not None


@pytest.mark.asyncio
async def test_bloc3_intervencions_actives_zero_mocks(admin_session, headers, boss_token):
    """/intervencions/actives retorna dades reals per JOIN o None (mai strings/coords falses)."""
    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)

    admin_session.add(
        Empresa(
            id=emp_uuid,
            nom="Empresa Zero Mock GIS",
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="zm-gis-" + uuid.uuid4().hex[:5],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
        )
    )
    await admin_session.flush()
    client_id = uuid.uuid4()
    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_uuid,
            codi="CLI-ZM",
            rao_social="Agrícola Can Vallès S.L.",
            nif="B77665544",
        )
    )
    cap_id = uuid.uuid4()
    admin_session.add(
        Usuari(
            id=cap_id,
            empresa_id=emp_uuid,
            nif="OP-ZM-1",
            nom="Pere",
            cognoms="Soler",
            rol="OPERARI",
            estat="ACTIU",
        )
    )
    await admin_session.flush()
    finca_id = uuid.uuid4()
    admin_session.add(
        Finca(
            id=finca_id,
            empresa_id=emp_uuid,
            client_id=client_id,
            nom="Parcel·la Bassa Nord",
            codi_candat_en_memoria="CANDAT-4092",
            latitud=41.6122,
            longitud=0.6255,
        )
    )
    await admin_session.flush()
    admin_session.add_all(
        [
            OrdreTreball(
                empresa_id=emp_uuid,
                codi="OT-GIS-REAL",
                client_id=client_id,
                finca_id=finca_id,
                cap_de_colla_id=cap_id,
                titol="Bomba Bassa Nord",
                adreca="Camí Sense Coords",
                estat="EN_OBRA",
            ),
            OrdreTreball(
                empresa_id=emp_uuid,
                codi="OT-GIS-BUIT",
                client_id=client_id,
                titol="Pendent sense finca ni cap",
                adreca="Adreça desconeguda 999",
                estat="PENDENT",
            ),
        ]
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/intervencions/actives", headers=headers)
        assert res.status_code == 200, res.text
        rows = {item["codi"]: item for item in res.json()}

        real_it = rows["OT-GIS-REAL"]
        assert real_it["client"] == "Agrícola Can Vallès S.L."
        assert real_it["cap_colla"] == "Pere Soler"
        assert real_it["sector"] == "Parcel·la Bassa Nord"
        assert real_it["codi_candat"] == "CANDAT-4092"
        assert real_it["pressio_bar"] is None
        assert real_it["coords"] == [pytest.approx(41.6122), pytest.approx(0.6255)]

        buit_it = rows["OT-GIS-BUIT"]
        assert buit_it["client"] == "Agrícola Can Vallès S.L."
        assert buit_it["cap_colla"] is None
        assert buit_it["sector"] is None
        assert buit_it["codi_candat"] is None
        assert buit_it["pressio_bar"] is None
        assert buit_it["coords"] is None


@pytest.mark.asyncio
async def test_bloc3_pressupost_ia_boto_triple_503_vs_200_i_rag(
    admin_session, headers, boss_token, tmp_path: Path
):
    """
    Verifica:
    1) /auth/me exposa node_ia_actiu i feature_copilot_ia.
    2) /pressupostos/generar-ia -> 503 quan node desactivat o offline; 200 quan actiu llegint catàleg del disc.
    3) /gestio/copilot/rag/document escriu a 10_protocols_i_manuals/procediments_interns/.
    """
    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    from tests.wss_test_helpers import live_empresa_wss_context

    disc_root = tmp_path / "disc_ia_rag"
    inicialitzar_arbre_carpetes_disc(disc_root)
    vault_token = f"svlt_bloc3_{uuid.uuid4().hex[:12]}"

    emp = Empresa(
        id=emp_uuid,
        nom="Empresa IA RAG Test",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini="iarag-" + uuid.uuid4().hex[:5],
        pla_subscripcio="ENTERPRISE",
        estat_pagament="ACTIU",
        disc_dur_url=f"wss-tunnel://{emp_uuid}",
        node_ia_url=f"wss-tunnel://{emp_uuid}",
        vault_token=vault_token,
        feature_copilot_ia=True,
        node_ia_actiu=False,
    )
    eng_id = uuid.uuid4()
    admin_session.add_all(
        [
            emp,
            Usuari(
                id=eng_id,
                empresa_id=emp_uuid,
                nif="ENG-IA-1",
                nom="Pau",
                cognoms="Tècnic",
                rol="ENGINYER",
                estat="ACTIU",
            ),
        ]
    )
    await admin_session.commit()

    eng_headers = {
        "Authorization": f"Bearer {_make_token(eng_id, emp_uuid, 'ENGINYER')}",
        "X-Empresa-ID": empresa_id,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. /auth/me amb node_ia_actiu=False
        me_off = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_off.status_code == 200
        assert me_off.json()["feature_copilot_ia"] is True
        assert me_off.json()["node_ia_actiu"] is False

        # 2. /pressupostos/generar-ia -> 503 COPILOT_DESACTIVAT
        res_503 = await ac.post(
            "/api/v1/gestio/pressupostos/generar-ia?prompt=Bomba%20hidr%C3%A0ulica",
            headers=headers,
        )
        assert res_503.status_code == 503

        # Activem node_ia_actiu però túnel WSS desconnectat -> 503 NODE_IA_OFFLINE
        emp.node_ia_actiu = True
        await admin_session.commit()

        me_on = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_on.status_code == 200
        assert me_on.json()["node_ia_actiu"] is True

        res_offline = await ac.post(
            "/api/v1/gestio/pressupostos/generar-ia?prompt=Bomba%20submergible",
            headers=headers,
        )
        assert res_offline.status_code == 503

        # Amb Túnel WSS real connectat + catàleg real al disc -> 200 PENDENT_AUDITORIA
        from app.services.copilot_config_service import save_strict_copilot_config

        await save_strict_copilot_config(
            db=admin_session,
            empresa_id=emp_uuid,
            system_prompt="Copilot sobirà de pressupostos d'Empresa IA RAG Test.",
            rag_prompt="",
            subagent_prompts={},
        )
        async with live_empresa_wss_context(emp_uuid, vault_token, disc_root):
            await SovereignStorageGateway.desar_entitat_json(
                db=admin_session,
                empresa_id=emp_uuid,
                categoria="magatzem_articles",
                item_id="art-bomba-1",
                dades={
                    "nom": "Bomba Submergible Grundfos SP",
                    "referencia_inventari": "BMB-SP5",
                    "preu_venda": 640.0,
                },
            )

            res_200 = await ac.post(
                "/api/v1/gestio/pressupostos/generar-ia?prompt=Subministrament%20bomba%20submergible",
                headers=headers,
            )
            assert res_200.status_code == 200, res_200.text
            data_200 = res_200.json()
            assert data_200["status"] == "PENDENT_AUDITORIA"
            assert data_200["draft"]["total_estimat"] == 640.0
            assert (
                disc_root / "04_factures" / "prefactures_i_pressupostos" / f"draft_{data_200['id']}.json"
            ).is_file()

            # Mateixa petició amb rol ENGINYER oculta els preus
            res_eng = await ac.post(
                "/api/v1/gestio/pressupostos/generar-ia?prompt=Subministrament%20bomba%20submergible",
                headers=eng_headers,
            )
            assert res_eng.status_code == 200
            assert res_eng.json()["draft"]["total_estimat"] is None
            assert res_eng.json()["draft"]["linies"][0]["preu_unitari"] is None

            # 3. RAG document via alias PWA {titol, contingut, tags}
            res_rag = await ac.post(
                "/api/v1/gestio/copilot/rag/document",
                json={
                    "titol": "Protocol Purga Bombes Submergibles",
                    "contingut": "1. Tancar clau de pas.\n2. Purgar aire superior abans d'arrencar.",
                    "tags": "bomba,purga,reg",
                },
                headers=headers,
            )
            assert res_rag.status_code == 201, res_rag.text
            doc_id = res_rag.json()["id"]
            rag_file = disc_root / "10_protocols_i_manuals" / "procediments_interns" / f"{doc_id}.json"
            assert rag_file.is_file()
            assert json.loads(rag_file.read_text(encoding="utf-8"))["titol"] == "Protocol Purga Bombes Submergibles"

            res_rag_list = await ac.get("/api/v1/gestio/copilot/rag/document", headers=headers)
            assert res_rag_list.status_code == 200
            assert any(d["id"] == doc_id for d in res_rag_list.json())


@pytest.mark.asyncio
async def test_bloc3_rls_aillament_feines_i_rag(admin_session, headers, boss_token, tmp_path: Path):
    """Aïllament RLS multi-tenant: Tenant B no pot llegir ni editar les OTs ni protocols RAG del Tenant A."""
    _, empresa_a_id = boss_token
    emp_a = uuid.UUID(empresa_a_id)
    emp_b = uuid.uuid4()
    disc_a = tmp_path / "disc_rls_a"
    disc_b = tmp_path / "disc_rls_b"
    inicialitzar_arbre_carpetes_disc(disc_a)
    inicialitzar_arbre_carpetes_disc(disc_b)

    admin_session.add_all(
        [
            Empresa(
                id=emp_a,
                nom="Tenant A Bloc3",
                nif="B" + uuid.uuid4().hex[:8].upper(),
                subdomini="tena3-" + uuid.uuid4().hex[:5],
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
                disc_dur_url=str(disc_a),
            ),
            Empresa(
                id=emp_b,
                nom="Tenant B Bloc3",
                nif="B" + uuid.uuid4().hex[:8].upper(),
                subdomini="tenb3-" + uuid.uuid4().hex[:5],
                pla_subscripcio="PRO",
                estat_pagament="ACTIU",
                disc_dur_url=str(disc_b),
            ),
        ]
    )
    await admin_session.flush()
    client_a = uuid.uuid4()
    boss_b = uuid.uuid4()
    admin_session.add_all(
        [
            Client(
                id=client_a,
                empresa_id=emp_a,
                codi="CLI-RLS-A",
                rao_social="Client Exclusiu A",
                nif="B90909090",
            ),
            Usuari(
                id=boss_b,
                empresa_id=emp_b,
                nif="BOSS-B-RLS",
                nom="Boss B",
                rol="BOSS",
                estat="ACTIU",
            ),
        ]
    )
    await admin_session.commit()

    headers_b = {
        "Authorization": f"Bearer {_make_token(boss_b, emp_b, 'BOSS')}",
        "X-Empresa-ID": str(emp_b),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_create_a = await ac.post(
            "/api/v1/gestio/feines",
            json={
                "codi": "OT-TENANT-A",
                "client_id": str(client_a),
                "titol": "Obra Confidencial A",
                "adreca": "Carrer Secret 1",
                "data_planificacio": "2027-04-20",
            },
            headers=headers,
        )
        assert res_create_a.status_code == 201, res_create_a.text
        ot_a_id = res_create_a.json()["id"]

        res_rag_a = await ac.post(
            "/api/v1/gestio/copilot/rag/document",
            json={
                "titol": "Secret Tenant A",
                "contingut": "Només visible al Tenant A",
                "tags": "secret",
            },
            headers=headers,
        )
        assert res_rag_a.status_code == 201

        # Tenant B NO veu OT d'A ni al llistat, ni al detall, ni la pot modificar, ni veu RAG d'A
        res_list_b = await ac.get("/api/v1/gestio/feines", headers=headers_b)
        assert res_list_b.status_code == 200
        assert all(it["id"] != ot_a_id for it in res_list_b.json())

        res_det_b = await ac.get(f"/api/v1/gestio/feines/{ot_a_id}", headers=headers_b)
        assert res_det_b.status_code == 404

        res_put_b = await ac.put(
            f"/api/v1/gestio/feines/{ot_a_id}",
            json={"titol": "Segrestat"},
            headers=headers_b,
        )
        assert res_put_b.status_code == 404

        res_rag_b = await ac.get("/api/v1/gestio/copilot/rag/document", headers=headers_b)
        assert res_rag_b.status_code == 200
        assert res_rag_b.json() == []
