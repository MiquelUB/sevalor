"""Tests de Fase 1: Verificació de l'arbre de 21 carpetes i Passarel·la cap al Disc del Client."""

import os
import uuid
from pathlib import Path

import pytest

from app.models.models import Empresa
from app.services.sovereign_storage import (
    MAPA_CARPETES_CLIENT,
    SovereignStorageGateway,
    inicialitzar_arbre_carpetes_disc,
)


@pytest.mark.asyncio
async def test_inicialitzacio_21_carpetes_disc_client(tmp_path: Path):
    """Comprova que es creen exactament totes les carpetes oficials (incloent Copilot i Protocols)."""
    disc_sevalormante = tmp_path / "Sevalormante_docs"
    creades = inicialitzar_arbre_carpetes_disc(disc_sevalormante)

    # 1. Verificar nombre de carpetes
    assert len(creades) == len(set(MAPA_CARPETES_CLIENT.values()))

    # 2. Verificar carpetes clau d'operacions
    assert (disc_sevalormante / "01_clients/fitxes").is_dir()
    assert (disc_sevalormante / "02_proveidors/fitxes").is_dir()
    assert (disc_sevalormante / "03_magatzem/articles_i_estoc").is_dir()
    assert (disc_sevalormante / "04_factures/emeses_verifactu_pdf").is_dir()
    assert (disc_sevalormante / "05_planols/arxius_base").is_dir()

    # 3. Verificar carpetes d'Autoaprenentatge del Copilot
    assert (disc_sevalormante / "09_copilot_ia/autoaprenentatge/memorandums_tecnics").is_dir()
    assert (disc_sevalormante / "09_copilot_ia/autoaprenentatge/historic_preus_i_mermes").is_dir()
    assert (disc_sevalormante / "09_copilot_ia/autoaprenentatge/converses_i_feedback").is_dir()
    assert (disc_sevalormante / "09_copilot_ia/prompt_sistema").is_dir()

    # 4. Verificar carpetes de Protocols i Manuals
    assert (disc_sevalormante / "10_protocols_i_manuals/procediments_interns").is_dir()
    assert (disc_sevalormante / "10_protocols_i_manuals/manuals_fabricants").is_dir()
    assert (disc_sevalormante / "10_protocols_i_manuals/normativa_i_prl").is_dir()


@pytest.mark.asyncio
async def test_escriptura_i_lectura_exclusiva_al_disc_del_client(db_session, tmp_path: Path):
    """Verifica que les entitats i fitxers d'una empresa van al seu disc_dur_url i NO a /docs ni /data."""
    disc_client = tmp_path / f"disc_sevalormante_{uuid.uuid4().hex[:6]}"
    emp_id = uuid.uuid4()
    nif_rnd = f"B{uuid.uuid4().int % 10000000:07d}A"
    sub_rnd = f"sevalormante-{emp_id.hex[:6]}"
    nova_emp = Empresa(
        id=emp_id,
        nom="Sevalormante SL",
        nif=nif_rnd,
        subdomini=sub_rnd,
        disc_dur_url=str(disc_client),
        node_ia_actiu=True,
    )
    db_session.add(nova_emp)
    await db_session.commit()

    # 1. Desar una fitxa de client al disc
    client_id = uuid.uuid4()
    ruta_json = await SovereignStorageGateway.desar_entitat_json(
        db=db_session,
        empresa_id=emp_id,
        categoria="clients",
        item_id=client_id,
        dades={"id": str(client_id), "rao_social": "Comunitat Diagonal 450", "nif": "H12345678"},
    )
    assert os.path.exists(ruta_json)
    assert str(disc_client) in ruta_json
    assert "/01_clients/fitxes/" in ruta_json

    # 2. Llegir entitats del disc
    entitats = await SovereignStorageGateway.llegir_entitats_json(
        db=db_session,
        empresa_id=emp_id,
        categoria="clients",
    )
    assert len(entitats) == 1
    assert entitats[0]["rao_social"] == "Comunitat Diagonal 450"

    # 3. Pujar un plànol binari al disc
    ruta_planol = await SovereignStorageGateway.pujar_fitxer_binari(
        db=db_session,
        empresa_id=emp_id,
        categoria="planols",
        nom_fitxer="esquema_caldera.pdf",
        content=b"%PDF-1.4 planol real sevalormante",
        content_type="application/pdf",
    )
    assert os.path.exists(ruta_planol)
    assert str(disc_client) in ruta_planol
    assert "/05_planols/arxius_base/esquema_caldera.pdf" in ruta_planol

    # 4. Verificar que NO s'ha creat res a /docs/<emp_id> ni /data/<emp_id> d'Hetzner
    assert not os.path.exists(f"/docs/{emp_id}")
    assert not os.path.exists(f"/data/{emp_id}")
