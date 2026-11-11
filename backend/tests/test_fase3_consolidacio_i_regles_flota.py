"""Tests de verificacio per a la Fase 3: Consolidacio Multi-Document i Motor de Regles a flota_service.py."""
from datetime import date

from app.services.flota_service import consolidar_i_validar_ocr_flota


def test_coherencia_creuada_coincident():
    """Verifica que quan tots els documents comparteixen matrícula i VIN, la coherència és vàlida."""
    docs = [
        {
            "nom_fitxer": "fitxa_tecnica.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "4321-KMN",
            "bastidor": "VF1FW5A0A64829103",
            "marca": "Renault",
            "model": "Kangoo",
            "mma_kg": 2100,
            "tara_kg": 1400,
            "data_matriculacio": "2025-06-01",
            "data_proxima_itv": "2027-06-01",
            "estat_itv": "FAVORABLE",
        },
        {
            "nom_fitxer": "permis_circulacio.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "4321-KMN",
            "bastidor": "VF1FW5A0A64829103",
            "titular": "CAMPOPRO SERVEIS AGRICOLES SL",
            "titular_nif": "B55891234",
        },
        {
            "nom_fitxer": "asseguranca.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "4321-KMN",
            "companyia_asseguradora": "Mapfre",
            "polissa_asseguranca": "POL-12345",
            "data_caducitat_asseguranca": "2027-06-01",
        },
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif="B55891234", data_referencia=date(2026, 11, 11))

    assert res["coherencia_creuada_vin_matricula"] is True
    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["validacio_tenant_cif"] == "COINCIDENT_PROPIETARI"
    assert res["regim_adquisicio"] == "PROPIETAT"
    assert res["estat_semafor"] == "OPERATIU_OK"
    assert res["apte_assignacio_pwa"] is True
    assert res["carrega_util_kg"] == 700  # 2100 - 1400


def test_coherencia_creuada_discrepancia_detectada():
    """Verifica que si es puja la pòlissa d'un altre vehicle, es bloqueja i alerta."""
    docs = [
        {
            "nom_fitxer": "fitxa_tecnica.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "4321-KMN",
            "bastidor": "VF1FW5A0A64829103",
        },
        {
            "nom_fitxer": "polissa_aliena.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "9104-MBB",  # Discrepància!
            "bastidor": "ZCFA81TN402739184",  # Discrepància!
        },
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif="B55891234", data_referencia=date(2026, 11, 11))

    assert res["coherencia_creuada_vin_matricula"] is False
    assert res["status"] == "PENDENT_REVISIO_MANUAL"
    errors = res["estat_operatiu_saas"]["errors_coherencia"]
    assert any("matrícules" in e for e in errors)
    assert any("bastidor" in e for e in errors)


def test_conciliacio_multitenant_renting():
    """Verifica que si el titular és Arval però l'arrendatari és el tenant, es concilia com a RÈNTING."""
    docs = [
        {
            "nom_fitxer": "contracte_renting.pdf",
            "tipus_document": "CONTRACTE_RENTING",
            "matricula": "7314-LJH",
            "bastidor": "VF1FW5A0A64829103",
            "titular": "ARVAL SERVICE LEASE, S.A.",
            "titular_nif": "A81573479",
            "arrendatari_nif": "B55891234",
            "empresa_renting": "Arval Service Lease",
            "num_contracte_renting": "CTR-ARV-2020-883921",
            "data_venciment_renting": "2027-11-18",
        },
        {
            "nom_fitxer": "permis_circulacio.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "7314-LJH",
        },
        {
            "nom_fitxer": "fitxa.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "7314-LJH",
            "data_proxima_itv": "2027-11-16",
        },
        {
            "nom_fitxer": "asseguranca.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "7314-LJH",
            "data_caducitat_asseguranca": "2027-11-18",
        },
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif="B55891234", data_referencia=date(2026, 11, 11))

    assert res["validacio_tenant_cif"] == "COINCIDENT_ARRENDATARI"
    assert res["regim_adquisicio"] == "RENTING"
    assert res["empresa_renting"] == "Arval Service Lease"
    assert res["num_contracte_renting"] == "CTR-ARV-2020-883921"


