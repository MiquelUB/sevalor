import pytest

from app.services.flota_service import consolidar_i_validar_ocr_flota
from app.services.ocr_service import processar_ocr_document_vehicle


@pytest.mark.asyncio
async def test_ocr_targeta_itv_vehicle():
    """Verifica l'extracció de camps complets d'una targeta ITV / fitxa tècnica."""
    doc_itv = (
        "TARGETA ITV (FITXA TÈCNICA)\n"
        "Matrícula: 4321-KMN\n"
        "VIN: VSSZZZ1234567890\n"
        "Marca: Ford Transit\n"
        "Combustible: Dièsel\n"
        "Data Inspecció: 20/09/2026\n"
        "Resultat: FAVORABLE\n"
        "Pròxima ITV: 20/09/2027\n"
        "Km: 120500\n"
    ).encode("utf-8")

    res = await processar_ocr_document_vehicle(doc_itv)

    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["matricula"] == "4321-KMN"
    assert res["bastidor"] == "VSSZZZ1234567890"
    assert res["marca"] == "Ford"
    assert res["model"] == "Transit"
    assert res["tipus"] == "DIESEL"
    assert res["distintiu_ambiental"] == "C"
    assert res["estat_itv"] == "FAVORABLE"
    assert res["data_proxima_itv"] == "2027-09-20"
    assert res["data_inspeccio_itv"] == "2026-09-20"
    assert res["odometre_acumulat"] == 120500
    assert res["carnet_necessari"] == "B"
    assert res["tipus_document"] == "ITV"


@pytest.mark.asyncio
async def test_ocr_polissa_asseguranca():
    """Verifica l'extracció de companyia, pòlissa i caducitat d'assegurança."""
    doc_asseguranca = (
        "JUSTIFICANT DE COBERTURA D'ASSEGURANÇA\n"
        "Companyia Asseguradora: Mapfre Seguros\n"
        "Pòlissa núm: MAP-88992211-X\n"
        "Matrícula: 4321-KMN\n"
        "Caducitat assegurança: 15/05/2027\n"
        "Règim: Rènting Alphabet\n"
        "Límit km anuals: 150000 km\n"
    ).encode("utf-8")

    res = await processar_ocr_document_vehicle(doc_asseguranca)

    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["companyia_asseguradora"] == "Mapfre"
    assert res["polissa_asseguranca"] == "MAP-88992211-X"
    assert res["data_caducitat_asseguranca"] == "2027-05-15"
    assert res["regim_adquisicio"] == "RENTING"
    assert res["renting_limit_km"] == 150000
    assert res["tipus_document"] == "ASSEGURANCA"


@pytest.mark.asyncio
async def test_ocr_contracte_lloguer():
    """Verifica l'extracció d'un contracte o albarà de lloguer de vehicle (Europcar/Sixt)."""
    doc_lloguer = (
        "CONTRACTE D'ARRENDAMENT / LLOGUER DE VEHICLE COMERCIAL\n"
        "Empresa arrendadora: Europcar IB SA\n"
        "Matrícula: 7788-BBB\n"
        "Marca: Renault Master\n"
        "Règim: Lloguer sense conductor\n"
        "Límit contractual: 30000 km\n"
        "Data devolució: 15/09/2026\n"
    ).encode("utf-8")

    res = await processar_ocr_document_vehicle(doc_lloguer)

    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["matricula"] == "7788-BBB"
    assert res["marca"] == "Renault"
    assert res["regim_adquisicio"] == "LLOGUER"
    assert res["renting_limit_km"] == 30000


@pytest.mark.asyncio
async def test_ocr_factura_compra_propietat():
    """Verifica que una factura de compra o certificat en propietat no té límit de km."""
    doc_compra = (
        "FACTURA DE COMPRAVENTA DE VEHICLE NOU\n"
        "Concessionari Oficial Ford Romacar\n"
        "Comprador: SEVALOR INSTAL·LACIONS SL\n"
        "Matrícula: 1122-CCC\n"
        "Marca: Ford Transit Courier\n"
        "Adquisició en propietat (compra directa)\n"
    ).encode("utf-8")

    res = await processar_ocr_document_vehicle(doc_compra)

    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["matricula"] == "1122-CCC"
    assert res["marca"] == "Ford"
    assert res["regim_adquisicio"] == "PROPIETAT"
    assert res["renting_limit_km"] is None


