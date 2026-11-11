from datetime import date

import pytest
from fastapi import HTTPException

from app.api.v1.operari_pwa.vehicles import validar_assignacio_vehicle_operari
from app.services.flota_service import consolidar_i_validar_ocr_flota

TENANT_CIF = "B55891234"
DATA_AVUI = date(2026, 11, 11)


def test_fase1_i_2_furgoneta_propia_n1_operatiu_ok():
    """Valida l'alta d'una Ford Transit Custom N1 en propietat amb tota la documentació en vigor."""
    docs = [
        {
            "nom_fitxer": "permis_circulacio.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "4829-LWT",
            "bastidor": "WF0YXXTTGYNJ58291",
            "marca": "Ford",
            "model": "Transit Custom",
            "titular": "CAMPOPRO SERVEIS AGRICOLES SL",
            "titular_nif": "B55891234",
            "codi_servei_dgt": "B00",
            "data_matriculacio": "2022-03-14",
        },
        {
            "nom_fitxer": "fitxa_eitv.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "4829-LWT",
            "bastidor": "WF0YXXTTGYNJ58291",
            "categoria_ue": "N1",
            "mma_kg": 3000,
            "tara_kg": 2015,
            "tipus": "DIESEL",
            "distintiu_ambiental": "C",
        },
        {
            "nom_fitxer": "informe_itv.pdf",
            "tipus_document": "INFORME_ITV",
            "matricula": "4829-LWT",
            "bastidor": "WF0YXXTTGYNJ58291",
            "estat_itv": "FAVORABLE",
            "data_inspeccio_itv": "2026-03-12",
            "data_proxima_itv": "2028-03-12",
            "odometre_acumulat": 64320,
        },
        {
            "nom_fitxer": "polissa_allianz.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "4829-LWT",
            "bastidor": "WF0YXXTTGYNJ58291",
            "companyia_asseguradora": "Allianz",
            "polissa_asseguranca": "048-99283741-02",
            "data_caducitat_asseguranca": "2027-03-14",
        }
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif=TENANT_CIF, avui=DATA_AVUI)

    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["regim_adquisicio"] == "PROPIETAT"
    assert res["titularitat_i_tenant"]["conciliacio_tenant"] == "VALIDAT_COM_PROPIETARI"
    assert res["capacitats_ot"]["carrega_util_kg"] == 985
    assert res["requisits_operari"]["carnet_minim"] == "B"
    assert res["requisits_operari"]["requereix_cap"] is False
    assert res["estat_operatiu_flota"]["estat_semafor"] == "OPERATIU_OK"
    assert res["estat_operatiu_flota"]["apte_assignacio_pwa"] is True
    assert len(res["documents_processats"]) == 4


def test_fase3_renting_venciment_imminent_i_conciliacio_arval():
    """Valida la Renault Kangoo de rènting amb ITV (5 dies) i Assegurança (7 dies) a punt de caducar."""
    docs = [
        {
            "nom_fitxer": "permis_arval.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "marca": "Renault",
            "model": "Kangoo Furgón",
            "titular": "ARVAL SERVICE LEASE SA",
            "titular_nif": "A81573479",
            "arrendatari": "CAMPOPRO SERVEIS AGRICOLES SL",
            "arrendatari_nif": "B55891234",
            "codi_servei_dgt": "A12",
            "data_matriculacio": "2020-11-18",
            "categoria_ue": "N1",
            "mma_kg": 1950,
            "tara_kg": 1346,
        },
        {
            "nom_fitxer": "informe_itv_2024.pdf",
            "tipus_document": "INFORME_ITV",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "estat_itv": "FAVORABLE_LEUS",
            "data_inspeccio_itv": "2024-11-16",
            "data_proxima_itv": "2026-11-16",
            "odometre_acumulat": 97840,
        },
        {
            "nom_fitxer": "polissa_mapfre.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "companyia_asseguradora": "Mapfre",
            "polissa_asseguranca": "071-2400981234-99",
            "data_caducitat_asseguranca": "2026-11-18",
        },
        {
            "nom_fitxer": "contracte_arval.pdf",
            "tipus_document": "CONTRACTE_RENTING",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "arrendatari_nif": "B55891234",
            "num_contracte_renting": "CTR-ARV-2020-883921",
            "data_venciment_renting": "2026-11-18",
            "renting_limit_km": 120000,
        }
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif=TENANT_CIF, avui=DATA_AVUI)

    # Conciliació Arval vs Tenant
    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["regim_adquisicio"] == "RENTING"
    assert res["titularitat_i_tenant"]["conciliacio_tenant"] == "VALIDAT_COM_ARRENDATARI"

    # Semàfor d'alerta imminent i bloqueig programat l'endemà de caducar la ITV (2026-11-17)
    assert res["estat_operatiu_flota"]["estat_semafor"] == "ALERTA_VENCIMENT_IMMINENT"
    assert res["estat_operatiu_flota"]["apte_assignacio_pwa"] is True
    assert res["estat_operatiu_flota"]["bloqueig_automatic_programat_el"] == "2026-11-17"

    # Alertes generades amb severitat WARNING
    alertes_warning = [a for a in res["alertes_flota_workers"] if a["severitat"] == "WARNING"]
    assert len(alertes_warning) == 3
    assert res["control_renting_i_costos"]["km_restants_disponibles"] == 22160
    assert res["control_renting_i_costos"]["risc_penalitzacio_km"] is False


