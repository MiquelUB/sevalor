import io
import uuid
import zipfile
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
async def test_crm_quota_operaris_i_bloqueig_alta_operaris(
    superadmin_headers: dict[str, str],
) -> None:
    """Verifica l'assignació dinàmica de quota_operaris, l'historial i el bloqueig quan se supera la llicència."""
    suffix = str(uuid.uuid4())[:8]
    payload = {
        "rao_social": f"Agro Quota {suffix} S.L.",
        "nif": "B" + str(uuid.uuid4())[:8].upper(),
        "subdomini": f"agro-{suffix}",
        "vertical": "SEVALOR",
        "pla_subscripcio": "STARTER",
        "quota_operaris": 1,
        "quota_buffer_mb": 400,
        "quota_disc_gb": 10,
        "boss_nif": "11223344A",
        "boss_nom": "Marc",
        "boss_cognoms": "Vila",
        "boss_email": f"marc@agro-{suffix}.cat",
        "boss_telefon": "+34600112233",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/superadmin/tenants/onboarding", json=payload, headers=superadmin_headers
        )
        assert res.status_code == 201, res.text
        tenant = res.json()["tenant"]
        empresa_id = tenant["id"]
        boss_id = tenant["boss_usuari_id"]
        assert tenant["quota_operaris"] == 1
        assert tenant["quota_buffer_mb"] == 400

        # Amb quota_operaris=1, podem crear 1 operari:
        boss_headers = make_tenant_headers(empresa_id, boss_id, "BOSS")
        op1_res = await ac.post(
            "/api/v1/gestio/operaris",
            json={
                "nom": "Operari",
                "cognoms": "Un",
                "nif": f"OP1{suffix[:5]}".upper(),
                "telefon": f"+34699{suffix[:6]}",
                "pin": "4829",
                "rol": "OPERARI",
                "cost_hora": 18.5,
            },
            headers=boss_headers,
        )
        assert op1_res.status_code == 201, op1_res.text

        # Ara hi ha 1 operari actiu. El següent operari ha de ser bloquejat (403) per límit de llicència:
        op2_res = await ac.post(
            "/api/v1/gestio/operaris",
            json={
                "nom": "Operari",
                "cognoms": "Dos",
                "nif": f"OP2{suffix[:5]}".upper(),
                "telefon": f"+34688{suffix[:6]}",
                "pin": "7391",
                "rol": "OPERARI",
                "cost_hora": 18.5,
            },
            headers=boss_headers,
        )
        assert op2_res.status_code == 403
        assert "llicència" in op2_res.json()["detail"].lower()

        # Ampliem la llicència a 6 operaris des del CRM Superadmin i verifiquem l'historial
        upd_quota = await ac.put(
            f"/api/v1/superadmin/tenants/{empresa_id}/quota",
            json={"quota_operaris": 6, "quota_buffer_mb": 600, "motiu": "Ampliació campanya reg"},
            headers=superadmin_headers,
        )
        assert upd_quota.status_code == 200
        assert upd_quota.json()["quota_operaris"] == 6

        detail_res = await ac.get(
            f"/api/v1/superadmin/tenants/{empresa_id}", headers=superadmin_headers
        )
        assert detail_res.status_code == 200
        hist = detail_res.json()["historial_llicencia"]
        assert len(hist) >= 1
        assert hist[0]["operaris_nous"] == 6


