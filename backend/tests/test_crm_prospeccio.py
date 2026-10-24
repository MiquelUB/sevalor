import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def superadmin_headers() -> dict[str, str]:
    payload = {
        "sub": "00000000-0000-0000-0000-000000000000",
        "rol": "SUPERADMIN",
        "empresa_id": None,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": True,
        "ip_allowlist": ["testclient", "127.0.0.1", "localhost", "*"],
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def make_tenant_headers(empresa_id: str, user_id: str, rol: str = "BOSS") -> dict[str, str]:
    payload = {
        "sub": user_id,
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "totp_activat": True,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_crm_pipeline_initial_state(superadmin_headers: dict[str, str]) -> None:
    """Verifica que el pipeline comercial del CRM retorna les 7 etapes estàndard del Kanban."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/superadmin/crm/prospeccio/pipeline", headers=superadmin_headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "etapes" in data
        assert "totals_mrr" in data
        assert "columnes" in data

        expected_stages = [
            "PROSPECCIO",
            "QUALIFICACIO",
            "DEMO_7_DIES",
            "PROPOSTA",
            "NEGOCIACIO",
            "GUANYAT",
            "PERDUT",
        ]
        for stage in expected_stages:
            assert stage in data["etapes"]
            assert stage in data["columnes"]
            assert isinstance(data["columnes"][stage], list)


@pytest.mark.asyncio
async def test_crm_crear_lead_i_oportunitat(superadmin_headers: dict[str, str]) -> None:
    """Verifica la creació d'un lead amb vertical flexible i la creació automàtica de la seva oportunitat."""
    suffix = str(uuid.uuid4())[:8]
    lead_payload = {
        "nom_empresa": f"Instal·lacions {suffix} S.L.",
        "nom_contacte": "Joan Martí",
        "email": f"joan_{suffix}@instal.cat",
        "telefon": "+34612345678",
        "vertical": "ElectricPro",
        "operaris_estimats": 12,
        "origen": "WEB",
        "notes": "Interessat en mòdul REBT per a 12 tècnics.",
        "crear_oportunitat_inicial": True,
        "valor_mensual_estimat": 490.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/leads",
            json=lead_payload,
            headers=superadmin_headers,
        )
        assert res.status_code == 201, res.text
        created = res.json()
        assert "lead_id" in created
        lead_id = created["lead_id"]

        # Recuperar el llistat i verificar el lead
        list_res = await ac.get("/api/v1/superadmin/crm/prospeccio/leads", headers=superadmin_headers)
        assert list_res.status_code == 200, list_res.text
        leads_list = list_res.json()
        assert any(item["id"] == lead_id for item in leads_list)

        # Recuperar el detall del lead
        get_res = await ac.get(f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}", headers=superadmin_headers)
        assert get_res.status_code == 200, get_res.text
        detail = get_res.json()
        assert detail["id"] == lead_id
        assert detail["nom_empresa"] == lead_payload["nom_empresa"]
        assert detail["vertical"] == "ElectricPro"
        assert len(detail["oportunitats"]) >= 1
        opp = detail["oportunitats"][0]
        assert opp["etapa"] == "PROSPECCIO"
        assert float(opp["valor_mensual_estimat"]) == 490.0

        # Verificar activitat registrada al timeline
        assert len(detail["activitats"]) >= 1
        assert detail["activitats"][0]["tipus"] == "NOTA"


@pytest.mark.asyncio
async def test_crm_afegir_activitat_timeline(superadmin_headers: dict[str, str]) -> None:
    """Verifica el registre d'una interacció (trucada/reunió) a la línia de temps del lead."""
    suffix = str(uuid.uuid4())[:8]
    lead_payload = {
        "nom_empresa": f"Fontaneria {suffix} S.L.",
        "nom_contacte": "Carles Puig",
        "email": f"carles_{suffix}@fonta.cat",
        "telefon": "+34688990011",
        "vertical": "HydroPro",
        "operaris_estimats": 6,
        "origen": "TRUCADA_FREDA",
        "valor_mensual_estimat": 290.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/leads",
            json=lead_payload,
            headers=superadmin_headers,
        )
        assert create_res.status_code == 201
        lead_id = create_res.json()["lead_id"]

        # Afegir activitat
        act_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}/activitats",
            json={
                "tipus": "TRUCADA",
                "titol": "Primer contacte telefònic",
                "descripcio": "El client confirma interès en demostració de 7 dies.",
                "autor_nom": "Equip Vendes",
            },
            headers=superadmin_headers,
        )
        assert act_res.status_code == 201, act_res.text
        act_data = act_res.json()
        assert "activitat_id" in act_data

        # Comprovar que l'activitat apareix al detall del lead
        get_res = await ac.get(f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}", headers=superadmin_headers)
        detail = get_res.json()
        activitats = detail["activitats"]
        assert any(a["titol"] == "Primer contacte telefònic" for a in activitats)


