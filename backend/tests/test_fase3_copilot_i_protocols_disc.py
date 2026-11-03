"""Tests de Fase 3: Validació d'Autoaprenentatge del Copilot Dedicat i Protocols de l'Empresa al Disc del Client."""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.models.models import Client, Empresa, OrdreTreball


@pytest.mark.asyncio
async def test_memorandum_tecnic_autoaprenentatge_disc_client(
    async_client: AsyncClient, admin_session, headers: dict, tmp_path: Path
):
    """Comprova que els memoràndums tècnics es guarden i actualitzen a 09_copilot_ia/autoaprenentatge/memorandums_tecnics."""
    empresa_id = uuid.UUID(headers["X-Empresa-ID"])
    disc_empresa = tmp_path / f"disc_copilot_{empresa_id.hex[:6]}"

    emp = Empresa(
        id=empresa_id,
        nom="Aigua i Gas Solucions SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}P",
        subdomini=f"aigua-{empresa_id.hex[:4]}",
        disc_dur_url=str(disc_empresa),
        node_ia_actiu=True,
    )
    admin_session.add(emp)
    await admin_session.commit()

    cli = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi=f"CLI-{uuid.uuid4().hex[:6]}",
        rao_social="Client Aigua SL",
        nif="B11223344",
        adreca_fiscal="Avinguda Diagonal 10",
    )
    admin_session.add(cli)

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi=f"OT-COP-{uuid.uuid4().hex[:4]}",
        client_id=cli.id,
        titol="Fuga en canonada principal",
        adreca="Carrer de la Pau 12, Sabadell",
        descripcio="Reparació d'urgència",
        estat="ASSIGNA_PENDENT",
    )
    admin_session.add(ot)
    await admin_session.commit()

    # 1. Generar memoràndum tècnic
    payload_memo = {
        "ordre_treball_id": str(ot.id),
        "text_dictat_operari": "Hem trobat una canonada de plom antiga que s'ha trencat al cavar la rasa.",
        "confianca_acustica": 0.95,
    }
    resp = await async_client.post("/gestio/copilot/incidencies/peritatge", json=payload_memo)
    assert resp.status_code in (200, 201), resp.text
    memo_id = resp.json()["id"]

    # Comprovar que el memoràndum JSON s'ha guardat al disc dur del client
    carpeta_memos = disc_empresa / "09_copilot_ia" / "autoaprenentatge" / "memorandums_tecnics"
    fitxa_memo = carpeta_memos / f"{memo_id}.json"
    assert fitxa_memo.exists(), f"Memoràndum no trobat a {fitxa_memo}"
    contingut_json = fitxa_memo.read_text(encoding="utf-8")
    assert "PROPOSTA" in contingut_json

    # 2. Validació per part de l'Enginyer (HITL)
    payload_val = {
        "accio": "APROVAR",
        "observacions_enginyer": "Autoritzat com a imprevist facturable segons informe tècnic.",
    }
    resp_val = await async_client.put(
        f"/gestio/copilot/memorandums/{memo_id}/validacio", json=payload_val
    )
    assert resp_val.status_code == 200, resp_val.text

    # Comprovar que el fitxer al disc dur del client reflecteix l'aprovació
    contingut_actualitzat = fitxa_memo.read_text(encoding="utf-8")
    assert "APROVAT_ENGINYER" in contingut_actualitzat