@pytest.mark.asyncio
async def test_verifactu_hitl_prefactura_equips_venda_i_hibernacio(
    superadmin_headers: dict[str, str],
) -> None:
    """
    Verifica:
    - Prohibició de rènting en equips IA (només VENDA, 100% editable).
    - Esborrany de prefactura NO final amb els 4 conceptes editables/opcionals.
    - Verificació humana obligatòria (HITL) per emetre factura Veri*factu amb SHA-256 i PDF.
    - Estat HIBERNANT per impagament i conservació permanent de factures i tiquets en donar de baixa.
    """
    suffix = str(uuid.uuid4())[:8]
    payload = {
        "rao_social": f"Hydro Verifactu {suffix} S.L.",
        "nif": "B" + str(uuid.uuid4())[:8].upper(),
        "subdomini": f"hydro-{suffix}",
        "vertical": "HYDROPRO",
        "pla_subscripcio": "PRO",
        "quota_operaris": 8,
        "quota_disc_gb": 50,
        "boss_nif": "99887766B",
        "boss_nom": "Anna",
        "boss_cognoms": "Serra",
        "boss_email": f"anna@hydro-{suffix}.cat",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/superadmin/tenants/onboarding", json=payload, headers=superadmin_headers
        )
        assert res.status_code == 201
        empresa_id = res.json()["tenant"]["id"]

        # 1. Intentar desar un equip amb modalitat RENTING ha de fallar (400 o 422 Pydantic Literal["VENDA"])
        bad_prefactura = await ac.post(
            "/api/v1/superadmin/crm/prefactures",
            json={
                "empresa_id": empresa_id,
                "periode_facturacio": "2026-10",
                "equips_ia_detall": [
                    {"nom": "PC IA", "unitats": 1, "preu_unitari": 500, "modalitat": "RENTING"}
                ],
            },
            headers=superadmin_headers,
        )
        assert bad_prefactura.status_code in (400, 422)

        # 2. Crear Esborrany de Prefactura vàlid (NO FINAL) amb els 4 conceptes editables
        pref_res = await ac.post(
            "/api/v1/superadmin/crm/prefactures",
            json={
                "empresa_id": empresa_id,
                "periode_facturacio": "2026-10",
                "concepte_onboarding": "Onboarding i Llicència Base",
                "import_onboarding": 200.0,
                "concepte_config_ia": "Configuració IA Local",
                "import_config_ia": 150.0,
                "equips_ia_detall": [
                    {
                        "nom": "PC IA Dedicat",
                        "unitats": 1,
                        "preu_unitari": 800.0,
                        "modalitat": "VENDA",
                    },
                    {
                        "nom": "Side Gateway",
                        "unitats": 2,
                        "preu_unitari": 120.0,
                        "modalitat": "VENDA",
                    },
                ],
                "num_operaris": 8,
                "preu_per_operari": 25.0,
                "iva_percent": 21.0,
            },
            headers=superadmin_headers,
        )
        assert pref_res.status_code == 201, pref_res.text
        pref = pref_res.json()
        prefactura_id = pref["id"]
        assert pref["estat"] == "ESBORRANY_PREFACTURA"
        assert pref["numero_factura"] is None
        assert pref["verificada_per_huma"] is False
        # Base = 200 + 150 + (800 + 240) + (8 * 25) = 1590.0
        assert pref["base_imposable"] == 1590.0

        # 3. Editar l'esborrany abans de verificar-lo
        edit_res = await ac.put(
            f"/api/v1/superadmin/crm/prefactures/{prefactura_id}",
            json={
                "empresa_id": empresa_id,
                "periode_facturacio": "2026-10",
                "concepte_onboarding": "Onboarding i Llicència Base",
                "import_onboarding": 200.0,
                "concepte_config_ia": None,
                "import_config_ia": 0.0,
                "equips_ia_detall": [
                    {
                        "nom": "PC IA Dedicat",
                        "unitats": 1,
                        "preu_unitari": 800.0,
                        "modalitat": "VENDA",
                    }
                ],
                "num_operaris": 10,
                "preu_per_operari": 20.0,
                "iva_percent": 21.0,
            },
            headers=superadmin_headers,
        )
        assert edit_res.status_code == 200
        # Nova Base = 200 + 0 + 800 + (10 * 20) = 1200.0
        assert edit_res.json()["base_imposable"] == 1200.0

        # 4. Verificació Humana (HITL) i Emissió Veri*factu
        emit_res = await ac.post(
            f"/api/v1/superadmin/crm/prefactures/{prefactura_id}/verificar-i-emetre",
            headers=superadmin_headers,
        )
        assert emit_res.status_code == 200, emit_res.text
        emesa = emit_res.json()["factura"]
        assert emesa["estat"] == "EMESA_VERIFACTU"
        assert emesa["verificada_per_huma"] is True
        assert emesa["numero_factura"].startswith("SEVALOR-")
        assert len(emesa["hash_actual"]) == 64

        # 5. Descarregar PDF Veri*factu
        pdf_res = await ac.get(
            f"/api/v1/superadmin/crm/factures/{prefactura_id}/pdf",
            headers=superadmin_headers,
        )
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content.startswith(b"%PDF")

        # 6. Marcar factura com a IMPAGADA i passar l'empresa a HIBERNANT
        hib_res = await ac.patch(
            f"/api/v1/superadmin/crm/factures/{prefactura_id}/estat-cobrament",
            json={"estat_cobrament": "IMPAGADA", "passar_a_hibernant": True},
            headers=superadmin_headers,
        )
        assert hib_res.status_code == 200
        tenant_after = await ac.get(
            f"/api/v1/superadmin/tenants/{empresa_id}", headers=superadmin_headers
        )
        assert tenant_after.json()["estat_pagament"] == "HIBERNANT"