def test_fase3_i_4_camio_pesant_n3_grua_i_bloqueig_operari_sense_carnet():
    """Valida un camió Iveco Eurocargo 18T (N3) amb grua Palfinger i les restriccions d'operari."""
    docs = [
        {
            "nom_fitxer": "permis_camio.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "9104-MBB",
            "bastidor": "ZCFA81TN402739184",
            "marca": "Iveco",
            "model": "Eurocargo ML180E28",
            "titular": "CAMPOPRO SERVEIS AGRICOLES SL",
            "titular_nif": "B55891234",
            "categoria_ue": "N3",
            "mma_kg": 18000,
            "tara_kg": 8420,
            "equipament_homologat": ["GRUA_AUTOCARGANT", "CAIXA_BASCULANT"],
            "data_proxima_itv": "2027-05-18",
            "data_calibratge_tacograf": "2027-05-15",
            "data_caducitat_asseguranca": "2027-05-22",
            "rc_explotacio_grua": True,
        },
        {
            "nom_fitxer": "targeta_mpc.pdf",
            "tipus_document": "TARGETA_TRANSPORT",
            "matricula": "9104-MBB",
            "bastidor": "ZCFA81TN402739184",
            "targeta_transport_tipus": "MPC",
            "targeta_transport_num": "MPC-12948573",
            "data_visat_transport": "2027-04-30",
        }
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif=TENANT_CIF, avui=DATA_AVUI)

    assert res["carnet_necessari"] == "C"
    assert res["requisits_operari"]["requereix_cap"] is True
    assert "OPERADOR_GRUA_CAMIO" in res["requisits_operari"]["certificats_prl_requerits"]
    assert res["regulacio_pesants"]["aplica_regim_pesant"] is True
    assert res["capacitats_ot"]["carrega_util_kg"] == 9580
    assert res["capacitats_ot"]["apte_grua_autocargant"] is True
    assert res["estat_operatiu_flota"]["documents_obligatoris_pendents"] == []

    # Fase 4: Comprovació d'assignació a operari amb carnet B -> Ha de denegar (403)
    operari_furgo = {"carnet_conduir": "B", "te_cap_vigent": False, "certificats_prl": []}
    with pytest.raises(HTTPException) as exc:
        validar_assignacio_vehicle_operari(res, operari_furgo)
    assert exc.value.status_code == 403
    assert "carnet C" in exc.value.detail

    # Operari amb carnet C + CAP però sense certificat PRL de Grua -> Ha de denegar (403)
    operari_camio_sense_grua = {"carnet_conduir": "C", "te_cap_vigent": True, "certificats_prl": []}
    with pytest.raises(HTTPException) as exc_prl:
        validar_assignacio_vehicle_operari(res, operari_camio_sense_grua)
    assert exc_prl.value.status_code == 403
    assert "OPERADOR_GRUA_CAMIO" in exc_prl.value.detail

    # Operari completament qualificat -> Permès (True)
    operari_qualificat = {
        "carnet_conduir": "C+E",
        "te_cap_vigent": True,
        "certificats_prl": ["OPERADOR_GRUA_CAMIO"]
    }
    assert validar_assignacio_vehicle_operari(res, operari_qualificat) is True


def test_fase3_rebuig_per_discrepancia_vin_entre_documents():
    """Verifica que si es barreja la fitxa tècnica d'un vehicle amb l'assegurança d'un altre, es bloqueja."""
    docs_barrejats = [
        {
            "nom_fitxer": "fitxa_1.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "4829-LWT",
            "bastidor": "WF0YXXTTGYNJ58291",
            "titular_nif": "B55891234",
        },
        {
            "nom_fitxer": "polissa_erronia.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "4829-LWT",
            "bastidor": "VF1FW5A0A64899999",  # VIN diferent!
            "titular_nif": "B55891234",
        }
    ]

    res = consolidar_i_validar_ocr_flota(docs_barrejats, tenant_cif=TENANT_CIF, avui=DATA_AVUI)

    assert res["status"] == "PENDENT_REVISIO_MANUAL"
    assert res["estat_operatiu_flota"]["coherencia_vin_matricula_entre_docs"] is False
    assert res["estat_operatiu_flota"]["apte_assignacio_pwa"] is False
    assert res["estat_operatiu_flota"]["estat_semafor"] == "BLOQUEJAT_INCIDENCIA"