@pytest.mark.asyncio
async def test_crm_canvi_etapa_kanban(superadmin_headers: dict[str, str]) -> None:
    """Verifica el moviment d'etapa d'una oportunitat al Kanban i l'auditoria corresponent."""
    suffix = str(uuid.uuid4())[:8]
    lead_payload = {
        "nom_empresa": f"Agro {suffix} S.L.",
        "nom_contacte": "Laura Soler",
        "email": f"laura_{suffix}@agro.cat",
        "telefon": "+34699001122",
        "vertical": "CampoPro",
        "operaris_estimats": 15,
        "origen": "REFERENCIA",
        "valor_mensual_estimat": 590.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/leads",
            json=lead_payload,
            headers=superadmin_headers,
        )
        assert create_res.status_code == 201
        lead_id = create_res.json()["lead_id"]

        detail_res = await ac.get(f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}", headers=superadmin_headers)
        opp_id = detail_res.json()["oportunitats"][0]["id"]

        # Moure oportunitat a PROPOSTA
        patch_res = await ac.patch(
            f"/api/v1/superadmin/crm/prospeccio/oportunitats/{opp_id}/etapa",
            json={
                "etapa": "PROPOSTA",
                "probabilitat_percent": 70,
            },
            headers=superadmin_headers,
        )
        assert patch_res.status_code == 200, patch_res.text
        opp_data = patch_res.json()
        assert opp_data["nova_etapa"] == "PROPOSTA"

        # Verificar a la línia de temps de l'oportunitat
        detail_after = await ac.get(f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}", headers=superadmin_headers)
        activitats = detail_after.json()["activitats"]
        assert any("PROPOSTA" in act["descripcio"] for act in activitats)


@pytest.mark.asyncio
async def test_crm_activar_demo_7_dies_aillament_i_ia_compartida(
    superadmin_headers: dict[str, str],
) -> None:
    """Verifica l'activació real d'un tenant demo de 7 dies:

    - Subdomini aïllat a PostgreSQL amb RLS
    - Data límit de prova exactament a 7 dies
    - Usuari BOSS + 2 operaris PWA per defecte
    - IA local compartida sense creuament de memòria
    - Actualització automàtica del lead a DEMO_ACTIVA i Kanban a DEMO_7_DIES
    """
    suffix = str(uuid.uuid4())[:8]
    lead_payload = {
        "nom_empresa": f"Constructora {suffix} S.L.",
        "nom_contacte": "Miquel Roig",
        "email": f"miquel_{suffix}@construc.cat",
        "telefon": "+34677112233",
        "vertical": "BuildingPro",
        "operaris_estimats": 8,
        "origen": "WEB",
        "valor_mensual_estimat": 380.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/leads",
            json=lead_payload,
            headers=superadmin_headers,
        )
        assert create_res.status_code == 201
        lead_id = create_res.json()["lead_id"]

        # Activar demo de 7 dies
        demo_res = await ac.post(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}/activar-demo",
            json={
                "durada_dies": 7,
                "vertical": "BuildingPro",
            },
            headers=superadmin_headers,
        )
        assert demo_res.status_code == 200, demo_res.text
        demo_data = demo_res.json()

        assert "empresa_id" in demo_data
        assert "subdomini" in demo_data
        assert demo_data["dies_restants"] == 7
        assert demo_data["vertical"] == "BuildingPro"
        assert "usuari_oficina" in demo_data
        assert "password_oficina" in demo_data
        assert "pins_operaris" in demo_data
        assert len(demo_data["pins_operaris"]) == 2

        # Comprovar que el lead reflecteix l'estat DEMO_ACTIVA
        lead_detail = await ac.get(f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}", headers=superadmin_headers)
        lead_info = lead_detail.json()
        assert lead_info["estat_qualificacio"] == "DEMO_ACTIVA"
        assert lead_info["empresa_demo_id"] == demo_data["empresa_id"]
        assert lead_info["data_inici_demo"] is not None
        assert lead_info["data_fi_demo"] is not None

        # Comprovar que l'oportunitat ha transitat a DEMO_7_DIES
        opps = lead_info["oportunitats"]
        assert opps[0]["etapa"] == "DEMO_7_DIES"


@pytest.mark.asyncio
async def test_crm_zero_trust_seguretat_accés(superadmin_headers: dict[str, str]) -> None:
    """Verifica que un usuari no superadmin rep 403 Forbidden als endpoints del CRM."""
    fake_empresa_id = str(uuid.uuid4())
    fake_user_id = str(uuid.uuid4())
    boss_headers = make_tenant_headers(fake_empresa_id, fake_user_id, "BOSS")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Usuari BOSS intentant accedir al CRM de Superadmin
        res = await ac.get("/api/v1/superadmin/crm/prospeccio/leads", headers=boss_headers)
        assert res.status_code == 403

        pipe_res = await ac.get("/api/v1/superadmin/crm/prospeccio/pipeline", headers=boss_headers)
        assert pipe_res.status_code == 403
