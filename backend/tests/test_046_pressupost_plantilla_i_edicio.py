"""Tests complets del mòdul de Pressupostos: plantilla HTML + PDF WeasyPrint, recursos, autocompletat client i edició prèvia."""

import base64
import uuid
from datetime import datetime, timezone

import pymupdf  # type: ignore[import-untyped]
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.models import Client, EinaCustodia, Empresa, OrdreTreball, Pressupost, Vehicle
from app.services.pressupost_service import (
    calcular_totals_pressupost_complet,
    generar_pdf_pressupost_bytes,
    renderitzar_html_pressupost,
)
from app.services.sovereign_storage import inicialitzar_arbre_carpetes_disc

VALID_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_plantilla_html_pressupost_chameleon_seccions_xss_i_pdf_weasyprint() -> None:
    """Verifica renderització HTML oficial, Chameleon HSL, seccions, descompte global, zero Veri*factu, XSS i PDF WeasyPrint."""
    emp = Empresa(
        id=uuid.uuid4(),
        nom="CampoPro Instal·lacions SL",
        rao_social_fiscal="CampoPro Instal·lacions S.L.",
        eslogan_activitat="Enginyeria agrícola i sistemes de reg",
        nif="B12345678",
        adreca="Carrer del Reg, 12",
        codi_postal="25001",
        poblacio="Lleida",
        provincia="Lleida",
        telefon_facturacio="973 000 111",
        email_facturacio="comercial@campopro.cat",
        dades_registre_mercantil="RM Lleida Tom 123 Foli 45 Full L-9999",
        primari_hsl="166 22% 24%",
    )
    cli = Client(
        id=uuid.uuid4(),
        empresa_id=emp.id,
        codi="CLI-001",
        rao_social="Agrícola Ponent SA",
        nif="A87654321",
        adreca_fiscal="Camí de l'Horta, 4",
        codi_postal="25100",
        poblacio="Almacelles",
        provincia="Lleida",
        persona_contacte="Joan Puig",
        email="joan@agricolaponent.cat",
        telefon="600112233",
    )
    linies_in = [
        {
            "seccio": "Mà d'obra i instal·lació",
            "concepte": "Muntatge electrovàlvules <script>alert(1)</script>",
            "detall": "Inclou proves de pressió i programació",
            "quantitat": 4,
            "preu_unitari": 50.0,
            "descompte_pct": 0.0,
            "tipus_iva": 21.0,
        },
        {
            "seccio": "Desplaçament i vehicle",
            "concepte": "Desplaçament (1234-BCD · Ford Transit)",
            "detall": "40 km a 0,50 €/km",
            "quantitat": 40,
            "preu_unitari": 0.5,
            "descompte_pct": 0.0,
            "tipus_iva": 21.0,
        },
        {
            "seccio": "Eines i maquinària",
            "concepte": "Ús de màquina de termofusió",
            "detall": "Equip homologat S/N TF-900",
            "quantitat": 1,
            "preu_unitari": 80.0,
            "descompte_pct": 0.0,
            "tipus_iva": 21.0,
        },
    ]
    calc = calcular_totals_pressupost_complet(linies_in, descompte_global_pct=10.0)
    assert calc["subtotal_brut"] == 300.0
    assert calc["descompte_global_import"] == 30.0
    assert calc["base_imposable"] == 270.0
    assert calc["quota_iva"] == 56.7
    assert calc["total"] == 326.7

    pres = Pressupost(
        id=uuid.uuid4(),
        empresa_id=emp.id,
        client_id=cli.id,
        numero="P-2026/001",
        total=calc["total"],
        estat="PENDENT",
        created_at=datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc),
    )
    detalls = {
        "titol": "Automatització sector reg Nord",
        "descripcio": "Subministrament i muntatge d'electrovàlvules, desplaçament i proves finals.",
        "adreca_obra": "Finca Nord, Almacelles",
        "data_pressupost": "2026-11-24",
        "validesa_dies": 30,
        "referencia_client": "REF-PONENT-2026",
        "elaborat_per": "Maria Soler",
        "vehicle_nom": "1234-BCD · Ford Transit",
        "desplacament_km": 40,
        "desplacament_preu_km": 0.5,
        "eines_resum": [{"id": "e1", "nom": "Termofusora", "model": "TF-900"}],
        "linies": calc["linies"],
        "subtotal_brut": calc["subtotal_brut"],
        "descompte_global_pct": 10.0,
        "descompte_global_import": calc["descompte_global_import"],
        "base_imposable": calc["base_imposable"],
        "quota_iva": calc["quota_iva"],
        "forma_pagament": "Transferència bancària 30 dies",
        "percentatge_acompte": 30.0,
        "termini_execucio": "5 dies laborables",
        "notes_exclusions": "No inclou obra civil ni rases.",
    }

    html_out = renderitzar_html_pressupost(
        empresa=emp,
        client=cli,
        pressupost=pres,
        detalls=detalls,
        logotip_bytes=VALID_PNG_BYTES,
    )

    assert "--accent: hsl(166, 22%, 24%);" in html_out
    assert "data:image/png;base64," in html_out
    assert "VERI*FACTU" not in html_out
    assert "QR tributario" not in html_out
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_out
    assert "P-2026/001" in html_out
    assert "Mà d&#39;obra i instal·lació" in html_out or "Mà d'obra i instal·lació" in html_out
    assert "Descompte (10 %)" in html_out
    assert "Bo per a acceptació" in html_out
    assert "1234-BCD · Ford Transit" in html_out
    assert "Termofusora (TF-900)" in html_out
    assert "98,01 €" in html_out  # 30% acompte de 326,70 €

    pdf_bytes = generar_pdf_pressupost_bytes(
        empresa=emp,
        client=cli,
        pressupost=pres,
        detalls=detalls,
        logotip_bytes=VALID_PNG_BYTES,
    )
    assert pdf_bytes.startswith(b"%PDF")
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    full_text = "\n".join(page.get_text() for page in doc)
    doc.close()

    assert "Pressupost" in full_text
    assert "P-2026/001" in full_text
    assert "Agrícola Ponent SA" in full_text
    assert "Automatització sector reg Nord" in full_text
    assert "326,70" in full_text
    assert "No inclou obra civil ni rases." in full_text