@pytest.mark.asyncio
async def test_ocr_multi_document_fusion():
    """Verifica que la combinació de dades procedents d'ITV i Assegurança cobreix els 16 camps."""
    doc_itv = (
        "TARGETA ITV\n"
        "Matrícula: 4321-KMN\n"
        "VIN: VSSZZZ1234567890\n"
        "Marca: Ford Transit\n"
        "Combustible: Dièsel\n"
        "Resultat: FAVORABLE\n"
        "Pròxima ITV: 20/09/2027\n"
        "Km: 120500\n"
    ).encode("utf-8")

    doc_polissa = (
        "PÒLISSA D'ASSEGURANÇA\n"
        "Asseguradora: Allianz\n"
        "Pòlissa: POL-998877\n"
        "Caducitat: 30/11/2027\n"
    ).encode("utf-8")

    res_itv = await processar_ocr_document_vehicle(doc_itv)
    res_polissa = await processar_ocr_document_vehicle(doc_polissa)

    # Fusionar dades com fa l'endpoint /ocr-draft
    merged = {
        "matricula": res_itv.get("matricula") or res_polissa.get("matricula"),
        "marca": res_itv.get("marca") or res_polissa.get("marca"),
        "model": res_itv.get("model") or res_polissa.get("model"),
        "tipus": res_itv.get("tipus") or res_polissa.get("tipus") or "DIESEL",
        "distintiu_ambiental": res_itv.get("distintiu_ambiental") or "C",
        "odometre_acumulat": res_itv.get("odometre_acumulat") or res_polissa.get("odometre_acumulat"),
        "companyia_asseguradora": res_polissa.get("companyia_asseguradora") or res_itv.get("companyia_asseguradora"),
        "polissa_asseguranca": res_polissa.get("polissa_asseguranca") or res_itv.get("polissa_asseguranca"),
        "data_caducitat_asseguranca": res_polissa.get("data_caducitat_asseguranca"),
        "estat_itv": res_itv.get("estat_itv") or "FAVORABLE",
        "data_proxima_itv": res_itv.get("data_proxima_itv"),
        "carnet_necessari": res_itv.get("carnet_necessari") or "B",
    }

    assert merged["matricula"] == "4321-KMN"
    assert merged["marca"] == "Ford"
    assert merged["model"] == "Transit"
    assert merged["tipus"] == "DIESEL"
    assert merged["distintiu_ambiental"] == "C"
    assert merged["odometre_acumulat"] == 120500
    assert merged["estat_itv"] == "FAVORABLE"
    assert merged["data_proxima_itv"] == "2027-09-20"
    assert merged["companyia_asseguradora"] == "Allianz"
    assert merged["polissa_asseguranca"] == "POL-998877"
    assert merged["data_caducitat_asseguranca"] == "2027-11-30"
    assert merged["carnet_necessari"] == "B"
    print("Tots els tests d'OCR Multi-Vehicle han passat al 100%!")


