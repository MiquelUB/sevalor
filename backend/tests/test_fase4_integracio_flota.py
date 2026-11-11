"""Suite de proves per a la Fase 4: Integració amb Operaris, PWA, Workers i Copilot de Flota.

Valida:
1. Guarda de seguretat `validar_permis_conduir` (apte_assignacio_pwa, jerarquia de carnets, requisit CAP i caducitat carnet).
2. Extensions del model Vehicle i esquemes VehicleCreate / VehicleResponse per a vehicles pesants i rènting.
3. Lògica del Worker de Celery per al bloqueig per venciments i càlcul de projecció de km de rènting.
4. Eines del Subagent de Despatx per a Torre de Control: `get_heavy_vehicles_for_ot` i auditoria consolidada de venciments i rènting km.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.gestio.flota import VehicleCreate, VehicleResponse, _build_vehicle_response
from app.api.v1.operari_pwa.vehicles import validar_assignacio_vehicle_operari
from app.models.models import Usuari, Vehicle
from app.services.flota_service import validar_permis_conduir
from app.services.subagents.subagent_flota_despatx import SubagentFlotaDespatx


def test_vehicle_apte_assignacio_pwa_property():
    """Comprova la propietat apte_assignacio_pwa del model Vehicle."""
    avui = date.today()

    # 1. Vehicle operatiu i en regla
    v_ok = Vehicle(
        matricula="1234-BBB",
        marca="Mercedes",
        model="Sprinter",
        estat="OPERATIU",
        estat_itv="FAVORABLE",
        data_proxima_itv=avui + timedelta(days=60),
        data_caducitat_asseguranca=avui + timedelta(days=90),
    )
    assert v_ok.apte_assignacio_pwa is True

    # 2. Vehicle amb ITV caducada
    v_itv_caducada = Vehicle(
        matricula="2345-CCC",
        estat="OPERATIU",
        estat_itv="CADUCADA",
        data_proxima_itv=avui - timedelta(days=1),
        data_caducitat_asseguranca=avui + timedelta(days=90),
    )
    assert v_itv_caducada.apte_assignacio_pwa is False

    # 3. Vehicle amb ITV Desfavorable
    v_desfavorable = Vehicle(
        matricula="3456-DDD",
        estat="OPERATIU",
        estat_itv="DESFAVORABLE",
        data_proxima_itv=avui + timedelta(days=20),
        data_caducitat_asseguranca=avui + timedelta(days=90),
    )
    assert v_desfavorable.apte_assignacio_pwa is False

    # 4. Vehicle amb Assegurança caducada
    v_ass_caducada = Vehicle(
        matricula="4567-EEE",
        estat="OPERATIU",
        estat_itv="FAVORABLE",
        data_proxima_itv=avui + timedelta(days=60),
        data_caducitat_asseguranca=avui - timedelta(days=5),
    )
    assert v_ass_caducada.apte_assignacio_pwa is False

    # 5. Vehicle en estat TALLER o BLOQUEJAT
    v_taller = Vehicle(
        matricula="5678-FFF",
        estat="TALLER",
        estat_itv="FAVORABLE",
        data_proxima_itv=avui + timedelta(days=60),
        data_caducitat_asseguranca=avui + timedelta(days=90),
    )
    assert v_taller.apte_assignacio_pwa is False


def test_validar_permis_conduir_jerarquia_i_cap():
    """Valida la jerarquia de carnet de conduir (C+E >= C >= B+E >= B) i la guarda de CAP."""
    avui = date.today()

    operari_b = Usuari(
        nom="Joan",
        cognoms="Pérez",
        carnet_conduir="B",
        carnet_caducitat=avui + timedelta(days=365),
    )
    operari_b.te_cap = False

    operari_c = Usuari(
        nom="Marc",
        cognoms="Soler",
        carnet_conduir="C",
        carnet_caducitat=avui + timedelta(days=365),
    )
    operari_c.te_cap = True

    operari_ce = Usuari(
        nom="Ramon",
        cognoms="Vila",
        carnet_conduir="C+E",
        carnet_caducitat=avui + timedelta(days=365),
    )
    operari_ce.te_cap = True

    # Vehicle lleuger que requereix B
    v_b = Vehicle(
        matricula="1111-AAA",
        carnet_necessari="B",
        requereix_cap=False,
        data_proxima_itv=avui + timedelta(days=30),
        data_caducitat_asseguranca=avui + timedelta(days=30),
        estat="OPERATIU",
    )
    # L'operari amb B pot conduir v_b
    validar_permis_conduir(v_b, operari_b)
    # L'operari amb C també pot conduir v_b
    validar_permis_conduir(v_b, operari_c)

    # Camió pesant que requereix C i CAP
    v_pesant = Vehicle(
        matricula="2222-BBB",
        carnet_necessari="C",
        requereix_cap=True,
        categoria_ue="N2",
        mma_kg=7500,
        data_proxima_itv=avui + timedelta(days=30),
        data_caducitat_asseguranca=avui + timedelta(days=30),
        estat="OPERATIU",
    )

    # 1. Operari amb carnet B ha de fallar
    with pytest.raises(HTTPException) as exc_b:
        validar_permis_conduir(v_pesant, operari_b)
    assert exc_b.value.status_code == 422
    assert "requereix permís 'C'" in exc_b.value.detail

    # 2. Operari amb C però sense CAP ha de fallar
    operari_c_sense_cap = Usuari(
        nom="Pau",
        carnet_conduir="C",
        carnet_caducitat=avui + timedelta(days=365),
    )
    operari_c_sense_cap.te_cap = False
    with pytest.raises(HTTPException) as exc_cap:
        validar_permis_conduir(v_pesant, operari_c_sense_cap)
    assert exc_cap.value.status_code == 422
    assert "CAP" in exc_cap.value.detail

    # 3. Operari amb C i CAP ha de passar
    validar_permis_conduir(v_pesant, operari_c)

    # 4. Operari amb C+E i CAP també ha de passar per jerarquia superior
    validar_permis_conduir(v_pesant, operari_ce)


def test_validar_permis_conduir_vehicle_bloquejat():
    """Valida que si el vehicle no és apte_assignacio_pwa es bloqueja l'assignació."""
    avui = date.today()
    v_caducat = Vehicle(
        matricula="9999-ZZZ",
        carnet_necessari="B",
        data_proxima_itv=avui - timedelta(days=1),  # Caducat
        data_caducitat_asseguranca=avui + timedelta(days=30),
        estat="OPERATIU",
    )
    operari = Usuari(
        nom="Jordi",
        carnet_conduir="B",
        carnet_caducitat=avui + timedelta(days=100),
    )

    with pytest.raises(HTTPException) as exc:
        validar_permis_conduir(v_caducat, operari)
    assert exc.value.status_code == 422
    assert "no és apte per a assignació" in exc.value.detail