@pytest.mark.asyncio
async def test_flux_complet_pressupost_autocompletat_edicio_html_pdf_i_ot(
    admin_session, headers, boss_token, tmp_path
) -> None:
    """Verifica alta client amb CP/població, següent número correlatiu, creació amb vehicle/eines, edició prèvia, HTML/PDF i traspàs a OT."""
    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    vault_token = f"svlt_p46_{uuid.uuid4().hex[:12]}"

    disc_root = tmp_path / "disc_pres_46"
    inicialitzar_arbre_carpetes_disc(disc_root)

    emp = Empresa(
        id=emp_uuid,
        nom="Sevalor Audit Pressupostos SL",
        nif="B" + str(uuid.uuid4())[:8].upper(),
        subdomini="pres46-" + str(uuid.uuid4())[:5],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
        disc_dur_url=f"wss-tunnel://{emp_uuid}",
        node_ia_url=f"wss-tunnel://{emp_uuid}",
        vault_token=vault_token,
        primari_hsl="205 60% 28%",
    )
    admin_session.add(emp)
    await admin_session.flush()

    client_id = uuid.uuid4()
    vehicle_id = uuid.uuid4()
    eina_id = uuid.uuid4()

    admin_session.add_all(
        [
            Client(
                id=client_id,
                empresa_id=emp_uuid,
                codi="CLI-46",
                rao_social="Cooperativa del Segre SCCL",
                nif="F25000111",
                telefon="973222333",
                email="gestio@coopsegre.cat",
                adreca_fiscal="Av. del Segre, 88",
                codi_postal="25007",
                poblacio="Lleida",
                provincia="Lleida",
                persona_contacte="Pere Martí",
            ),
            Vehicle(
                id=vehicle_id,
                empresa_id=emp_uuid,
                matricula="5678-KLM",
                marca="Renault",
                model="Master",
            ),
            EinaCustodia(
                id=eina_id,
                empresa_id=emp_uuid,
                nom="Trepant Percutor Hilti",
                model="TE-70",
                numero_serie="SN-HLT-001",
            ),
        ]
    )
    await admin_session.commit()

    from tests.wss_test_helpers import live_empresa_wss_context

    async with live_empresa_wss_context(emp_uuid, vault_token, disc_root):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. GET /clients retorna CP, població, província i persona de contacte per autocompletar
            res_clis = await client.get("/api/v1/gestio/clients", headers=headers)
            assert res_clis.status_code == 200, res_clis.text
            cli_data = next(c for c in res_clis.json() if c["id"] == str(client_id))
            assert cli_data["codi_postal"] == "25007"
            assert cli_data["poblacio"] == "Lleida"
            assert cli_data["provincia"] == "Lleida"
            assert cli_data["persona_contacte"] == "Pere Martí"

            # 2. Següent número correlatiu
            res_num = await client.get("/api/v1/gestio/pressupostos/seguent-numero", headers=headers)
            assert res_num.status_code == 200, res_num.text
            num_proposat = res_num.json()["numero"]
            assert num_proposat.endswith("/001")

            # 3. Crear pressupost amb vehicle, eines, desplaçament, descripció, seccions i condicions
            payload_create = {
                "client_id": str(client_id),
                "numero": num_proposat,
                "titol": "Manteniment estació de bombament",
                "descripcio": "Revisió de quadre elèctric, substitució de bomba i proves de cabal.",
                "adreca_obra": "Estació Bombament Nord, Lleida",
                "validesa_dies": 30,
                "referencia_client": "OBRA-SEGRE-01",
                "elaborat_per": "Tècnic Sevalor",
                "vehicle_id": str(vehicle_id),
                "eines_ids": [str(eina_id)],
                "desplacament_km": 30,
                "desplacament_preu_km": 0.5,
                "descompte_global_pct": 5.0,
                "forma_pagament": "Transferència 30 dies",
                "percentatge_acompte": 25.0,
                "termini_execucio": "3 dies laborables",
                "notes_exclusions": "Exclou permisos elèctrics.",
                "linies": [
                    {
                        "seccio": "Mà d'obra",
                        "tipus_linia": "MA_OBRA",
                        "concepte": "Intervenció tècnica",
                        "detall": "2 operaris jornada completa",
                        "quantitat": 8,
                        "preu_unitari": 50.0,
                        "descompte_pct": 0.0,
                        "tipus_iva": 21.0,
                    },
                    {
                        "seccio": "Desplaçament i vehicle",
                        "tipus_linia": "DESPLACAMENT",
                        "vehicle_id": str(vehicle_id),
                        "concepte": "Desplaçament 5678-KLM",
                        "quantitat": 30,
                        "preu_unitari": 0.5,
                        "descompte_pct": 0.0,
                        "tipus_iva": 21.0,
                    },
                ],
            }
            res_create = await client.post("/api/v1/gestio/pressupostos", json=payload_create, headers=headers)
            assert res_create.status_code == 201, res_create.text
            created = res_create.json()
            pres_id = created["id"]
            assert created["client_codi_postal"] == "25007"
            assert created["client_persona_contacte"] == "Pere Martí"
            assert created["vehicle_id"] == str(vehicle_id)
            assert "5678-KLM" in (created["vehicle_nom"] or "")
            assert len(created["eines_resum"]) == 1
            assert created["eines_resum"][0]["nom"] == "Trepant Percutor Hilti"
            assert created["subtotal_brut"] == 415.0
            assert created["descompte_global_import"] == 20.75
            assert created["base_imposable"] == 394.25

            # 4. Previsualització HTML + PDF oficial abans d'enviar
            res_html = await client.get(f"/api/v1/gestio/pressupostos/{pres_id}/html", headers=headers)
            assert res_html.status_code == 200
            assert "Cooperativa del Segre SCCL" in res_html.text
            assert "5678-KLM" in res_html.text
            assert "Trepant Percutor Hilti" in res_html.text

            res_pdf = await client.get(f"/api/v1/gestio/pressupostos/{pres_id}/pdf", headers=headers)
            assert res_pdf.status_code == 200
            assert res_pdf.content.startswith(b"%PDF")

            # 5. Editar el pressupost un cop generat abans d'enviar-lo (incloent canvi de línies i condicions)
            res_put = await client.put(
                f"/api/v1/gestio/pressupostos/{pres_id}",
                json={
                    "titol": "Manteniment estació de bombament (Revisat)",
                    "descompte_global_pct": 0.0,
                    "termini_execucio": "2 dies laborables",
                    "linies": [
                        {
                            "seccio": "Mà d'obra",
                            "concepte": "Intervenció tècnica ajustada",
                            "quantitat": 10,
                            "preu_unitari": 50.0,
                            "descompte_pct": 0.0,
                            "tipus_iva": 21.0,
                        }
                    ],
                },
                headers=headers,
            )
            assert res_put.status_code == 200, res_put.text
            updated = res_put.json()
            assert updated["titol"] == "Manteniment estació de bombament (Revisat)"
            assert updated["base_imposable"] == 500.0
            assert updated["total"] == 605.0
            assert updated["termini_execucio"] == "2 dies laborables"

            # 6. Si el client demana canvis (REBUTJAT), es pot re-editar i torna a PENDENT
            res_reb = await client.post(f"/api/v1/gestio/pressupostos/{pres_id}/rebutjar", headers=headers)
            assert res_reb.status_code == 200
            assert res_reb.json()["estat"] == "REBUTJAT"

            res_reedit = await client.put(
                f"/api/v1/gestio/pressupostos/{pres_id}",
                json={"notes_exclusions": "Inclou revisió de pressostat."},
                headers=headers,
            )
            assert res_reedit.status_code == 200
            assert res_reedit.json()["estat"] == "PENDENT"

            # 7. Aprovar i convertir a OT -> traspassa vehicle_id i adreca_obra!
            res_aprov = await client.post(f"/api/v1/gestio/pressupostos/{pres_id}/aprovar", headers=headers)
            assert res_aprov.status_code == 200

            res_ot = await client.post(f"/api/v1/gestio/pressupostos/{pres_id}/convertir-ot", headers=headers)
            assert res_ot.status_code == 201, res_ot.text
            ot_id = uuid.UUID(res_ot.json()["ordre_treball_id"])

            ot_db = (
                await admin_session.execute(select(OrdreTreball).where(OrdreTreball.id == ot_id))
            ).scalar_one()
            assert ot_db.vehicle_id == vehicle_id
            assert ot_db.adreca == "Estació Bombament Nord, Lleida"
            assert "Trepant Percutor Hilti" not in (ot_db.descripcio or "")
            eina_linked = (
                await admin_session.execute(select(EinaCustodia).where(EinaCustodia.id == eina_id))
            ).scalar_one()
            assert eina_linked.ordre_treball_id == ot_id
            assert eina_linked.estat == "CUSTODIADA"