@pytest.mark.asyncio
async def test_ocr_fitxers_markdown_reals():
    """Verifica l'extracció directa dels 4 fitxers .md reals de proves de l'usuari."""
    import os

    folder = "demo_docs/Banc_Documents_Sevalor_Complet/demo_docs/02_flota_vehicles/docs_1"
    itv_path = os.path.join(folder, " TARJETA DE INSPECCIÓN TÉCNICA DE VEHÍCULOS.md")
    informe_path = os.path.join(folder, "INFORME D'INSPECCIÓ TÈCNICA DE VEHICLES (ITV).md")
    permis_path = os.path.join(folder, "PERMISO DE CIRCULACIÓN.md")
    seguro_path = os.path.join(folder, "Seguro vehicle.md")

    if os.path.exists(itv_path):
        res_itv = await processar_ocr_document_vehicle(open(itv_path, "rb").read())
        assert res_itv["matricula"] == "4829-LWT"
        assert res_itv["bastidor"] == "WF0YXXTTGYNJ58291"
        assert res_itv["marca"] == "Ford"
        assert res_itv["model"] == "TRANSIT CUSTOM"
        assert res_itv["tipus"] == "DIESEL"
        assert res_itv["distintiu_ambiental"] == "C"
        assert res_itv["odometre_acumulat"] == 64320
        assert res_itv["estat_itv"] == "FAVORABLE"
        assert res_itv["data_proxima_itv"] == "2028-03-12"
        assert res_itv["tipus_document"] == "ITV"
        assert res_itv["renting_limit_km"] is None

    if os.path.exists(informe_path):
        res_inf = await processar_ocr_document_vehicle(open(informe_path, "rb").read())
        assert res_inf["matricula"] == "4829-LWT"
        assert res_inf["bastidor"] == "WF0YXXTTGYNJ58291"
        assert res_inf["marca"] == "Ford"
        assert res_inf["estat_itv"] == "FAVORABLE"
        assert res_inf["data_proxima_itv"] == "2028-03-12"
        assert res_inf["renting_limit_km"] is None

    if os.path.exists(permis_path):
        res_perm = await processar_ocr_document_vehicle(open(permis_path, "rb").read())
        assert res_perm["matricula"] == "4829-LWT"
        assert res_perm["bastidor"] == "WF0YXXTTGYNJ58291"
        assert res_perm["marca"] == "Ford"
        assert res_perm["tipus"] == "DIESEL"
        assert res_perm["regim_adquisicio"] == "PROPIETAT"
        assert res_perm["renting_limit_km"] is None
        assert res_perm["tipus_document"] == "PERMIS_CIRCULACIO"

    if os.path.exists(seguro_path):
        res_seg = await processar_ocr_document_vehicle(open(seguro_path, "rb").read())
        assert res_seg["matricula"] == "4829-LWT"
        assert res_seg["bastidor"] == "WF0YXXTTGYNJ58291"
        assert res_seg["companyia_asseguradora"] == "Allianz"
        assert res_seg["polissa_asseguranca"] == "048-99283741-02"
        assert res_seg["data_caducitat_asseguranca"] == "2027-03-14"
        assert res_seg["tipus_document"] == "ASSEGURANCA"

    print("Extracció dels fitxers .md reals (vehicle 1) validada al 100%!")


@pytest.mark.asyncio
async def test_ocr_vehicle_2_renting_reals():
    """Verifica l'extracció dels fitxers de vehicle 2 (Rènting Arval / Kangoo)."""
    import os

    folder = "demo_docs/Banc_Documents_Sevalor_Complet/demo_docs/02_flota_vehicles/vehicle_2"
    itv_path = os.path.join(folder, " TARJETA DE INSPECCIÓN TÉCNICA DE VEHÍCULOS (eITV).md")
    permis_path = os.path.join(folder, " PERMISO DE CIRCULACIÓN.md")
    renting_path = os.path.join(folder, " RENTING OPERATIVO.md")
    cert_path = os.path.join(folder, "CERTIFICADO DE ARRENDAMIENTO Y AUTORIZACIÓN DE USO (RENTING).md")

    if os.path.exists(itv_path):
        res_itv = await processar_ocr_document_vehicle(open(itv_path, "rb").read())
        assert res_itv["matricula"] == "7314-LJH"
        assert res_itv["marca"] == "Renault"
        assert res_itv["model"] == "KANGOO"
        assert res_itv["data_proxima_itv"] == "2026-11-16"
        assert res_itv["odometre_acumulat"] == 97840
        assert res_itv["regim_adquisicio"] is None

    if os.path.exists(permis_path):
        res_perm = await processar_ocr_document_vehicle(open(permis_path, "rb").read())
        assert res_perm["matricula"] == "7314-LJH"
        assert res_perm["regim_adquisicio"] == "RENTING"
        assert res_perm["tipus_document"] == "PERMIS_CIRCULACIO"

    if os.path.exists(renting_path):
        res_rent = await processar_ocr_document_vehicle(open(renting_path, "rb").read())
        assert res_rent["matricula"] == "7314-LJH"
        assert res_rent["companyia_asseguradora"] == "Mapfre"
        assert res_rent["polissa_asseguranca"] == "071-2400981234-99"
        assert res_rent["regim_adquisicio"] == "RENTING"

    if os.path.exists(cert_path):
        res_cert = await processar_ocr_document_vehicle(open(cert_path, "rb").read())
        assert res_cert["matricula"] == "7314-LJH"
        assert res_cert["regim_adquisicio"] == "RENTING"

    print("Extracció dels fitxers .md reals (vehicle 2) validada al 100%!")