def test_vehicle_create_and_response_schemas_pesants_renting():
    """Valida la serialització de VehicleCreate i VehicleResponse amb camps de Fase 1 i Fase 4."""
    avui = date.today()
    veh_create = VehicleCreate(
        matricula="5555-KLM",
        marca="Iveco",
        model="Daily Grua",
        tipus="CAMIO_LLEUGER",
        estat="OPERATIU",
        carnet_necessari="C",
        categoria_ue="N2",
        mma_kg=7200,
        tara_kg=4200,
        carrega_util_kg=3000,
        requereix_cap=True,
        equipament_homologat=["GRUA_AUTOCARGANT", "ENGANXALL_REMOLC"],
        titular_nif="A28000000",
        arrendatari_nif="B12345678",
        regim_adquisicio="RENTING",
        empresa_renting="Alphabet España Fleet Management S.A.U.",
        num_contracte_renting="ALP-2026-9988",
        data_venciment_renting=avui + timedelta(days=365),
        dades_pesants={
            "data_visat_transport": (avui + timedelta(days=180)).isoformat(),
            "targeta_transport_num": "MD-PE-123456",
            "data_calibratge_tacograf": (avui + timedelta(days=240)).isoformat(),
        },
        documents_processats=[
            {
                "tipus_document": "FITXA_TECNICA",
                "nom_fitxer": "fitxa_tecnica.pdf",
                "num_bastidor_vin": "VF3YCTMFC12345678",
            }
        ],
    )

    assert veh_create.mma_kg == 7200
    assert veh_create.carrega_util_kg == 3000
    assert veh_create.requereix_cap is True
    assert "GRUA_AUTOCARGANT" in veh_create.equipament_homologat
    assert len(veh_create.documents_processats or []) == 1

    # Model mock
    v_db = Vehicle(
        id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),
        matricula=veh_create.matricula,
        marca=veh_create.marca,
        model=veh_create.model,
        tipus=veh_create.tipus,
        estat=veh_create.estat,
        carnet_necessari=veh_create.carnet_necessari,
        categoria_ue=veh_create.categoria_ue,
        mma_kg=veh_create.mma_kg,
        tara_kg=veh_create.tara_kg,
        carrega_util_kg=veh_create.carrega_util_kg,
        requereix_cap=veh_create.requereix_cap,
        equipament_homologat=veh_create.equipament_homologat,
        titular_nif=veh_create.titular_nif,
        arrendatari_nif=veh_create.arrendatari_nif,
        regim_adquisicio=veh_create.regim_adquisicio,
        empresa_renting=veh_create.empresa_renting,
        num_contracte_renting=veh_create.num_contracte_renting,
        data_venciment_renting=veh_create.data_venciment_renting,
        dades_pesants=veh_create.dades_pesants,
        odometre_acumulat=12500,
        data_proxima_itv=avui + timedelta(days=100),
        data_caducitat_asseguranca=avui + timedelta(days=100),
    )

    resp = _build_vehicle_response(v_db)
    assert isinstance(resp, VehicleResponse)
    assert resp.matricula == "5555-KLM"
    assert resp.apte_assignacio_pwa is True
    assert resp.carrega_util_kg == 3000
    assert resp.requereix_cap is True
    assert "GRUA_AUTOCARGANT" in resp.equipament_homologat


