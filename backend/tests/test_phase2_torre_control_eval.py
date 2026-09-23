import uuid
from datetime import datetime, timezone

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.models import (
    Article,
    Client,
    Empresa,
    FullaPicking,
    Incidencia,
    LiniaPicking,
    OrdreTreball,
    Usuari,
)


@pytest.fixture
async def f2_eval_setup(admin_session: AsyncSession):
    """Configuració dinàmica per a l'avaluació de la Fase 2 (Torre de Control GIS i Agenda)."""
    # 1. Crear Empresa A i Empresa B
    emp_a_id = uuid.uuid4()
    empresa_a = Empresa(
        id=emp_a_id,
        nom=f"Empresa GIS A {emp_a_id.hex[:6]}",
        subdomini=f"gisa-{emp_a_id.hex[:6]}",
        nif=f"A{emp_a_id.hex[:8].upper()}"
    )
    admin_session.add(empresa_a)

    emp_b_id = uuid.uuid4()
    empresa_b = Empresa(
        id=emp_b_id,
        nom=f"Empresa GIS B {emp_b_id.hex[:6]}",
        subdomini=f"gisb-{emp_b_id.hex[:6]}",
        nif=f"B{emp_b_id.hex[:8].upper()}"
    )
    admin_session.add(empresa_b)
    await admin_session.flush()

    # Boss Empresa A
    boss_a_id = uuid.uuid4()
    boss_a = Usuari(
        id=boss_a_id,
        empresa_id=emp_a_id,
        nom="Boss GIS A",
        email=f"boss.a.{emp_a_id.hex[:6]}@sevalortest.com",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="BOSS",
        nif=f"NIF{emp_a_id.hex[:6].upper()}"
    )
    admin_session.add(boss_a)

    # Boss Empresa B
    boss_b_id = uuid.uuid4()
    boss_b = Usuari(
        id=boss_b_id,
        empresa_id=emp_b_id,
        nom="Boss GIS B",
        email=f"boss.b.{emp_b_id.hex[:6]}@sevalortest.com",
        password_hash=bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode(),
        rol="BOSS",
        nif=f"NIF{emp_b_id.hex[:6].upper()}"
    )
    admin_session.add(boss_b)
    await admin_session.flush()

    # 2. Crear Client a Empresa A
    client_a_id = uuid.uuid4()
    client_a = Client(
        id=client_a_id,
        empresa_id=emp_a_id,
        codi=f"CLI-A-{emp_a_id.hex[:4]}",
        rao_social="Finca Verda Ecològica S.L.",
        nif=f"B{emp_a_id.hex[:8].upper()}",
        email="contacte@fincaverda.cat",
        telefon="+34 938 111 222"
    )
    admin_session.add(client_a)
    await admin_session.flush()

    # 3. Crear Ordre de Treball amb Coordenades Reals (Sagrada Família Barcelona)
    ot_id = uuid.uuid4()
    ot = OrdreTreball(
        id=ot_id,
        empresa_id=emp_a_id,
        client_id=client_a_id,
        codi=f"OT-GIS-{emp_a_id.hex[:4]}",
        titol="Instal·lació comptador general de reg",
        adreca="41.4036, 2.1744",
        estat="PENDENT",
        version_id=1
    )
    admin_session.add(ot)
    await admin_session.flush()

    # 4. Articles i materials per a la Fitxa 360
    art_id = uuid.uuid4()
    article = Article(
        id=art_id,
        empresa_id=emp_a_id,
        referencia_inventari=f"ART-{emp_a_id.hex[:4]}",
        nom="Electrovalvula 24V 2 polzades",
        unitat_mesura="UNITAT",
        familia="VALVULERIA"
    )
    admin_session.add(article)
    await admin_session.flush()

    fulla_id = uuid.uuid4()
    fulla = FullaPicking(
        id=fulla_id,
        empresa_id=emp_a_id,
        ordre_treball_id=ot_id,
        estat_picking="COMPLETAT"
    )
    admin_session.add(fulla)
    await admin_session.flush()

    linia_id = uuid.uuid4()
    linia = LiniaPicking(
        id=linia_id,
        empresa_id=emp_a_id,
        picking_id=fulla_id,
        article_id=art_id,
        quantitat_prevista=10.0,
        quantitat_carregada_pick_in=10.0,
        quantitat_retornada_pick_out=2.0  # Consum real = 8.0
    )
    admin_session.add(linia)

    # Incidència associada a l'OT
    inc_id = uuid.uuid4()
    inc = Incidencia(
        id=inc_id,
        empresa_id=emp_a_id,
        ordre_treball_id=ot_id,
        ambit="OBRA",
        estat="VERMELL",
        text_observacions="Arrel d'arbre que trenca el conducte principal"
    )
    admin_session.add(inc)

    await admin_session.commit()

    return {
        "empresa_a_id": str(emp_a_id),
        "empresa_b_id": str(emp_b_id),
        "boss_a_email": boss_a.email,
        "boss_b_email": boss_b.email,
        "password": "Password123!",
        "client_a_id": str(client_a_id),
        "ot_id": str(ot_id),
        "ot_codi": ot.codi,
        "article_nom": "Electrovalvula 24V 2 polzades"
    }