def test_parsejar_adreca_fiscal_i_contacte_fallback() -> None:
    """Verifica el desglossament automàtic d'adreça fiscal (carrer, CP, població, província) i fallback de contacte."""
    from app.services.pressupost_service import (
        extreure_contacte_fallback,
        parsejar_adreca_fiscal,
    )

    p1 = parsejar_adreca_fiscal("Carrer Major, 12, 08500 Vic (Barcelona)")
    assert p1["adreca"] == "Carrer Major, 12"
    assert p1["codi_postal"] == "08500"
    assert p1["poblacio"] == "Vic"
    assert p1["provincia"] == "Barcelona"

    p2 = parsejar_adreca_fiscal("Pol. Ind. Les Guixeres, nau 4, 17600 Figueres")
    assert p2["adreca"] == "Pol. Ind. Les Guixeres, nau 4"
    assert p2["codi_postal"] == "17600"
    assert p2["poblacio"] == "Figueres"
    assert p2["provincia"] == "Girona"

    p3 = parsejar_adreca_fiscal("Av. Catalunya 10, 43800 Valls, Tarragona")
    assert p3["adreca"] == "Av. Catalunya 10"
    assert p3["codi_postal"] == "43800"
    assert p3["poblacio"] == "Valls"
    assert p3["provincia"] == "Tarragona"

    em, tel = extreure_contacte_fallback(None, None, "Cap d'obra: 612 345 678 / obra@tanca.cat")
    assert em == "obra@tanca.cat"
    assert tel == "612 345 678"