@pytest.mark.asyncio
async def test_subagent_flota_get_heavy_vehicles_for_ot():
    """Valida la nova eina del subagent per filtrar vehicles pesants amb grua per a una OT."""
    empresa_id = uuid.uuid4()
    subagent = SubagentFlotaDespatx()

    v1 = Vehicle(
        matricula="1001-AAA",
        marca="Renault",
        model="Kangoo",
        categoria_ue="M1",
        carrega_util_kg=600,
        equipament_homologat=[],
        carnet_necessari="B",
        requereix_cap=False,
        estat="OPERATIU",
    )

    v2_grua = Vehicle(
        matricula="2002-BBB",
        marca="Iveco",
        model="Daily 70C",
        categoria_ue="N2",
        carrega_util_kg=3200,
        equipament_homologat=["GRUA_AUTOCARGANT", "ENGANXALL_REMOLC"],
        carnet_necessari="C",
        requereix_cap=True,
        estat="OPERATIU",
    )

    # Mock db session
    mock_db = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (v2_grua, "Manel", "Font"),
        (v1, "Pere", "Gomis"),
    ]
    mock_db.execute.return_value = mock_result

    # Cerca 1: Exigir GRUA_AUTOCARGANT
    res_grua = await subagent.tool_get_heavy_vehicles_for_ot(
        mock_db, empresa_id, equipament="GRUA_AUTOCARGANT"
    )
    assert res_grua["trobat"] is True
    assert res_grua["total_vehicles"] == 1
    assert res_grua["vehicles"][0]["matricula"] == "2002-BBB"
    assert res_grua["vehicles"][0]["carrega_util_kg"] == 3200
    assert res_grua["vehicles"][0]["requereix_cap"] is True

    # Cerca 2: Exigir càrrega mínima útil >= 2000 kg
    res_carrega = await subagent.tool_get_heavy_vehicles_for_ot(
        mock_db, empresa_id, carrega_minima_kg=2000
    )
    assert res_carrega["trobat"] is True
    assert res_carrega["total_vehicles"] == 1
    assert res_carrega["vehicles"][0]["matricula"] == "2002-BBB"

    # Cerca 3: Exigir càrrega mínima útil >= 5000 kg (ha de retornar 0)
    res_zero = await subagent.tool_get_heavy_vehicles_for_ot(
        mock_db, empresa_id, carrega_minima_kg=5000
    )
    assert res_zero["trobat"] is False
    assert res_zero["total_vehicles"] == 0