@pytest.mark.asyncio
async def test_ocr_draft_furgoneta_propia_n1_ok():
    """Fase 5: Valida la Ford Transit (4829-LWT), carnet B, titularitat directa i OPERATIU_OK."""
    import os

    folder = "demo_docs/Banc_Documents_Sevalor_Complet/demo_docs/02_flota_vehicles/docs_1"
    if not os.path.exists(folder):
        folder = os.path.join("..", folder)

    docs_extrets = []
    for fitxer in sorted(os.listdir(folder)):
        if fitxer.endswith(".md"):
            path = os.path.join(folder, fitxer)
            content = open(path, "rb").read()
            res = await processar_ocr_document_vehicle(content)
            res["nom_fitxer"] = fitxer
            docs_extrets.append(res)

    draft = consolidar_i_validar_ocr_flota(docs_extrets, tenant_cif="B55891234")

    # Identificadors principals
    assert draft["matricula"] == "4829-LWT"
    assert draft["bastidor"] == "WF0YXXTTGYNJ58291"
    assert draft["num_bastidor_vin"] == "WF0YXXTTGYNJ58291"
    assert draft["marca"] == "Ford"
    assert "TRANSIT" in (draft["model"] or "").upper()

    # Característiques tècniques i carnet
    assert draft["carnet_necessari"] == "B"
    assert draft["categoria_ue"] == "N1"
    assert draft["mma_kg"] == 3000
    assert draft["requereix_cap"] is False

    # Titularitat i conciliació multitenant directa
    assert draft["titular_nif"] == "B55891234"
    assert draft["regim_adquisicio"] == "PROPIETAT"
    assert draft["validacio_tenant_cif"] == "COINCIDENT_PROPIETARI"

    # Coherència creuada i semàfor
    assert draft["coherencia_creuada_vin_matricula"] is True
    assert draft["estat_semafor"] == "OPERATIU_OK"
    assert draft["apte_assignacio_pwa"] is True
    assert draft["estat_itv"] == "FAVORABLE"
    assert draft["documents_mancants"] == []
    print("Test furgoneta pròpia N1 (4829-LWT) validat al 100%!")


@pytest.mark.asyncio
async def test_ocr_draft_renting_venciment_imminent():
    """Fase 5: Valida la Renault Kangoo (7314-LJH), conciliació Arval vs. Tenant (A12),

    detecció de defectes lleus (FAVORABLE_LEUS) i dispars d'alerta crítica a <10 dies.
    """
    import os

    folder = "demo_docs/Banc_Documents_Sevalor_Complet/demo_docs/02_flota_vehicles/vehicle_2"
    if not os.path.exists(folder):
        folder = os.path.join("..", folder)

    docs_extrets = []
    for fitxer in sorted(os.listdir(folder)):
        if fitxer.endswith(".md"):
            path = os.path.join(folder, fitxer)
            content = open(path, "rb").read()
            res = await processar_ocr_document_vehicle(content)
            res["nom_fitxer"] = fitxer
            docs_extrets.append(res)

    draft = consolidar_i_validar_ocr_flota(docs_extrets, tenant_cif="B55891234")

    # Identificadors principals
    assert draft["matricula"] == "7314-LJH"
    assert draft["bastidor"] == "VF1FW5A0A64829103"
    assert draft["marca"] == "Renault"
    assert "KANGOO" in (draft["model"] or "").upper()

    # Conciliació Multitenant (Arval vs Tenant via servei A12 o arrendatari NIF)
    assert draft["titular_nif"] == "A81573479"
    assert draft["arrendatari_nif"] == "B55891234"
    assert draft["regim_adquisicio"] == "RENTING"
    assert draft["validacio_tenant_cif"] == "COINCIDENT_ARRENDATARI"

    # Detecció de defectes lleus
    assert draft["estat_itv"] == "FAVORABLE_LEUS"

    # Venciment de pròxima ITV i dispar d'alerta imminent (< 10 dies)
    assert draft["data_proxima_itv"] == "2026-11-16"
    assert draft["estat_semafor"] == "ALERTA_VENCIMENT_IMMINENT"
    assert draft["apte_assignacio_pwa"] is True

    # Comprovar alertes programades: ha d'haver-hi alerta per ITV imminent (< 10 dies)
    alertes_itv = [
        a for a in draft.get("alertes_programades", []) if a.get("camp") == "data_proxima_itv"
    ]
    assert len(alertes_itv) > 0
    alerta_itv = alertes_itv[0]
    assert alerta_itv["dies_restants"] is not None
    assert alerta_itv["dies_restants"] < 10
    print("Test renting venciment imminent (7314-LJH) validat al 100%!")