@pytest.mark.asyncio
async def test_pressupost_codi_client_excavadora_hores_cost_eines_operaris_i_ia_json(
    admin_session, headers, boss_token, tmp_path
) -> None:
    """Verifica codi client, dades contacte, multi-slot vehicle+excavadora/hores, cost eines, operaris Cost/Hora i generar-ia JSON."""
    from app.core.security import create_access_token
    from app.models.models import Usuari
    from app.services.copilot_config_service import save_strict_copilot_config
    from tests.wss_test_helpers import live_empresa_wss_context

    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    vault_token = f"svlt_p46b_{uuid.uuid4().hex[:12]}"
    disc_root = tmp_path / "disc_pres_46b"
    inicialitzar_arbre_carpetes_disc(disc_root)

    emp = Empresa(
        id=emp_uuid,
        nom="Tancaments i Obra SL",
        nif="B" + str(uuid.uuid4())[:8].upper(),
        subdomini="pres46b-" + str(uuid.uuid4())[:5],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
        disc_dur_url=f"wss-tunnel://{emp_uuid}",
        node_ia_url=f"wss-tunnel://{emp_uuid}",
        vault_token=vault_token,
        feature_copilot_ia=True,
        node_ia_actiu=True,
    )
    admin_session.add(emp)
    await admin_session.flush()

    cli_id = uuid.uuid4()
    veh_furg_id = uuid.uuid4()
    veh_exc_id = uuid.uuid4()
    eina_id = uuid.uuid4()
    op_id = uuid.uuid4()
    eng_id = uuid.uuid4()

    admin_session.add_all(
        [
            Client(
                id=cli_id,
                empresa_id=emp_uuid,
                codi="CLI-0042",
                rao_social="Masia La Serra SL",
                nif="B44556677",
                adreca_fiscal="Camí de la Serra, 8, 08500 Vic",
                codi_postal=None,
                poblacio=None,
                provincia=None,
                persona_contacte="Marc Serra",
                dades_contacte="Encarregat finca · horari 8-14h · marc@masia.cat · 699 112 233",
                email=None,
                telefon=None,
            ),
            Vehicle(
                id=veh_furg_id,
                empresa_id=emp_uuid,
                matricula="1111-FUR",
                marca="Renault",
                model="Master",
                tipus="THERMIC",
            ),
            Vehicle(
                id=veh_exc_id,
                empresa_id=emp_uuid,
                matricula="E-9900-EXC",
                marca="Kubota",
                model="KX027 Mini-Excavadora",
                tipus="MAQUINARIA",
                tarifa_diaria_eur=520.0,
            ),
            EinaCustodia(
                id=eina_id,
                empresa_id=emp_uuid,
                nom="Foradadora de Pilons Hidràulica",
                model="FP-200",
                numero_serie="FP-2026-01",
            ),
            Usuari(
                id=op_id,
                empresa_id=emp_uuid,
                nif="12345678A",
                nom="Oriol",
                cognoms="Casals",
                telefon="600222333",
                rol="OPERARI",
                estat="ACTIU",
                especialitat="CONDUCTOR_MAQUINARIA",
                cost_hora_eur=34.50,
            ),
            Usuari(
                id=eng_id,
                empresa_id=emp_uuid,
                nif="87654321B",
                nom="Laia",
                cognoms="Vidal",
                email="laia@tancaments.cat",
                rol="ENGINYER",
                estat="ACTIU",
                cost_hora_eur=48.00,
            ),
        ]
    )
    await admin_session.commit()

    await save_strict_copilot_config(
        db=admin_session,
        empresa_id=emp_uuid,
        system_prompt="Ets el Copilot tècnic de pressupostos de Tancaments i Obra SL.",
        rag_prompt="",
        subagent_prompts={},
    )

    eng_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': str(eng_id), 'rol': 'ENGINYER', 'empresa_id': empresa_id})}",
        "X-Empresa-ID": empresa_id,
    }

    async with live_empresa_wss_context(emp_uuid, vault_token, disc_root):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. GET /gestio/clients ha de resoldre codi, CP, població i província des d'adreca_fiscal
            res_cli = await client.get("/api/v1/gestio/clients", headers=headers)
            assert res_cli.status_code == 200
            cli_item = next(c for c in res_cli.json() if c["id"] == str(cli_id))
            assert cli_item["codi"] == "CLI-0042"
            assert cli_item["codi_postal"] == "08500"
            assert cli_item["poblacio"] == "Vic"
            assert cli_item["provincia"] == "Barcelona"
            assert "Encarregat finca" in (cli_item["dades_contacte"] or "")

            # 2. GET /gestio/pressupostos/operaris-imputacio retorna Cost/Hora Imputació d'Obra per BOSS i l'oculta a ENGINYER
            res_ops = await client.get("/api/v1/gestio/pressupostos/operaris-imputacio", headers=headers)
            assert res_ops.status_code == 200, res_ops.text
            ops_boss = res_ops.json()
            op_oriol = next(o for o in ops_boss if o["id"] == str(op_id))
            assert op_oriol["cost_hora_eur"] == 34.50
            assert op_oriol["nom_complet"] == "Oriol Casals"

            res_ops_eng = await client.get(
                "/api/v1/gestio/pressupostos/operaris-imputacio", headers=eng_headers
            )
            assert res_ops_eng.status_code == 200
            op_oriol_eng = next(o for o in res_ops_eng.json() if o["id"] == str(op_id))
            assert op_oriol_eng["cost_hora_eur"] is None

            # 3. Crear pressupost amb multi-slot (furgoneta km + excavadora hores) + eina amb cost + mà d'obra operari
            res_p = await client.post(
                "/api/v1/gestio/pressupostos",
                json={
                    "client_id": str(cli_id),
                    "numero": "P-2026/042",
                    "titol": "Reparació tanca perimetral 2 km",
                    "vehicles_desplacaments": [
                        {
                            "vehicle_id": str(veh_furg_id),
                            "km": 60,
                            "preu_km": 0.45,
                            "import_fix": 20.0,
                        },
                        {
                            "vehicle_id": str(veh_exc_id),
                            "hores": 6.0,
                            "preu_hora": 65.0,
                        },
                    ],
                    "eines_ids": [str(eina_id)],
                    "eines_assignades": [
                        {
                            "id": str(eina_id),
                            "quantitat": 4.0,
                            "unitat": "h",
                            "cost_eur": 25.0,
                        }
                    ],
                    "linies": [
                        {
                            "operari_id": str(op_id),
                            "seccio": "Mà d'obra i instal·lació",
                            "tipus_linia": "MA_OBRA",
                            "concepte": "Mà d'obra — Oriol Casals",
                            "quantitat": 8,
                            "preu_unitari": 34.50,
                            "tipus_iva": 21.0,
                        },
                        {
                            "vehicle_id": str(veh_exc_id),
                            "seccio": "Desplaçament i vehicle",
                            "tipus_linia": "MAQUINARIA",
                            "concepte": "Ús per hores (E-9900-EXC · Kubota KX027)",
                            "quantitat": 6,
                            "preu_unitari": 65.0,
                            "tipus_iva": 21.0,
                        },
                        {
                            "eina_id": str(eina_id),
                            "seccio": "Eines i maquinària",
                            "tipus_linia": "EINA",
                            "concepte": "Ús d'eina: Foradadora de Pilons Hidràulica",
                            "quantitat": 4,
                            "preu_unitari": 25.0,
                            "tipus_iva": 21.0,
                        },
                    ],
                },
                headers=headers,
            )
            assert res_p.status_code == 201, res_p.text
            p_data = res_p.json()
            assert p_data["client_codi"] == "CLI-0042"
            assert p_data["referencia_client"] == "CLI-0042"
            assert p_data["client_adreca"] == "Camí de la Serra, 8"
            assert p_data["client_codi_postal"] == "08500"
            assert p_data["client_poblacio"] == "Vic"
            assert p_data["client_provincia"] == "Barcelona"
            assert p_data["client_email"] == "marc@masia.cat"
            assert p_data["client_telefon"] == "699 112 233"
            assert "Encarregat finca" in (p_data["client_dades_contacte"] or "")
            assert len(p_data["vehicles_desplacaments"]) == 2
            assert p_data["vehicles_desplacaments"][1]["hores"] == 6.0
            assert p_data["vehicles_desplacaments"][1]["preu_hora"] == 65.0
            assert p_data["eines_resum"][0]["cost_eur"] == 25.0
            assert p_data["eines_resum"][0]["quantitat"] == 4.0
            assert p_data["eines_resum"][0]["unitat"] == "h"
            assert p_data["linies"][0]["operari_id"] == str(op_id)

            # 4. HTML renderitza codi client, dades contacte, excavadora hores i cost d'eina
            res_html = await client.get(
                f"/api/v1/gestio/pressupostos/{p_data['id']}/html", headers=headers
            )
            assert res_html.status_code == 200
            assert "Codi client: CLI-0042" in res_html.text
            assert "08500 Vic (Barcelona)" in res_html.text
            assert "marc@masia.cat" in res_html.text
            assert "E-9900-EXC" in res_html.text
            assert "65,00 €/h" in res_html.text
            assert "25,00 €/h" in res_html.text

            # 5. Copilot IA accepta JSON body, resol automàticament el model viu encara que el perfil tingui un model antic
            #    i aplica pressupost de timeout >= 65s (evitant 503 prematurs en inferència CPU local)
            await save_strict_copilot_config(
                db=admin_session,
                empresa_id=emp_uuid,
                system_prompt="Ets el Copilot tècnic de pressupostos de Tancaments i Obra SL.\n\n" + ("Detall extens de context. " * 120),
                rag_prompt="Instruccions RAG llargues per xat general.",
                subagent_prompts={},
                llm_chat_model="model-antic-no-carregat",
                timeout_budget_s=18.0,
            )
            res_ia = await client.post(
                "/api/v1/gestio/pressupostos/generar-ia",
                json={
                    "prompt": "Reparació canvi de tanca perimetral — malla 10x10x160 i pilons acàcia 20x190, 2 Km",
                    "client_id": str(cli_id),
                },
                headers=headers,
            )
            assert res_ia.status_code == 200, res_ia.text
            assert res_ia.json()["status"] == "PENDENT_AUDITORIA"
            assert res_ia.json()["draft"]["resum_tecnic"]

            # 6. Eines manuals/lloguer (id=None) amb decimals també es persisteixen i es mostren a l'HTML
            res_upd = await client.put(
                f"/api/v1/gestio/pressupostos/{p_data['id']}",
                json={
                    "client_id": str(cli_id),
                    "numero": "P-2026/042",
                    "titol": "Reparació tanca perimetral 2 km",
                    "eines_assignades": [
                        {
                            "id": str(eina_id),
                            "nom": "Clavadora de pilons hidràulica",
                            "quantitat": 4.5,
                            "unitat": "h",
                            "cost_eur": 25.0,
                        },
                        {
                            "id": None,
                            "nom": "Ahoyadora tèrmica lloguer",
                            "quantitat": 2.5,
                            "unitat": "h",
                            "cost_eur": 18.75,
                        },
                    ],
                    "linies": p_data["linies"],
                },
                headers=headers,
            )
            assert res_upd.status_code == 200, res_upd.text
            upd_data = res_upd.json()
            assert len(upd_data["eines_resum"]) == 2
            assert upd_data["eines_resum"][1]["nom"] == "Ahoyadora tèrmica lloguer"
            assert upd_data["eines_resum"][1]["quantitat"] == 2.5
            assert upd_data["eines_resum"][1]["cost_eur"] == 18.75