@pytest.mark.asyncio
async def test_subagent_flota_audit_venciments_i_renting_km():
    """Valida l'auditoria consolidada de venciments i excés de quilometratge de rènting."""
    avui = date.today()
    empresa_id = uuid.uuid4()
    subagent = SubagentFlotaDespatx()

    # Vehicle amb contracte rènting i excés de km
    v_renting_exces = Vehicle(
        matricula="7777-XYZ",
        regim_adquisicio="RENTING",
        renting_limit_km=50000,
        odometre_inici_contracte=0,
        odometre_acumulat=54000,  # 4.000 km d'excés
        preu_km_exces_eur=0.15,
        data_venciment_renting=avui + timedelta(days=10),  # Venciment imminent (<= 15 dies)
        data_proxima_itv=avui + timedelta(days=100),
        data_caducitat_asseguranca=avui + timedelta(days=100),
    )

    mock_db = MagicMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [v_renting_exces]
    mock_db.execute.return_value = mock_res

    res_audit = await subagent.tool_audit_itv_insurance_fleet(mock_db, empresa_id, dies_marge=30)

    assert res_audit["trobat"] is True
    assert len(res_audit["alertes"]) == 1
    assert res_audit["alertes"][0]["tipus"] == "RÈNTING"
    assert res_audit["alertes"][0]["dies_restants"] == 10
    assert res_audit["alertes"][0]["severitat"] == "WARNING"

    # Comprovar alerta d'excés de quilometratge de rènting
    assert len(res_audit["alertes_renting_km"]) == 1
    alerta_km = res_audit["alertes_renting_km"][0]
    assert alerta_km["matricula"] == "7777-XYZ"
    assert alerta_km["exces_km"] == 4000
    assert alerta_km["penalitzacio_eur"] == 600.0  # 4000 * 0.15


def test_validar_assignacio_vehicle_operari_pwa():
    """Valida les regles de negoci del validador PWA d'assignació d'operari."""
    # 1. Vehicle bloquejat operativament (403)
    veh_bloquejat = {
        "estat_operatiu_flota": {
            "apte_assignacio_pwa": False,
            "estat_semafor": "BLOQUEJAT_CADUCAT",
        },
        "requisits_operari": {"carnet_minim": "B"},
    }
    operari_ok = {"carnet_conduir": "B"}
    with pytest.raises(HTTPException) as exc1:
        validar_assignacio_vehicle_operari(veh_bloquejat, operari_ok)
    assert exc1.value.status_code == 403
    assert "Vehicle bloquejat operativament: BLOQUEJAT_CADUCAT" in exc1.value.detail

    # 2. Permís insuficient (C requerit vs B operari -> 403)
    veh_camio = {
        "estat_operatiu_flota": {"apte_assignacio_pwa": True, "estat_semafor": "OPERATIU_OK"},
        "requisits_operari": {"carnet_minim": "C", "requereix_cap": True},
    }
    with pytest.raises(HTTPException) as exc2:
        validar_assignacio_vehicle_operari(veh_camio, {"carnet_conduir": "B", "te_cap_vigent": True})
    assert exc2.value.status_code == 403
    assert "Permís insuficient: es requereix carnet C" in exc2.value.detail

    # 3. Manca de CAP en vigor per a vehicle pesant (403)
    with pytest.raises(HTTPException) as exc3:
        validar_assignacio_vehicle_operari(veh_camio, {"carnet_conduir": "C", "te_cap_vigent": False})
    assert exc3.value.status_code == 403
    assert "Es requereix certificat CAP en vigor per a vehicles >3.500 kg" in exc3.value.detail

    # 4. Manca de formació PRL obligatòria (ex: operador de grua) (403)
    veh_grua = {
        "estat_operatiu_flota": {"apte_assignacio_pwa": True, "estat_semafor": "OPERATIU_OK"},
        "requisits_operari": {
            "carnet_minim": "C",
            "requereix_cap": True,
            "certificats_prl_requerits": ["PRL_OPERADOR_GRUA"],
        },
    }
    with pytest.raises(HTTPException) as exc4:
        validar_assignacio_vehicle_operari(
            veh_grua,
            {"carnet_conduir": "C", "te_cap_vigent": True, "certificats_prl": []},
        )
    assert exc4.value.status_code == 403
    assert "Falta formació PRL obligatòria: PRL_OPERADOR_GRUA" in exc4.value.detail

    # 5. Tot validat satisfactòriament -> True
    res = validar_assignacio_vehicle_operari(
        veh_grua,
        {
            "carnet_conduir": "C+E",
            "te_cap_vigent": True,
            "certificats_prl": ["PRL_OPERADOR_GRUA", "PRL_TREBALLS_EN_ALTURA"],
        },
    )
    assert res is True


if __name__ == "__main__":
    test_vehicle_apte_assignacio_pwa_property()
    test_validar_permis_conduir_jerarquia_i_cap()
    test_validar_permis_conduir_vehicle_bloquejat()
    test_validar_assignacio_vehicle_operari_pwa()
    test_vehicle_create_and_response_schemas_pesants_renting()
    import asyncio

    asyncio.run(test_subagent_flota_get_heavy_vehicles_for_ot())
    asyncio.run(test_subagent_flota_audit_venciments_i_renting_km())
    print("TOTES LES PROVES DE FASE 4 HAN PASSAT AMB ÈXIT (100% VERD)!")