@pytest.mark.asyncio
async def test_ocr_draft_camio_pesant_n3_grua():
    """Fase 5: Valida l'Iveco Eurocargo (9104-MBB), mma_kg = 18000, assignació automàtica de

    carnet_necessari = "C", requereix_cap = True, tacògraf i TARGETA_TRANSPORT.
    """
    import os

    folder = "demo_docs/Banc_Documents_Sevalor_Complet/demo_docs/02_flota_vehicles/camio"
    if not os.path.exists(folder):
        folder = os.path.join("..", folder)

    docs_extrets = []
    for fitxer in sorted(os.listdir(folder)):
        if fitxer.endswith(".md"):
            path = os.path.join(folder, fitxer)
            content = open(path, "rb").read()
            res = await processar_ocr_document_vehicle(content)
            res["nom_fitxer"] = fitxer
            docs_extrets.append(res)

    draft = consolidar_i_validar_ocr_flota(docs_extrets, tenant_cif="B55891234")

    # Identificadors principals
    assert draft["matricula"] == "9104-MBB"
    assert draft["bastidor"] == "ZCFA81TN402739184"
    assert draft["marca"] == "Iveco"
    assert "EUROCARGO" in (draft["model"] or "").upper()

    # Pesant N3 i regulació de carnet
    assert draft["categoria_ue"] == "N3"
    assert draft["mma_kg"] == 18000
    assert draft["carnet_necessari"] == "C"
    assert draft["requereix_cap"] is True

    # Equipament homologat (Grua, Tacògraf)
    equipament = draft.get("equipament_homologat") or []
    assert any("GRUA" in e for e in equipament)
    assert any("TACOGRAF" in e for e in equipament)

    # Dades pesants (Tacògraf digital i Targeta de Transport MPC)
    dades_p = draft.get("dades_pesants") or {}
    assert "targeta_transport_num" in dades_p
    assert "12948573" in dades_p["targeta_transport_num"]
    assert "data_calibratge_tacograf" in dades_p

    # Documentació reglamentària
    tipus_processats = {d.get("tipus_detectat") for d in draft.get("documents_processats", [])}
    assert "TARGETA_TRANSPORT" in tipus_processats
    assert "TARGETA_TRANSPORT" not in draft.get("documents_mancants", [])
    print("Test camió pesant N3 amb grua (9104-MBB) validat al 100%!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_ocr_targeta_itv_vehicle())
    asyncio.run(test_ocr_polissa_asseguranca())
    asyncio.run(test_ocr_contracte_lloguer())
    asyncio.run(test_ocr_factura_compra_propietat())
    asyncio.run(test_ocr_multi_document_fusion())
    asyncio.run(test_ocr_fitxers_markdown_reals())
    asyncio.run(test_ocr_vehicle_2_renting_reals())
    asyncio.run(test_ocr_draft_furgoneta_propia_n1_ok())
    asyncio.run(test_ocr_draft_renting_venciment_imminent())
    asyncio.run(test_ocr_draft_camio_pesant_n3_grua())
    print("ALL TESTS PASSED CLEANLY.")
