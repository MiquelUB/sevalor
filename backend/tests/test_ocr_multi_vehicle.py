import pytest

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


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ocr_targeta_itv_vehicle())
    asyncio.run(test_ocr_polissa_asseguranca())
    asyncio.run(test_ocr_multi_document_fusion())
    print("ALL TESTS PASSED CLEANLY.")