@pytest.mark.asyncio
async def test_auditoria_post_obra_mermes_preus_disc_client(
    async_client: AsyncClient, admin_session, headers: dict, tmp_path: Path
):
    """Comprova que l'històric de mermes i preus post-obra es desen a 09_copilot_ia/autoaprenentatge/historic_preus_i_mermes."""
    empresa_id = uuid.UUID(headers["X-Empresa-ID"])
    disc_empresa = tmp_path / f"disc_auditoria_{empresa_id.hex[:6]}"

    emp = Empresa(
        id=empresa_id,
        nom="Electrotècnics Girona SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}E",
        subdomini=f"electro-{empresa_id.hex[:4]}",
        disc_dur_url=str(disc_empresa),
        node_ia_actiu=True,
    )
    admin_session.add(emp)
    await admin_session.commit()

    cli = Client(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi=f"CLI-{uuid.uuid4().hex[:6]}",
        rao_social="Client Electric SL",
        nif="B55667788",
        adreca_fiscal="Carrer Major 5",
    )
    admin_session.add(cli)

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        codi=f"OT-AUD-{uuid.uuid4().hex[:4]}",
        client_id=cli.id,
        titol="Instal·lació elèctrica nau",
        adreca="Polígon Industrial Nord, Girona",
        descripcio="Estesa de cables",
        estat="ASSIGNA_PENDENT",
    )
    admin_session.add(ot)
    await admin_session.commit()

    payload_auditoria = {
        "ordre_treball_id": str(ot.id),
        "materials_consumits": [
            {
                "article_id": str(uuid.uuid4()),
                "article": "Cable Cu 16mm²",
                "quantitat_real": 120.0,
                "unitat": "METRES",
            }
        ],
        "hores_reals": 8.5,
        "hores_previstes": 7.0,
        "km_reals": 25.0,
        "despeses_camp": 15.0,
    }
    resp = await async_client.post(
        "/gestio/copilot/reconciliacio/post-obra", json=payload_auditoria
    )
    assert resp.status_code == 200, resp.text
    auditoria_id = resp.json()["auditoria_id"]

    # Comprovar que l'auditoria post-obra és a 09_copilot_ia/autoaprenentatge/historic_preus_i_mermes
    carpeta_mermes = disc_empresa / "09_copilot_ia" / "autoaprenentatge" / "historic_preus_i_mermes"
    fitxa_aud = carpeta_mermes / f"{auditoria_id}.json"
    assert fitxa_aud.exists(), f"Fitxa d'auditoria no trobada a {fitxa_aud}"
    assert '"desviacio_hores": 1.5' in fitxa_aud.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_protocols_interns_i_system_prompt_disc_client(
    async_client: AsyncClient, admin_session, headers: dict, tmp_path: Path
):
    """Comprova que els protocols interns es guarden a 10_protocols_i_manuals i el system prompt a 09_copilot_ia/prompt_sistema."""
    empresa_id = uuid.UUID(headers["X-Empresa-ID"])
    disc_empresa = tmp_path / f"disc_protocols_{empresa_id.hex[:6]}"

    emp = Empresa(
        id=empresa_id,
        nom="Fontaners del Maresme SL",
        nif=f"B{uuid.uuid4().int % 10000000:07d}M",
        subdomini=f"maresme-{empresa_id.hex[:4]}",
        disc_dur_url=str(disc_empresa),
        node_ia_actiu=True,
    )
    admin_session.add(emp)
    await admin_session.commit()

    # 1. Afegir Protocol Intern RAG
    payload_rag = {
        "pregunta": "Com actuar davant d'una fuita d'aigua amb amiant?",
        "resposta": "Aturar el subministrament immediatament, no foradar i contactar amb empresa homologada RERA.",
        "paraules_clau": "amiant, canonada fibrociment, seguretat, prl",
    }
    resp_rag = await async_client.post("/gestio/copilot/rag/document", json=payload_rag)
    assert resp_rag.status_code == 201, resp_rag.text

    carpeta_protocols = disc_empresa / "10_protocols_i_manuals" / "procediments_interns"
    fitxers_protocols = list(carpeta_protocols.glob("*.json"))
    assert len(fitxers_protocols) >= 1
    assert any("amiant" in f.read_text(encoding="utf-8") for f in fitxers_protocols)

    # 2. Configurar System Prompt de l'Agent Copilot
    prompt_personalitzat = "Ets el Copilot de Fontaners del Maresme. Prioritza sempre el compliment del Codi Tècnic de l'Edificació (CTE-DB-HS)."
    payload_config = {
        "node_ia_actiu": True,
        "node_ia_url": "http://192.168.1.100:1234",
        "disc_dur_url": str(disc_empresa),
        "agent_prompt_system": prompt_personalitzat,
    }
    resp_conf = await async_client.put("/gestio/configuracio/node-ia", json=payload_config)
    assert resp_conf.status_code == 200, resp_conf.text

    fitxer_prompt = disc_empresa / "09_copilot_ia" / "prompt_sistema" / "system_prompt.txt"
    assert fitxer_prompt.exists(), f"Fitxer de prompt no trobat a {fitxer_prompt}"
    assert prompt_personalitzat in fitxer_prompt.read_text(encoding="utf-8")