@pytest.mark.asyncio
async def test_f2_01_mapa_serveix_dades_reals(f2_eval_setup):
    """TEST-F2-01: El mapa GIS serveix coordenades reals de les feines de l'empresa (Zero Mock Data)."""
    setup = f2_eval_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # Autenticació Boss A
        login_res = await client.post("/auth/login", json={
            "email": setup["boss_a_email"],
            "password": setup["password"]
        })
        assert login_res.status_code == 200
        token_a = login_res.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Empresa-ID": setup["empresa_a_id"]}

        # GET /gestio/feines/mapa
        map_res = await client.get("/gestio/feines/mapa", headers=headers_a)
        assert map_res.status_code == 200
        markers = map_res.json()
        assert len(markers) >= 1

        # Trobar el marcador de la nostra OT
        ot_marker = next((m for m in markers if m["id"] == setup["ot_id"]), None)
        assert ot_marker is not None
        assert ot_marker["codi"] == setup["ot_codi"]
        assert ot_marker["lat"] == pytest.approx(41.4036, abs=0.001)
        assert ot_marker["lng"] == pytest.approx(2.1744, abs=0.001)
        assert ot_marker["client_rao_social"] == "Finca Verda Ecològica S.L."


@pytest.mark.asyncio
async def test_f2_02_bloqueig_optimista_agenda(f2_eval_setup):
    """TEST-F2-02: Bloqueig optimista a l'agendament d'OTs: retorn 409 Conflict si la versió no coincideix."""
    setup = f2_eval_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        login_res = await client.post("/auth/login", json={
            "email": setup["boss_a_email"],
            "password": setup["password"]
        })
        token_a = login_res.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Empresa-ID": setup["empresa_a_id"]}

        ot_id = setup["ot_id"]

        # 1. Primera planificació amb version_id = 1 -> èxit (HTTP 200)
        payload1 = {
            "hora_inici_prevista": datetime(2026, 10, 5, 8, 0, tzinfo=timezone.utc).isoformat(),
            "hora_fi_prevista": datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc).isoformat(),
            "version_id": 1
        }
        res1 = await client.put(f"/gestio/feines/{ot_id}/agendar", json=payload1, headers=headers_a)
        assert res1.status_code == 200, f"Error agendant: {res1.text}"
        data1 = res1.json()
        assert data1["version_id"] == 2

        # 2. Segon intent concurrent amb la versió vella (version_id = 1) -> HTTP 409 Conflict
        res_conflict = await client.put(f"/gestio/feines/{ot_id}/agendar", json=payload1, headers=headers_a)
        assert res_conflict.status_code == 409
        assert "Conflicte de concurrència" in res_conflict.json()["detail"]

        # 3. Intent amb la versió correcta (version_id = 2) -> èxit
        payload2 = {
            "hora_inici_prevista": datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc).isoformat(),
            "hora_fi_prevista": datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc).isoformat(),
            "version_id": 2
        }
        res2 = await client.put(f"/gestio/feines/{ot_id}/agendar", json=payload2, headers=headers_a)
        assert res2.status_code == 200
        assert res2.json()["version_id"] == 3


@pytest.mark.asyncio
async def test_f2_03_rls_mapa_aillament(f2_eval_setup):
    """TEST-F2-03: Aïllament RLS: l'empresa B no pot veure les OTs de l'empresa A al mapa."""
    setup = f2_eval_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # Autenticació Boss B (Empresa B)
        login_res_b = await client.post("/auth/login", json={
            "email": setup["boss_b_email"],
            "password": setup["password"]
        })
        token_b = login_res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Empresa-ID": setup["empresa_b_id"]}

        # GET mapa des d'Empresa B
        map_b = await client.get("/gestio/feines/mapa", headers=headers_b)
        assert map_b.status_code == 200
        # Ha de retornar llista buida [] per a l'Empresa B
        assert map_b.json() == []


@pytest.mark.asyncio
async def test_f2_04_fitxa_360_client(f2_eval_setup):
    """TEST-F2-04: Fitxa 360° del Client recopila intervencions, peces instal·lades i incidències (Spec 012 RF-04)."""
    setup = f2_eval_setup
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        login_res = await client.post("/auth/login", json={
            "email": setup["boss_a_email"],
            "password": setup["password"]
        })
        token_a = login_res.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Empresa-ID": setup["empresa_a_id"]}

        client_id = setup["client_a_id"]

        # GET /gestio/clients/{client_id}/fitxa360
        res = await client.get(f"/gestio/clients/{client_id}/fitxa360", headers=headers_a)
        assert res.status_code == 200, f"Error fitxa 360: {res.text}"
        data = res.json()

        # Validació del Client
        assert data["client"]["id"] == client_id
        assert data["client"]["rao_social"] == "Finca Verda Ecològica S.L."

        # Validació d'Intervencions
        assert len(data["intervencions"]) >= 1
        assert any(it["id"] == setup["ot_id"] for it in data["intervencions"])

        # Validació de Peces Instal·lades (amb càlcul de consum real = 10 - 2 = 8)
        assert len(data["peces_instalades"]) >= 1
        peca = data["peces_instalades"][0]
        assert peca["nom_article"] == "Electrovalvula 24V 2 polzades"
        assert peca["quantitat_instalada"] == 8.0

        # Validació d'Incidències
        assert len(data["incidencies"]) >= 1
        inc = data["incidencies"][0]
        assert "Arrel d'arbre" in inc["text_observacions"]
        assert inc["estat"] == "VERMELL"

        # Validació del Resum
        assert data["resum"]["total_intervencions"] >= 1
        assert data["resum"]["total_peces_instalades"] >= 1
        assert data["resum"]["total_incidencies"] >= 1
        assert data["resum"]["dies_analitzats"] == 365
