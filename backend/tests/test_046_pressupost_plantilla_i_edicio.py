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
            assert "Trepant Percutor Hilti" in (ot_db.descripcio or "")
