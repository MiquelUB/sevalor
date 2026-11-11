"""Tests de verificacio per a la Fase 2: Codis UE Harmonitzats, Pesants, Renting i Normalitzacio Determinista."""
import os

import pytest

from app.services.ocr_service import processar_ocr_document_vehicle


@pytest.mark.asyncio
async def test_ocr_harmonitzat_permis_circulacio_camio():
    """Verifica l'extracció i normalització dels codis UE harmonitzats d'un camió pesant N3."""
    doc_permis = (
        "PERMISO DE CIRCULACIÓN - DIRECCIÓN GENERAL DE TRÁFICO\n"
        "A. Matrícula: 9104 MBB\n"
        "B. Fecha de primera matrícula: 22/05/2023\n"
        "C.1.1 Apellidos o razón social: CAMPOPRO SERVEIS AGRICOLES SL\n"
        "C.1.2 Nombre / NIF: B55891234\n"
        "C.4 c) Es el propietario del vehículo\n"
        "D.1 Marca: IVECO\n"
        "D.3 Denominación comercial: EUROCARGO ML180E28\n"
        "E. Nº Identificación (VIN): ZCFA81TN402739184\n"
        "F.2 Masa máxima en carga admisible (MMA): 18000 kg\n"
        "G. Masa en servicio (Tara): 8420 kg\n"
        "J. Categoría del vehículo: N3 (CAMIÓN PESADO)\n"
        "Servicio al que se destina: B09\n"
    ).encode("utf-8")

    res = await processar_ocr_document_vehicle(doc_permis)

    assert res["status"] == "EXTRET_AUTOMATIC"
    assert res["matricula"] == "9104-MBB"
    assert res["bastidor"] == "ZCFA81TN402739184"
    assert res["marca"] == "Iveco"
    assert res["model"] == "EUROCARGO ML180E28"
    assert res["titular"] == "CAMPOPRO SERVEIS AGRICOLES SL"
    assert res["titular_nif"] == "B55891234"
    assert res["data_matriculacio"] == "2023-05-22"
    assert res["categoria_ue"] == "N3"
    assert res["mma_kg"] == 18000
    assert res["tara_kg"] == 8420
    assert res["carrega_util_kg"] == 9580  # 18000 - 8420
    assert res["regim_adquisicio"] == "PROPIETAT"  # Codi B09
    assert res["carnet_necessari"] == "C"  # Pesant N3 > 3500kg sense enganxall
    assert res["requereix_cap"] is True


@pytest.mark.asyncio
async def test_ocr_harmonitzat_eitv_camio_amb_enganxall():
    """Verifica l'extracció d'eITV amb enganxall Ringfeder i MMR > 750kg -> C+E."""
    doc_eitv = (
        "TARJETA DE INSPECCIÓN TÉCNICA DE VEHÍCULOS (eITV)\n"
        "(A) Matrícula: 9104 MBB\n"
        "(D.1) Marca: IVECO\n"
        "(D.3) Denominación comercial: EUROCARGO ML180E28\n"
        "(E) Nº Identificación (VIN): ZCFA81TN402739184\n"
        "(J) Categoría del vehículo: N3\n"
        "(F.2) MMA: 18000 kg\n"
        "(G) Masa en orden de marcha: 8420 kg\n"
        "(O.1.2) MMR c/f: 14500 kg (Enganche Ringfeder)\n"
        "Carrozado y Reformas: Instala grúa PALFINGER y caja abierta basculante\n"
        "Tacógrafo Digital: VDO DTCO 4.1\n"
        "FECHA INSPECCIÓN: 18/05/2026\n"
        "RESULTADO: FAVORABLE\n"
        "VÁLIDA HASTA: 18/05/2027\n"
        "Km: 118450\n"
    ).encode("utf-8")

    res = await processar_ocr_document_vehicle(doc_eitv)

    assert res["matricula"] == "9104-MBB"
    assert res["categoria_ue"] == "N3"
    assert res["mma_kg"] == 18000
    assert res["carnet_necessari"] == "C+E"  # Pesant N3 amb MMR 14500kg i enganxall
    assert res["requereix_cap"] is True
    assert "GRUA" in res["equipament_homologat"]
    assert "ENGANXALL" in res["equipament_homologat"]
    assert "TACOGRAF" in res["equipament_homologat"]
    assert res["dades_pesants"]["tacograf_model"] == "VDO DTCO 4.1"