def test_semafor_operatiu_bloquejat_per_caducitat():
    """Verifica que si l'assegurança o ITV ha caducat (<= 0 dies), el vehicle queda bloquejat per circular."""
    docs = [
        {
            "nom_fitxer": "itv_caducada.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "1122-CCC",
            "data_proxima_itv": "2026-11-01",  # Caducat respecte a 2026-11-11 (-10 dies)
            "estat_itv": "FAVORABLE",
        },
        {
            "nom_fitxer": "permis.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "1122-CCC",
        },
        {
            "nom_fitxer": "asseguranca.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "1122-CCC",
            "data_caducitat_asseguranca": "2027-05-01",
        },
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif="B55891234", data_referencia=date(2026, 11, 11))

    assert res["estat_semafor"] == "BLOQUEJAT_CADUCAT"
    assert res["apte_assignacio_pwa"] is False
    critiques = [a for a in res["alertes_programades"] if a["severitat"] == "CRITICAL"]
    assert len(critiques) >= 1
    assert critiques[0]["tipus"] == "ITV_CADUCAT"
    assert critiques[0]["dies_restants"] == -10


def test_semafor_operatiu_alerta_imminent():
    """Verifica que si un venciment és en 1-15 dies, el semàfor és WARNING però és apte."""
    docs = [
        {
            "nom_fitxer": "itv_imminent.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "1122-CCC",
            "data_proxima_itv": "2026-11-18",  # En 7 dies respecte a 2026-11-11
            "estat_itv": "FAVORABLE",
        },
        {
            "nom_fitxer": "permis.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "1122-CCC",
        },
        {
            "nom_fitxer": "asseguranca.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "1122-CCC",
            "data_caducitat_asseguranca": "2027-05-01",
        },
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif="B55891234", data_referencia=date(2026, 11, 11))

    assert res["estat_semafor"] == "ALERTA_VENCIMENT_IMMINENT"
    assert res["apte_assignacio_pwa"] is True
    warnings = [a for a in res["alertes_programades"] if a["severitat"] == "WARNING"]
    assert len(warnings) >= 1
    assert warnings[0]["tipus"] == "ITV_VENCIMENT_IMMINENT"
    assert warnings[0]["dies_restants"] == 7


def test_control_documentacio_obligatoria_pesant():
    """Verifica que per a un camió pesant (>3500kg) s'exigeix la targeta de transport."""
    docs = [
        {
            "nom_fitxer": "permis.pdf",
            "tipus_document": "PERMIS_CIRCULACIO",
            "matricula": "9104-MBB",
            "mma_kg": 18000,
            "categoria_ue": "N3",
            "data_matriculacio": "2023-05-22",
            "data_proxima_itv": "2027-05-18",
            "data_caducitat_asseguranca": "2027-05-22",
        },
        {
            "nom_fitxer": "fitxa.pdf",
            "tipus_document": "FITXA_TECNICA",
            "matricula": "9104-MBB",
        },
        {
            "nom_fitxer": "asseguranca.pdf",
            "tipus_document": "ASSEGURANCA",
            "matricula": "9104-MBB",
        },
    ]

    res = consolidar_i_validar_ocr_flota(docs, tenant_cif="B55891234", data_referencia=date(2026, 11, 11))

    assert "TARGETA_TRANSPORT" in res["documents_mancants"]
    # Com que el camió té més d'1 any d'antiguitat (matriculat al 2023 vs 2026), també exigeix informe ITV
    assert "INFORME_ITV" in res["documents_mancants"]


if __name__ == "__main__":
    test_coherencia_creuada_coincident()
    test_coherencia_creuada_discrepancia_detectada()
    test_conciliacio_multitenant_renting()
    test_semafor_operatiu_bloquejat_per_caducitat()
    test_semafor_operatiu_alerta_imminent()
    test_control_documentacio_obligatoria_pesant()
    print("ALL FASE 3 TESTS PASSED SUCCESSFULLY!")