@pytest.mark.asyncio
async def test_convertir_pressupost_a_ot_importacio_completa_materials_eines_hores_i_rls(
    admin_session, headers, boss_token, tmp_path
) -> None:
    """Verifica el traspàs complet de pressupost aprovat a OT: materials (picking + reserva estoc), eines en custòdia, hores previstes, tarifa/h, operaris, vehicle, km, coordenades i aïllament RLS."""
    from app.core.security import create_access_token
    from app.models.models import (
        Article,
        EstocMagatzem,
        Finca,
        FullaPicking,
        LiniaPicking,
        Magatzem,
        OrdreTreballOperari,
        Usuari,
    )
    from tests.wss_test_helpers import live_empresa_wss_context

    _, empresa_id = boss_token
    emp_uuid = uuid.UUID(empresa_id)
    vault_token = f"svlt_otimp_{uuid.uuid4().hex[:12]}"
    disc_root = tmp_path / "disc_pres_ot_complet"
    inicialitzar_arbre_carpetes_disc(disc_root)

    emp = Empresa(
        id=emp_uuid,
        nom="Instal·lacions Totals SL",
        nif="B" + str(uuid.uuid4())[:8].upper(),
        subdomini="otimp-" + str(uuid.uuid4())[:6],
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
        disc_dur_url=f"wss-tunnel://{emp_uuid}",
        node_ia_url=f"wss-tunnel://{emp_uuid}",
        vault_token=vault_token,
    )
    # Segon tenant per validar aïllament RLS
    emp2_uuid = uuid.uuid4()
    emp2 = Empresa(
        id=emp2_uuid,
        nom="Altra Empresa RLS SL",
        nif="B" + str(uuid.uuid4())[:8].upper(),
        subdomini="rlsother-" + str(uuid.uuid4())[:6],
        pla_subscripcio="STARTER",
        estat_pagament="ACTIU",
    )
    admin_session.add_all([emp, emp2])
    await admin_session.flush()

    cli_id = uuid.uuid4()
    finca_id = uuid.uuid4()
    mag_id = uuid.uuid4()
    art_stock_ok_id = uuid.uuid4()
    art_stock_parcial_id = uuid.uuid4()
    art_ref_only_id = uuid.uuid4()
    veh_furg_id = uuid.uuid4()
    veh_exc_id = uuid.uuid4()
    eina_1_id = uuid.uuid4()
    eina_2_id = uuid.uuid4()
    cap_id = uuid.uuid4()
    op2_id = uuid.uuid4()
    other_boss_id = uuid.uuid4()

    admin_session.add_all(
        [
            Client(
                id=cli_id,
                empresa_id=emp_uuid,
                codi="CLI-IMP1",
                rao_social="Agrària Completa SL",
                nif="B99887766",
                adreca_fiscal="Camí del Canal, 5, 25200 Cervera",
            ),
            Finca(
                id=finca_id,
                empresa_id=emp_uuid,
                client_id=cli_id,
                nom="Finca Parcel·la Nord",
                adreca="Polígon 4, Parcel·la 12, Cervera",
                latitud=41.670123,
                longitud=1.271456,
            ),
            Magatzem(
                id=mag_id,
                empresa_id=emp_uuid,
                nom="Nau Central Cervera",
                tipus="NAU_CENTRAL",
            ),
            Article(
                id=art_stock_ok_id,
                empresa_id=emp_uuid,
                referencia_inventari="TUB-PE-50",
                nom="Tub PEAD 50mm PN10",
                unitat_mesura="METRES",
                preu_cost=2.10,
                preu_venda=4.50,
            ),
            Article(
                id=art_stock_parcial_id,
                empresa_id=emp_uuid,
                referencia_inventari="VALV-EL-2",
                nom="Electrovàlvula 2 polzades",
                unitat_mesura="UNITAT",
                preu_cost=35.00,
                preu_venda=65.00,
            ),
            Article(
                id=art_ref_only_id,
                empresa_id=emp_uuid,
                referencia_inventari="COL-50",
                nom="Colze 90º PE 50mm",
                unitat_mesura="UNITAT",
                preu_cost=1.50,
                preu_venda=3.80,
            ),
            Vehicle(
                id=veh_furg_id,
                empresa_id=emp_uuid,
                matricula="7788-MNP",
                marca="Ford",
                model="Transit",
                estat="OPERATIU",
                carnet_necessari="B",
            ),
            Vehicle(
                id=veh_exc_id,
                empresa_id=emp_uuid,
                matricula="E-1234-KB",
                marca="Kubota",
                model="KX019",
                tipus="MAQUINARIA",
                estat="OPERATIU",
            ),
            EinaCustodia(
                id=eina_1_id,
                empresa_id=emp_uuid,
                nom="Termofusora 20-63mm",
                model="TF-63",
                numero_serie="SN-TF63-01",
                estat="DISPONIBLE",
            ),
            EinaCustodia(
                id=eina_2_id,
                empresa_id=emp_uuid,
                nom="Detector de Fuites Acústic",
                model="DFA-9",
                numero_serie="SN-DFA9-02",
                estat="DISPONIBLE",
            ),
            Usuari(
                id=cap_id,
                empresa_id=emp_uuid,
                nif="11111111C",
                nom="Jordi",
                cognoms="Soler",
                rol="CAP_DE_COLLA",
                estat="ACTIU",
                carnet_conduir="B",
                cost_hora_eur=28.00,
            ),
            Usuari(
                id=op2_id,
                empresa_id=emp_uuid,
                nif="22222222D",
                nom="Pau",
                cognoms="Valls",
                rol="OPERARI",
                estat="ACTIU",
                carnet_conduir="B",
                cost_hora_eur=24.00,
            ),
            Usuari(
                id=other_boss_id,
                empresa_id=emp2_uuid,
                nif="33333333E",
                nom="Anna",
                cognoms="Altres",
                rol="BOSS",
                estat="ACTIU",
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add_all(
        [
            EstocMagatzem(
                empresa_id=emp_uuid,
                article_id=art_stock_ok_id,
                magatzem_id=mag_id,
                quantitat_fisica=100.0,
                quantitat_virtual_reservada=0.0,
            ),
            EstocMagatzem(
                empresa_id=emp_uuid,
                article_id=art_stock_parcial_id,
                magatzem_id=mag_id,
                quantitat_fisica=2.0,
                quantitat_virtual_reservada=0.0,
            ),
            EstocMagatzem(
                empresa_id=emp_uuid,
                article_id=art_ref_only_id,
                magatzem_id=mag_id,
                quantitat_fisica=50.0,
                quantitat_virtual_reservada=0.0,
            ),
        ]
    )
    await admin_session.commit()

    other_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': str(other_boss_id), 'rol': 'BOSS', 'empresa_id': str(emp2_uuid)})}",
        "X-Empresa-ID": str(emp2_uuid),
    }

    async with live_empresa_wss_context(emp_uuid, vault_token, disc_root):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res_create = await client.post(
                "/api/v1/gestio/pressupostos",
                json={
                    "client_id": str(cli_id),
                    "numero": "P-2026/900",
                    "titol": "Instal·lació reg sector Nord",
                    "descripcio": "Rasa, estesa de tub i muntatge de vàlvules.",
                    "finca_id": str(finca_id),
                    "adreca_obra": "Polígon 4, Parcel·la 12, Cervera",
                    "vehicles_desplacaments": [
                        {"vehicle_id": str(veh_furg_id), "km": 48, "preu_km": 0.50},
                        {"vehicle_id": str(veh_exc_id), "hores": 4.0, "preu_hora": 60.0},
                    ],
                    "eines_ids": [str(eina_1_id)],
                    "eines_assignades": [
                        {"id": str(eina_1_id), "quantitat": 5.0, "unitat": "h", "cost_eur": 15.0},
                        {"id": None, "nom": "Compactadora lloguer", "quantitat": 1.0, "unitat": "dia", "cost_eur": 85.0},
                    ],
                    "termini_execucio": "2 dies laborables",
                    "notes_exclusions": "Client aporta punt elèctric.",
                    "linies": [
                        {
                            "operari_id": str(op2_id),
                            "seccio": "Mà d'obra i instal·lació",
                            "tipus_linia": "MA_OBRA",
                            "concepte": "Mà d'obra — Pau Valls",
                            "quantitat": 6.5,
                            "preu_unitari": 42.0,
                            "tipus_iva": 21.0,
                        },
                        {
                            "operari_id": str(cap_id),
                            "seccio": "Mà d'obra i instal·lació",
                            "tipus_linia": "MA_OBRA",
                            "concepte": "Mà d'obra — Jordi Soler",
                            "quantitat": 3.5,
                            "preu_unitari": 42.0,
                            "tipus_iva": 21.0,
                        },
                        {
                            "article_id": str(art_stock_ok_id),
                            "seccio": "Materials i subministraments",
                            "tipus_linia": "MATERIAL",
                            "concepte": "[TUB-PE-50] Tub PEAD 50mm PN10",
                            "quantitat": 20.0,
                            "preu_unitari": 4.50,
                            "tipus_iva": 21.0,
                        },
                        {
                            "article_id": str(art_stock_ok_id),
                            "seccio": "Materials i subministraments",
                            "tipus_linia": "MATERIAL",
                            "concepte": "[TUB-PE-50] Tub PEAD 50mm PN10 (ampliació)",
                            "quantitat": 10.0,
                            "preu_unitari": 4.50,
                            "tipus_iva": 21.0,
                        },
                        {
                            "article_id": str(art_stock_parcial_id),
                            "seccio": "Materials i subministraments",
                            "tipus_linia": "MATERIAL",
                            "concepte": "[VALV-EL-2] Electrovàlvula 2 polzades",
                            "quantitat": 5.0,
                            "preu_unitari": 65.00,
                            "tipus_iva": 21.0,
                        },
                        {
                            "seccio": "Materials i subministraments",
                            "tipus_linia": "MATERIAL",
                            "concepte": "[COL-50] Colze 90º PE 50mm",
                            "quantitat": 8.0,
                            "preu_unitari": 3.80,
                            "tipus_iva": 21.0,
                        },
                        {
                            "seccio": "Materials i subministraments",
                            "tipus_linia": "MATERIAL",
                            "concepte": "Grava rentada a granel (fora de catàleg)",
                            "quantitat": 2.0,
                            "preu_unitari": 40.0,
                            "tipus_iva": 21.0,
                        },
                        {
                            "eina_id": str(eina_2_id),
                            "seccio": "Eines i maquinària",
                            "tipus_linia": "EINA",
                            "concepte": "Ús d'eina: Detector de Fuites Acústic",
                            "quantitat": 2.0,
                            "preu_unitari": 20.0,
                            "tipus_iva": 21.0,
                        },
                        {
                            "vehicle_id": str(veh_exc_id),
                            "seccio": "Desplaçament i vehicle",
                            "tipus_linia": "MAQUINARIA",
                            "concepte": "Ús per hores (E-1234-KB · Kubota KX019)",
                            "quantitat": 4.0,
                            "preu_unitari": 60.0,
                            "tipus_iva": 21.0,
                        },
                    ],
                },
                headers=headers,
            )
            assert res_create.status_code == 201, res_create.text
            pres_id = res_create.json()["id"]

            # Aprovar i convertir a OT
            res_aprov = await client.post(
                f"/api/v1/gestio/pressupostos/{pres_id}/aprovar", headers=headers
            )
            assert res_aprov.status_code == 200, res_aprov.text

            # RLS: Un altre tenant no pot convertir el pressupost
            res_rls_conv = await client.post(
                f"/api/v1/gestio/pressupostos/{pres_id}/convertir-ot", headers=other_headers
            )
            assert res_rls_conv.status_code == 404

            res_ot = await client.post(
                f"/api/v1/gestio/pressupostos/{pres_id}/convertir-ot", headers=headers
            )
            assert res_ot.status_code == 201, res_ot.text
            conv_data = res_ot.json()
            ot_id = uuid.UUID(conv_data["ordre_treball_id"])
            assert conv_data["materials_importats"] == 3
            assert conv_data["eines_importades"] == 2
            assert conv_data["operaris_importats"] == 2
            assert conv_data["hores_previstes"] == 10.0
            assert conv_data["preu_venda_hora_aplicat"] == 42.0
            assert conv_data["km_previstos"] == 48
            assert any("Electrovàlvula" in av for av in conv_data["avisos"])

            # Verificar persistència real a PostgreSQL
            ot_db = (
                await admin_session.execute(select(OrdreTreball).where(OrdreTreball.id == ot_id))
            ).scalar_one()
            assert ot_db.estat == "ASSIGNADA"
            assert ot_db.cap_de_colla_id == cap_id
            assert ot_db.vehicle_id == veh_furg_id
            assert ot_db.finca_id == finca_id
            assert float(ot_db.latitud) == pytest.approx(41.670123, rel=1e-4)
            assert float(ot_db.longitud) == pytest.approx(1.271456, rel=1e-4)
            assert ot_db.km_imputats == 48
            assert float(ot_db.cost_flota_real) > 0.0
            assert float(ot_db.cost_materials_picking_pmp) > 0.0
            assert float(ot_db.pvp_materials_aplicat) > 0.0
            assert float(ot_db.hores_imputades_facturables) == 0.0
            assert float(ot_db.preu_venda_hora_aplicat) == 42.0
            assert ot_db.hora_inici_prevista is not None
            assert ot_db.hora_fi_prevista is not None
            dur_h = (ot_db.hora_fi_prevista - ot_db.hora_inici_prevista).total_seconds() / 3600.0
            assert dur_h == pytest.approx(10.0, rel=1e-3)
            # La descripció ha de ser neta: MAI bolcar eines, materials ni hores com a text pla
            desc_ot = ot_db.descripcio or ""
            assert "Rasa, estesa de tub i muntatge de vàlvules." in desc_ot
            assert "Eines previstes" not in desc_ot
            assert "Hores de treball previstes" not in desc_ot
            assert "Materials fora de catàleg" not in desc_ot
            assert "Vehicles / Maquinària previstos" not in desc_ot
            assert any("Grava rentada a granel" in av for av in conv_data["avisos"])
            assert any("Compactadora lloguer" in av for av in conv_data["avisos"])

            # Vehicle sincronitzat a ASSIGNAT
            veh_db = (
                await admin_session.execute(select(Vehicle).where(Vehicle.id == veh_furg_id))
            ).scalar_one()
            assert veh_db.estat == "ASSIGNAT"

            # Quadrilla d'operaris importada
            ops_db = (
                await admin_session.execute(
                    select(OrdreTreballOperari).where(OrdreTreballOperari.ordre_treball_id == ot_id)
                )
            ).scalars().all()
            assert {o.operari_id for o in ops_db} == {cap_id, op2_id}
            assert any(o.operari_id == cap_id and o.es_cap_de_colla for o in ops_db)

            # Eines en custòdia vinculades a l'OT
            eines_db = (
                await admin_session.execute(
                    select(EinaCustodia).where(EinaCustodia.ordre_treball_id == ot_id)
                )
            ).scalars().all()
            assert {e.id for e in eines_db} == {eina_1_id, eina_2_id}
            assert all(e.estat == "CUSTODIADA" and e.custodiat_per_operari_id == cap_id for e in eines_db)

            # FullaPicking + LiniaPicking + reserves d'estoc
            fulla_db = (
                await admin_session.execute(
                    select(FullaPicking).where(FullaPicking.ordre_treball_id == ot_id)
                )
            ).scalar_one()
            linies_pk = (
                await admin_session.execute(
                    select(LiniaPicking).where(LiniaPicking.picking_id == fulla_db.id)
                )
            ).scalars().all()
            pk_by_art = {lp.article_id: float(lp.quantitat_prevista) for lp in linies_pk}
            assert pk_by_art == {
                art_stock_ok_id: 30.0,  # 20 + 10 agregats
                art_stock_parcial_id: 5.0,  # importat complet encara que estoc era 2
                art_ref_only_id: 8.0,  # resolt via [COL-50]
            }

            estoc_ok = (
                await admin_session.execute(
                    select(EstocMagatzem).where(EstocMagatzem.article_id == art_stock_ok_id)
                )
            ).scalar_one()
            assert float(estoc_ok.quantitat_virtual_reservada) == 30.0

            estoc_parcial = (
                await admin_session.execute(
                    select(EstocMagatzem).where(EstocMagatzem.article_id == art_stock_parcial_id)
                )
            ).scalar_one()
            assert float(estoc_parcial.quantitat_virtual_reservada) == 2.0

            # Verificar GET /gestio/feines/{ot_id} i GET /gestio/feines/{ot_id}/conciliacio
            res_feina = await client.get(f"/api/v1/gestio/feines/{ot_id}", headers=headers)
            assert res_feina.status_code == 200, res_feina.text
            f_json = res_feina.json()
            assert f_json["hores_previstes"] == 10.0
            assert f_json["preu_venda_hora_aplicat"] == 42.0
            assert f_json["vehicle_id"] == str(veh_furg_id)
            assert f_json["vehicle_matricula"] == "7788-MNP"
            assert f_json["km_imputats"] == 48
            assert f_json["import_pressupostat"] > 0
            assert len(f_json["linies_picking"]) == 3
            assert all(lp["preu_venda_unitari"] > 0 for lp in f_json["linies_picking"])
            assert len(f_json["eines"]) == 2
            assert len(f_json["operaris_assignats"]) == 2

            res_conc = await client.get(f"/api/v1/gestio/feines/{ot_id}/conciliacio", headers=headers)
            assert res_conc.status_code == 200, res_conc.text
            c_json = res_conc.json()
            assert c_json["temps_i_gps"]["hores_previstes"] == 10.0
            assert c_json["materials"]["total_linies"] == 3
            assert len(c_json["eines"]) == 2
            assert c_json["vehicle"]["matricula"] == "7788-MNP"
            assert c_json["pressupost"]["numero"] == "P-2026/900"
            assert c_json["resum_comercial"]["valor_ma_obra_previst_pvp"] == pytest.approx(420.0)
            assert c_json["resum_intern"]["cost_ma_obra_previst"] == pytest.approx(280.0)
            assert c_json["resum_intern"]["cost_flota_real"] > 0
            assert c_json["resum_intern"]["cost_total_previst"] > 0
            assert c_json["resum_intern"]["marge_previst_eur"] is not None

            # Escenari 2: Pressupost sense operari (només hores) -> Fulla 360° assigna operari, vehicle i picking al convertir
            res_p2 = await client.post(
                "/api/v1/gestio/pressupostos",
                json={
                    "client_id": str(cli_id),
                    "numero": "P-2026/901",
                    "titol": "Manteniment bomba sense operari inicial",
                    "descripcio": "Revisió de pressió i substitució de vàlvula.",
                    "vehicle_id": str(veh_furg_id),
                    "desplacament_km": 30,
                    "eines_ids": [str(eina_1_id)],
                    "linies": [
                        {
                            "seccio": "Mà d'obra i instal·lació",
                            "tipus_linia": "MA_OBRA",
                            "concepte": "Mà d'obra tècnica (sense operari assignat)",
                            "quantitat": 4.0,
                            "preu_unitari": 50.0,
                            "tipus_iva": 21.0,
                        },
                        {
                            "article_id": str(art_ref_only_id),
                            "seccio": "Materials i subministraments",
                            "tipus_linia": "MATERIAL",
                            "concepte": "[COL-50] Colze 90º PE 50mm",
                            "quantitat": 4.0,
                            "preu_unitari": 3.80,
                            "tipus_iva": 21.0,
                        },
                    ],
                },
                headers=headers,
            )
            assert res_p2.status_code == 201, res_p2.text
            p2_id = res_p2.json()["id"]
            await client.post(f"/api/v1/gestio/pressupostos/{p2_id}/aprovar", headers=headers)

            res_ot2 = await client.post(
                f"/api/v1/gestio/pressupostos/{p2_id}/convertir-ot",
                json={
                    "cap_de_colla_id": str(cap_id),
                    "operaris_ids": [str(cap_id), str(op2_id)],
                    "vehicle_id": str(veh_furg_id),
                    "km_imputats": 35,
                    "hores_previstes": 4.5,
                    "preu_venda_hora_aplicat": 50.0,
                    "eina_ids": [str(eina_1_id)],
                    "linies_picking": [
                        {"article_id": str(art_ref_only_id), "quantitat_prevista": 4.0}
                    ],
                },
                headers=headers,
            )
            assert res_ot2.status_code == 201, res_ot2.text
            ot2_id = res_ot2.json()["ordre_treball_id"]
            res_f2 = await client.get(f"/api/v1/gestio/feines/{ot2_id}", headers=headers)
            assert res_f2.status_code == 200
            f2 = res_f2.json()
            assert f2["estat"] == "ASSIGNADA"
            assert f2["cap_de_colla_id"] == str(cap_id)
            assert set(f2["operaris_ids"]) == {str(cap_id), str(op2_id)}
            assert f2["vehicle_id"] == str(veh_furg_id)
            assert f2["km_imputats"] == 35
            assert f2["hores_previstes"] == 4.5
            assert len(f2["linies_picking"]) == 1
            assert len(f2["eines"]) == 1
            assert f2["descripcio"] == "Revisió de pressió i substitució de vàlvula."

            # RLS: Segon tenant no pot llegir l'OT ni la seva conciliació
            res_rls_ot = await client.get(f"/api/v1/gestio/feines/{ot_id}", headers=other_headers)
            assert res_rls_ot.status_code == 404