@pytest.mark.asyncio
async def test_tiquets_autodiagnostic_pc_apagat_recuperacio_zip_i_telemetria_anonima(
    superadmin_headers: dict[str, str],
) -> None:
    """
    Verifica:
    - Autodiagnòstic d'ordinador local d'empresa apagat en obrir un tiquet i endpoint 503 d'arxiu extern.
    - Botó de recuperació de totes les dades (.zip) i retenció de factures/tiquets després de baixa RGPD.
    - Telemetria anònima d'operaris (PWA-REF sense noms ni NIFs).
    """
    suffix = str(uuid.uuid4())[:8]
    payload = {
        "rao_social": f"Clima Node {suffix} S.L.",
        "nif": "B" + str(uuid.uuid4())[:8].upper(),
        "subdomini": f"clima-{suffix}",
        "vertical": "BUILDINGPRO",
        "pla_subscripcio": "PRO",
        "quota_operaris": 5,
        "quota_disc_gb": 25,
        "boss_nif": "55443322C",
        "boss_nom": "Joan",
        "boss_cognoms": "prat",
        "boss_email": f"joan@clima-{suffix}.cat",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/superadmin/tenants/onboarding", json=payload, headers=superadmin_headers
        )
        assert res.status_code == 201
        empresa_id = res.json()["tenant"]["id"]
        boss_id = res.json()["tenant"]["boss_usuari_id"]

        # Configurar un node_ia_url que apunta a un port local tancat per simular que l'ordinador del client està apagat
        await ac.put(
            f"/api/v1/superadmin/tenants/{empresa_id}/feature-flags",
            json={
                "feature_copilot_ia": True,
                "feature_flota": True,
                "feature_planols": True,
                "feature_telegram": True,
                "node_ia_url": "http://127.0.0.1:59999",
                "node_ia_actiu": True,
            },
            headers=superadmin_headers,
        )

        # 1. Quan l'operari consulta un plànol històric que viu al disc de l'empresa i el PC està apagat -> 503 clar
        operari_headers = make_tenant_headers(empresa_id, boss_id, "OPERARI")
        ext_res = await ac.get(
            "/api/v1/operari/planols/arxiu-extern?cerca=Caldera",
            headers=operari_headers,
        )
        assert ext_res.status_code == 503
        ext_detail = ext_res.json()["detail"]
        assert ext_detail["code"] == "NODE_EMPRESA_OFFLINE"
        assert "ordinador central de la teva empresa està apagat" in ext_detail["message"]

        # 2. Quan obren un tiquet al CRM, el sistema detecta que l'ordinador de l'empresa està apagat
        tiq_res = await ac.post(
            "/api/v1/superadmin/crm/tiquets",
            json={
                "empresa_id": empresa_id,
                "assumpte": "No carrega el plànol de la caldera antiga",
                "descripcio": "L'operari és a l'obra i no pot obrir el plànol històric.",
                "prioritat": "ALTA",
            },
            headers=superadmin_headers,
        )
        assert tiq_res.status_code == 201
        tiq_data = tiq_res.json()
        assert tiq_data["pc_empresa_online_al_crear"] is False
        assert "APAGAT" in (tiq_data["diagnostic_node"]["advertencia"] or "")

        # 3. Exportació / Recuperació de totes les dades de l'empresa en ZIP
        zip_res = await ac.get(
            f"/api/v1/superadmin/tenants/{empresa_id}/recuperar-dades",
            headers=superadmin_headers,
        )
        assert zip_res.status_code == 200
        assert zip_res.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(zip_res.content))
        assert "empresa_metadata.json" in zf.namelist()
        assert "factures_saas_b2b.json" in zf.namelist()

        # 4. Telemetria Anònima RGPD (sense noms ni NIFs d'operaris)
        tel_res = await ac.get("/api/v1/superadmin/telemetria/kpis", headers=superadmin_headers)
        assert tel_res.status_code == 200
        tenants_tel = tel_res.json()["tenants"]
        my_tel = next((t for t in tenants_tel if t["id"] == empresa_id), None)
        assert my_tel is not None
        assert "operaris_connectats" in my_tel
        assert isinstance(my_tel["pwa_sessions_anonimes"], list)
        for sess in my_tel["pwa_sessions_anonimes"]:
            assert sess["pwa_ref"].startswith("PWA-REF-")
            assert "nom" not in sess
            assert "nif" not in sess

        # 5. Executar baixa certificada RGPD i comprovar que els tiquets i factures es mantenen al CRM
        dest_res = await ac.post(
            f"/api/v1/superadmin/tenants/{empresa_id}/destruccio",
            headers=superadmin_headers,
        )
        assert dest_res.status_code == 200
        tiq_list = await ac.get(
            f"/api/v1/superadmin/crm/tiquets?empresa_id={empresa_id}",
            headers=superadmin_headers,
        )
        assert tiq_list.status_code == 200
        assert len(tiq_list.json()) == 1