def test_esquema_definitiu_ocr_draft_completesa_7314_ljh():
    """Valida la presència de totes les 4 peces noves del .json definitiu per a l'OCR draft."""
    docs = [
        {
            "nom_fitxer": "permis_circulacio.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "marca": "Renault",
            "model": "Kangoo Furgón Profesional",
            "titular": "ARVAL SERVICE LEASE SA",
            "titular_nif": "A81573479",
            "arrendatari": "CAMPOPRO SERVEIS AGRICOLES SL",
            "arrendatari_nif": "B55891234",
            "codi_servei_dgt": "A12",
            "data_matriculacio": "2020-11-18",
            "categoria_ue": "N1",
            "mma_kg": 1950,
            "tara_kg": 1346,
            "tipus": "DIESEL",
            "distintiu_ambiental": "C",
        },
        {
            "nom_fitxer": "fitxa_tecnica_eitv.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "equipament_homologat": ["MAMPARA_CARREGA"],
        },
        {
            "nom_fitxer": "informe_itv_2024.pdf",
            "tipus_document": "INFORME_ITV",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "estat_itv": "FAVORABLE_LEUS",
            "data_inspeccio_itv": "2024-11-16",
            "data_proxima_itv": "2026-11-16",
            "odometre_acumulat": 97840,
        },
        {
            "nom_fitxer": "polissa_mapfre.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "companyia_asseguradora": "Mapfre",
            "polissa_asseguranca": "071-2400981234-99",
            "data_caducitat_asseguranca": "2026-11-18",
        },
        {
            "nom_fitxer": "certificat_arval_renting.pdf",
            "tipus_document": "CONTRACTE_RENTING",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "arrendatari_nif": "B55891234",
            "num_contracte_renting": "CTR-ARV-2020-883921",
            "data_venciment_renting": "2026-11-18",
            "renting_limit_km": 120000,
        },
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif=TENANT_CIF, avui=DATA_AVUI)

    # 1. Projecció de Rènting i Costos
    c_renting = res["control_renting_i_costos"]
    assert c_renting["es_renting_o_leasing"] is True
    assert c_renting["km_restants_disponibles"] == 22160
    assert c_renting["risc_penalitzacio_km"] is False
    assert "mitjana_km_diaris" in c_renting
    assert "km_projectats_fi_contracte" in c_renting

    # 2. Match directe amb RRHH i Operaris
    req_op = res["requisits_operari"]
    assert req_op["carnet_minim"] == "B"
    assert req_op["requereix_cap"] is False
    assert req_op["requereix_targeta_conductor_tacograf"] is False
    assert isinstance(req_op["certificats_prl_requerits"], list)

    # 3. Capacitats per al Planificador d'OT
    cap_ot = res["capacitats_ot"]
    assert cap_ot["categoria_ue"] == "N1"
    assert cap_ot["classificacio_dgt"] == "2400"
    assert cap_ot["carrega_util_kg"] == 604
    assert cap_ot["mmr_amb_fre_kg"] == 1050
    assert cap_ot["mmr_sense_fre_kg"] == 670
    assert cap_ot["dimensions_mm"]["llargada"] == 4282
    assert "MAMPARA_CARREGA" in cap_ot["equipament_homologat"]

    # 4. Detall ITV i Assegurança enriquits
    assert res["detall_itv"]["periodicitat_actual_mesos"] == 24
    assert res["detall_itv"]["propera_periodicitat_mesos"] == 12
    assert res["detall_itv"]["defectes_detectats"][0]["gravetat"] == "DL"
    assert res["detall_asseguranca"]["modalitat"] == "TOT_RISC_FRANQUICIA"
    assert res["detall_asseguranca"]["franquicia_euros"] == 150.0

    # 5. Persistència DocumentFlota i SovereignStorage
    for doc in res["documents_processats"]:
        assert doc["accio_persistencia"] == "UPSERT_DOCUMENT_FLOTA"
        assert "hash_sha256" in doc and len(doc["hash_sha256"]) == 64

    # 6. Alertes amigables per a workers i copilot
    for al in res["alertes_flota_workers"]:
        assert "missatge" in al and len(al["missatge"]) > 10


if __name__ == "__main__":
    test_fase1_i_2_furgoneta_propia_n1_operatiu_ok()
    test_fase3_renting_venciment_imminent_i_conciliacio_arval()
    test_fase3_i_4_camio_pesant_n3_grua_i_bloqueig_operari_sense_carnet()
    test_fase3_rebuig_per_discrepancia_vin_entre_documents()
    test_esquema_definitiu_ocr_draft_completesa_7314_ljh()
    print("ALL FASE 5 TESTS (test_ocr_flota_fases_complet.py) PASSED SUCCESSFULLY!")