@pytest.mark.asyncio
async def test_ocr_renting_servei_a12_i_contracte():
    """Verifica la detecció de servei DGT A12, empresa de rènting i contracte."""
    doc_renting = (
        "CERTIFICADO DE ARRENDAMIENTO Y AUTORIZACIÓN DE USO\n"
        "ARVAL SERVICE LEASE, S.A. con NIF A81573479\n"
        "Matrícula: 7314 LJH\n"
        "Número de Bastidor (VIN): VF1FW5A0A64829103\n"
        "Régimen: Arrendamiento Operativo a Largo Plazo (Código DGT A12)\n"
        "Razón Social Arrendataria: CAMPOPRO SERVEIS AGRICOLES SL\n"
        "NIF / CIF: B55891234\n"
        "REFERENCIA CONTRATO MAESTRO: CMA-2020-009481\n"
        "ANEXO CONTRATO VEHÍCULO: CTR-ARV-2020-883921\n"
        "FECHA DE FINALIZACIÓN CONTRATO: 18/11/2026\n"
    ).encode("utf-8")

    res = await processar_ocr_document_vehicle(doc_renting)

    assert res["matricula"] == "7314-LJH"
    assert res["bastidor"] == "VF1FW5A0A64829103"
    assert res["regim_adquisicio"] == "RENTING"
    assert res["empresa_renting"] == "Arval Service Lease"
    assert res["num_contracte_renting"] == "CTR-ARV-2020-883921"
    assert res["data_venciment_renting"] == "2026-11-18"
    assert res["arrendatari_nif"] == "B55891234"
    assert res["tipus_document"] == "CONTRACTE_RENTING"


@pytest.mark.asyncio
async def test_ocr_targeta_transport_reat():
    """Verifica l'extracció de la targeta MPC i visat biennal de transport."""
    doc_trans = (
        "DIRECCIÓ GENERAL DE TRANSPORTS I MOBILITAT (REGISTRE REAT - MITMA)\n"
        "CERTIFICAT D'INSCRIPCIÓ D'AUTORITZACIÓ DE TRANSPORT (TARGETA MPC)\n"
        "CLAU I NÚMERO D'AUTORITZACIÓ: MPC - 12948573\n"
        "DATA PROPER VISAT OBLIGATORI: 30/04/2027\n"
        "Raó Social: CAMPOPRO SERVEIS AGRICOLES SL\n"
        "NIF / CIF: B55891234\n"
        "Matrícula: 9104 MBB\n"
        "Núm. de Bastidor (VIN): ZCFA81TN402739184\n"
    ).encode("utf-8")

    res = await processar_ocr_document_vehicle(doc_trans)

    assert res["matricula"] == "9104-MBB"
    assert res["tipus_document"] == "TARGETA_TRANSPORT"
    assert res["dades_pesants"]["targeta_transport_num"] == "MPC - 12948573"
    assert res["dades_pesants"]["data_visat_transport"] == "2027-04-30"


@pytest.mark.asyncio
async def test_ocr_camio_documents_reals():
    """Verifica el processament dels fitxers reals del camió pesant de demo_docs/camio."""
    folder = "demo_docs/Banc_Documents_Sevalor_Complet/demo_docs/02_flota_vehicles/camio"
    permis_path = os.path.join(folder, "PERMISO DE CIRCULACIÓN.md")
    eitv_path = os.path.join(folder, "TARJETA DE INSPECCIÓN TÉCNICA DE VEHÍCULOS (eITV).md")
    trans_path = os.path.join(folder, "REGISTRE REAT - MITMA.md")

    if os.path.exists(permis_path):
        res_p = await processar_ocr_document_vehicle(open(permis_path, "rb").read())
        assert res_p["matricula"] == "9104-MBB"
        assert res_p["bastidor"] == "ZCFA81TN402739184"
        assert res_p["categoria_ue"] == "N3"
        assert res_p["mma_kg"] == 18000
        assert res_p["requereix_cap"] is True

    if os.path.exists(eitv_path):
        res_e = await processar_ocr_document_vehicle(open(eitv_path, "rb").read())
        assert res_e["matricula"] == "9104-MBB"
        assert res_e["mma_kg"] == 18000
        assert res_e["carnet_necessari"] == "C+E"  # Porta remolc/enganxall Ringfeder
        assert res_e["requereix_cap"] is True

    if os.path.exists(trans_path):
        res_t = await processar_ocr_document_vehicle(open(trans_path, "rb").read())
        assert res_t["matricula"] == "9104-MBB"
        assert res_t["tipus_document"] == "TARGETA_TRANSPORT"
        assert res_t["dades_pesants"]["targeta_transport_num"] == "MPC - 12948573"


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ocr_harmonitzat_permis_circulacio_camio())
    asyncio.run(test_ocr_harmonitzat_eitv_camio_amb_enganxall())
    asyncio.run(test_ocr_renting_servei_a12_i_contracte())
    asyncio.run(test_ocr_targeta_transport_reat())
    asyncio.run(test_ocr_camio_documents_reals())
    print("ALL FASE 2 OCR TESTS PASSED SUCCESSFULLY!")
