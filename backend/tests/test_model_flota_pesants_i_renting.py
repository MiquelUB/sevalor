"""Test de verificacio per a la Fase 1: Models SQLAlchemy i DDL (a014_flota_pesants_i_renting_ext)."""
import importlib.util
import uuid
from datetime import date
from pathlib import Path

from app.models.models import DocumentFlota, Vehicle


def _carregar_migracio_a014():
    ruta = Path(__file__).parent.parent / "alembic" / "versions" / "a014_flota_pesants_i_renting_ext.py"
    spec = importlib.util.spec_from_file_location("mig_a014", ruta)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vehicle_model_new_columns():
    empresa_id = uuid.uuid4()
    v = Vehicle(
        empresa_id=empresa_id,
        matricula="1234-XYZ",
        marca="Mercedes-Benz",
        model="Actros",
        titular_nif="B12345678",
        arrendatari_nif="A87654321",
        codi_servei_dgt="B09",
        categoria_ue="N3",
        mma_kg=18000,
        tara_kg=8500,
        carrega_util_kg=9500,
        mmr_amb_fre_kg=14500,
        requereix_cap=True,
        equipament_homologat=["TACÒGRAF INTEL·LIGENT 4.0", "PLATAFORMA ELEVADORA"],
        certificats_prl_requerits=["PRL_OPERADOR_GRUA_AUTOCARGANT"],
        empresa_renting="Fraikin Alquiler de Vehículos",
        num_contracte_renting="FRAIK-2026-9921",
        data_venciment_renting=date(2028, 12, 31),
        dades_pesants={
            "data_calibratge_tacograf": "2027-05-10",
            "targeta_transport_num": "MDPE-12345678",
            "data_visat_transport": "2027-01-31",
        },
        regulacio_pesants={
            "data_calibratge_tacograf": "2027-05-10",
            "targeta_transport_num": "MDPE-12345678",
            "data_visat_transport": "2027-01-31",
        },
        estat_semafor="OPERATIU_OK",
    )

    assert v.matricula == "1234-XYZ"
    assert v.titular_nif == "B12345678"
    assert v.arrendatari_nif == "A87654321"
    assert v.codi_servei_dgt == "B09"
    assert v.categoria_ue == "N3"
    assert v.mma_kg == 18000
    assert v.tara_kg == 8500
    assert v.carrega_util_kg == 9500
    assert v.mmr_amb_fre_kg == 14500
    assert v.requereix_cap is True
    assert "PLATAFORMA ELEVADORA" in v.equipament_homologat
    assert "PRL_OPERADOR_GRUA_AUTOCARGANT" in v.certificats_prl_requerits
    assert v.empresa_renting == "Fraikin Alquiler de Vehículos"
    assert v.num_contracte_renting == "FRAIK-2026-9921"
    assert v.data_venciment_renting == date(2028, 12, 31)
    assert v.dades_pesants["targeta_transport_num"] == "MDPE-12345678"
    assert v.regulacio_pesants["targeta_transport_num"] == "MDPE-12345678"
    assert v.estat_semafor == "OPERATIU_OK"
    assert v.apte_assignacio_pwa is True


def test_document_flota_model_new_columns():
    empresa_id = uuid.uuid4()
    vehicle_id = uuid.uuid4()

    doc = DocumentFlota(
        empresa_id=empresa_id,
        vehicle_id=vehicle_id,
        tipus_document="FITXA_TECNICA",
        nom_arxiu="fitxa_tecnica_actros.pdf",
        ruta_arxiu="/data/empresa_1/vehicles/fitxa_tecnica_actros.pdf",
        bastidor_detectat="WDB9634031L123456",
        nif_detectat="B12345678",
        metadata_ocr={
            "motor": "OM471",
            "cilindrada_cm3": 12809,
            "potencia_kw": 330,
        },
    )

    assert doc.tipus_document == "FITXA_TECNICA"
    assert doc.bastidor_detectat == "WDB9634031L123456"
    assert doc.nif_detectat == "B12345678"
    assert doc.metadata_ocr["motor"] == "OM471"


def test_migration_a014_metadata():
    mig_a014 = _carregar_migracio_a014()
    assert mig_a014.revision == "a014_flota_pesants_i_renting_ext"
    assert mig_a014.down_revision == "a013_flota_regims_i_odometre"
    assert hasattr(mig_a014, "upgrade")
    assert hasattr(mig_a014, "downgrade")


if __name__ == "__main__":
    test_vehicle_model_new_columns()
    test_document_flota_model_new_columns()
    test_migration_a014_metadata()
    print("ALL FASE 1 TESTS PASSED SUCCESSFULLY!")
