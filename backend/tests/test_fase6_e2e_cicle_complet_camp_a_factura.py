"""Test E2E Integral Fase 6 — Cicle complet Operari (PWA) -> Enginyer (Fulla 360°) -> Boss (Veri*factu).

Zero Mock Data: PostgreSQL real sobre SAVEPOINT, disc sobirà real, render PDF PyMuPDF, estocs atòmics,
Magic Bytes reals, signatura PNG, conciliació, validació, pre-facturació i emissió Veri*factu.
"""

from __future__ import annotations

import base64
import uuid
from datetime import date, timedelta
from pathlib import Path

import pymupdf  # type: ignore[import-untyped]
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1.operari_auth import create_access_token
from app.core.db import set_tenant_context
from app.main import app
from app.models.models import (
    Article,
    CarpetaPlanol,
    Client,
    Empresa,
    EstocMagatzem,
    FullaPicking,
    LiniaPicking,
    Magatzem,
    MovimentEstoc,
    OrdreTreball,
    PlanolBase,
    Pressupost,
    Usuari,
    Vehicle,
)
from app.services.sovereign_storage import SovereignStorageGateway, inicialitzar_arbre_carpetes_disc

VALID_WEBP_BYTES = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 30
VALID_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
VALID_PNG_BYTES = base64.b64decode(VALID_PNG_B64)
VALID_PNG_DATA_URI = f"data:image/png;base64,{VALID_PNG_B64}"


def _make_pdf_bytes() -> bytes:
    doc = pymupdf.open()  # type: ignore[no-untyped-call]
    p = doc.new_page(width=200, height=200)  # type: ignore[no-untyped-call]
    p.insert_text((20, 40), "Planol E2E Finca Nord")
    raw = doc.tobytes()  # type: ignore[no-untyped-call]
    doc.close()  # type: ignore[no-untyped-call]
    return bytes(raw)


@pytest.mark.asyncio
async def test_fase6_e2e_cicle_complet_operari_enginyer_boss_i_verifactu(
    admin_session,
    tmp_path: Path,
):
    """Certifica d'extrem a extrem totes les Fases 1-5 en un únic flux real sense mocks."""
    disc = tmp_path / "disc_e2e_f6"
    inicialitzar_arbre_carpetes_disc(disc)

    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    op_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    veh_id = uuid.uuid4()
    mag_nau_id = uuid.uuid4()
    mag_van_id = uuid.uuid4()
    art_nau_id = uuid.uuid4()
    art_van_id = uuid.uuid4()
    carpeta_id = uuid.uuid4()
    planol_id = uuid.uuid4()
    ot_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom="Sevalor E2E Fase 6 SL",
            nif="B" + emp_id.hex[:8].upper(),
            subdomini=f"e2e-f6-{emp_id.hex[:6]}",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc),
            node_ia_actiu=True,
        )
    )
    await admin_session.flush()

    admin_session.add(
        Vehicle(
            id=veh_id,
            empresa_id=emp_id,
            matricula=f"99{emp_id.hex[:2].upper()}F6",
            marca="Ford",
            model="Transit Custom",
            estat="ASSIGNAT",
        )
    )
    await admin_session.flush()

    for uid, nom_u, rol_u in [
        (boss_id, "Director", "BOSS"),
        (eng_id, "Enginyera", "ENGINYER"),
        (op_id, "Operari", "OPERARI"),
    ]:
        admin_session.add(
            Usuari(
                id=uid,
                empresa_id=emp_id,
                nif=f"{rol_u[0]}{uid.hex[:7].upper()}E",
                nom=nom_u,
                cognoms="E2E",
                email=f"{rol_u.lower()}-e2e-{emp_id.hex[:6]}@sevalor.test",
                telefon="600999888",
                rol=rol_u,
                vehicle_assignat_id=veh_id if rol_u == "OPERARI" else None,
                pin_hash="fake",
                password_hash="fake",
                estat="ACTIU",
            )
        )

    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"CLI-E2E-{emp_id.hex[:4].upper()}",
            rao_social="Finca Integral E2E SA",
            nif="A" + cli_id.hex[:8].upper(),
            adreca_fiscal="Camí del Reg 99",
            iban_xifrat_simetric="ES7921000813610123456789",
            actiu=True,
        )
    )
    admin_session.add_all(
        [
            Magatzem(id=mag_nau_id, empresa_id=emp_id, nom="Nau Central", tipus="NAU", actiu=True),
            Magatzem(
                id=mag_van_id,
                empresa_id=emp_id,
                nom="Furgoneta 99F6",
                tipus="FURGONETA",
                vehicle_id=veh_id,
                actiu=True,
            ),
            Article(
                id=art_nau_id,
                empresa_id=emp_id,
                referencia_inventari=f"NAU-{emp_id.hex[:4].upper()}",
                nom="Tub PE100 63mm",
                unitat_mesura="METRES_LINEALS",
                preu_cost=5.0,
                preu_cost_mitja=5.0,
                pmp_actual=5.0,
                preu_venda=12.0,
                estoc_total_actual=100.0,
            ),
            Article(
                id=art_van_id,
                empresa_id=emp_id,
                referencia_inventari=f"VAN-{emp_id.hex[:4].upper()}",
                nom="Enllaç Ràpid 63mm",
                unitat_mesura="UNITAT",
                preu_cost=3.0,
                preu_cost_mitja=3.0,
                pmp_actual=3.0,
                preu_venda=8.0,
                estoc_total_actual=20.0,
            ),
            CarpetaPlanol(id=carpeta_id, empresa_id=emp_id, nom="Finques E2E", categoria="FINQUES"),
            Pressupost(
                id=uuid.uuid4(),
                empresa_id=emp_id,
                client_id=cli_id,
                numero=f"PRES-E2E-{emp_id.hex[:4].upper()}",
                total=500.00,
                estat="APROVAT",
            ),
        ]
    )
    await admin_session.flush()

    pdf_path = await SovereignStorageGateway.pujar_fitxer_binari(
        db=admin_session,
        empresa_id=emp_id,
        categoria="planols_tecnics",
        nom_fitxer=f"planol_e2e_{planol_id.hex[:6]}.pdf",
        content=_make_pdf_bytes(),
        content_type="application/pdf",
    )
    admin_session.add(
        PlanolBase(
            id=planol_id,
            empresa_id=emp_id,
            carpeta_id=carpeta_id,
            client_id=cli_id,
            titol="Plànol Hidràulic E2E",
            codi_referencia="PLN-E2E",
            tipus_fitxer="PDF",
            fitxer_path=pdf_path,
            mida_bytes=len(_make_pdf_bytes()),
        )
    )
    admin_session.add_all(
        [
            EstocMagatzem(
                id=uuid.uuid4(),
                empresa_id=emp_id,
                magatzem_id=mag_nau_id,
                article_id=art_nau_id,
                quantitat_fisica=100.0,
                quantitat_virtual_reservada=10.0,
                quantitat_cuarentena=0.0,
            ),
            EstocMagatzem(
                id=uuid.uuid4(),
                empresa_id=emp_id,
                magatzem_id=mag_van_id,
                article_id=art_van_id,
                quantitat_fisica=20.0,
                quantitat_virtual_reservada=0.0,
                quantitat_cuarentena=0.0,
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=emp_id,
            client_id=cli_id,
            cap_de_colla_id=op_id,
            vehicle_id=veh_id,
            planol_id=planol_id,
            codi=f"OT-E2E-{emp_id.hex[:4].upper()}",
            titol="Instal·lació línia principal de reg",
            adreca="Finca E2E, Parcel·la 7",
            estat="ASSIGNADA",
            data_planificacio=date.today(),
            preu_venda_hora_aplicat=60.00,
            import_pressupostat=500.00,
        )
    )
    await admin_session.flush()

    fp_id = uuid.uuid4()
    lp_nau_id = uuid.uuid4()
    admin_session.add(
        FullaPicking(
            id=fp_id,
            empresa_id=emp_id,
            ordre_treball_id=ot_id,
            estat_picking="PENDENT_CARREGA",
        )
    )
    await admin_session.flush()
    admin_session.add(
        LiniaPicking(
            id=lp_nau_id,
            empresa_id=emp_id,
            picking_id=fp_id,
            article_id=art_nau_id,
            magatzem_id=mag_nau_id,
            quantitat_prevista=10.0,
            quantitat_carregada_pick_in=0.0,
            quantitat_retornada_pick_out=0.0,
            quantitat_mermada=0.0,
            origen_estoc="NAU",
        )
    )
    await admin_session.commit()

    def _hdr(uid: uuid.UUID, rol: str) -> dict[str, str]:
        tok = create_access_token(str(uid), rol, str(emp_id), timedelta(minutes=30))
        return {"Authorization": f"Bearer {tok}", "X-Empresa-ID": str(emp_id)}

    h_op = _hdr(op_id, "OPERARI")
    h_eng = _hdr(eng_id, "ENGINYER")
    h_boss = _hdr(boss_id, "BOSS")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # ── BLOC 1: OPERARI A CAMP (PWA) ──
        # 1.1 Renderitzar plànol PDF i desar capa As-Built vinculada a l'OT
        r_render = await ac.get(f"/operari/planols/{planol_id}/render?pagina=1", headers=h_op)
        assert r_render.status_code == 200
        assert r_render.headers["content-type"] == "image/png"
        assert r_render.headers.get("x-total-pages") == "1"

        r_capa = await ac.post(
            f"/operari/planols/{planol_id}/capes",
            json={
                "nom": "Capa As-Built Reg E2E",
                "disciplina": "REG",
                "ordre_treball_id": str(ot_id),
                "geometries_geojson": {"type": "FeatureCollection", "features": []},
            },
            headers=h_op,
        )
        assert r_capa.status_code in (200, 201), r_capa.text

        # 1.2 Obrir i tancar tram de temps
        r_start = await ac.put(f"/operari/feines/{ot_id}/comencar", json={}, headers=h_op)
        assert r_start.status_code == 200, r_start.text
        r_stop = await ac.put(f"/operari/feines/{ot_id}/finalitzar-temps", json={}, headers=h_op)
        assert r_stop.status_code == 200, r_stop.text

        # 1.3 Picking Nau (Pick-In 10 -> Pick-Out 2 retornats + 1 merma => 8 consumits, 1 quarantena)
        r_pin = await ac.put(
            f"/operari/picking/linies/{lp_nau_id}",
            json={"quantitat_carregada_pick_in": 10.0},
            headers=h_op,
        )
        assert r_pin.status_code == 200, r_pin.text
        r_pout = await ac.put(
            f"/operari/picking/linies/{lp_nau_id}",
            json={"quantitat_retornada_pick_out": 2.0, "quantitat_mermada": 1.0},
            headers=h_op,
        )
        assert r_pout.status_code == 200, r_pout.text

        # 1.4 Consum des del magatzem de la furgoneta (3 unitats)
        r_van = await ac.post(
            "/operari/picking/consum-vehicle",
            json={
                "ordre_treball_id": str(ot_id),
                "article_id": str(art_van_id),
                "quantitat": 3.0,
            },
            headers=h_op,
        )
        assert r_van.status_code == 201, r_van.text

        # 1.5 Pujar 3 fotos QA reals (Magic Bytes)
        for tipus in ("INICIAL", "INTERMEDIA", "FINAL"):
            r_f = await ac.post(
                f"/operari/feines/{ot_id}/fotos",
                data={"tipus": tipus},
                files={"foto": (f"{tipus.lower()}.webp", VALID_WEBP_BYTES, "image/webp")},
                headers=h_op,
            )
            assert r_f.status_code == 200, r_f.text

        # 1.6 Capturar tiquet de despesa vinculat a l'OT
        r_tiq = await ac.post(
            "/operari/tiquets/captura-rapida",
            data={"categoria": "FERRETERIA", "ordre_treball_id": str(ot_id)},
            files={"foto_tiquet": ("tiquet_e2e.webp", VALID_WEBP_BYTES, "image/webp")},
            headers=h_op,
        )
        assert r_tiq.status_code == 201, r_tiq.text

        # 1.7 Tancar feina amb Signatura PNG real + Receptor + Observacions
        r_fin = await ac.put(
            f"/operari/feines/{ot_id}/finalitzar",
            json={
                "signatura_base64": VALID_PNG_DATA_URI,
                "nom_receptor": "Ramon Propietari",
                "dni_receptor": "77889900X",
                "observacions": "Prova hidràulica OK a 5 bar.",
                "hores": 2.0,
            },
            headers=h_op,
        )
        assert r_fin.status_code == 200, r_fin.text

        # ── BLOC 2: ENGINYER AL PANELL DE CONTROL (FULLA 360° I FITXA CLIENT) ──
        r_conc = await ac.get(f"/gestio/feines/{ot_id}/conciliacio", headers=h_eng)
        assert r_conc.status_code == 200, r_conc.text
        c_data = r_conc.json()
        assert c_data["disclaimer"]["codi"] == "CONCLOSA_PENDENT_VALIDACIO"
        assert c_data["fotos_qa"]["protocol_complet"] is True
        assert c_data["signatura"]["present"] is True
        assert c_data["signatura"]["nom_receptor"] == "Ramon Propietari"
        assert len(c_data["materials"]["linies"]) == 2
        assert {m["origen_estoc"] for m in c_data["materials"]["linies"]} == {"NAU", "FURGONETA"}
        assert len(c_data["capes_gis"]) == 1
        assert c_data["tiquets"]["total"] == 1
        assert c_data["resum_intern"]["cost_materials_pmp"] is None
        assert c_data["resum_intern"]["marge_real_eur"] is None

        # Validar conciliació (ajustant a 2.0h exactes)
        r_val = await ac.put(
            f"/gestio/feines/{ot_id}/validar-conciliacio",
            json={
                "hores_imputades_facturables": 2.0,
                "checklist_conciliacio": {
                    "hores_revisades": True,
                    "materials_conciliats": True,
                    "evidencies_comprovades": True,
                    "incidencies_tiquets": True,
                },
                "notes_validacio_tecnica": "Validació tècnica E2E OK.",
            },
            headers=h_eng,
        )
        assert r_val.status_code == 200, r_val.text
        assert r_val.json()["disclaimer"]["codi"] == "VALIDADA_PENDENT_FACTURAR"

        # Passar a pre-facturació des de la Fulla 360° (ENGINYER)
        r_pre = await ac.post(
            f"/gestio/feines/{ot_id}/passar-a-prefacturacio",
            headers=h_eng,
        )
        assert r_pre.status_code == 201, r_pre.text
        pre_id = r_pre.json()["id"]
        # Base = 2h*60 (120) + 8m*12 (96) + 3u*8 (24) = 240.00; IVA 21% = 50.40; Total = 290.40
        assert float(r_pre.json()["base_imposable"]) == pytest.approx(240.00, abs=0.02)
        assert float(r_pre.json()["liquid_exigible"]) == pytest.approx(290.40, abs=0.02)

        # Enginyer verifica Fitxa 360° Client + PDF de la pre-factura + barrera 403 Comptabilitat
        r_cli = await ac.get(f"/gestio/clients/{cli_id}/fitxa-360", headers=h_eng)
        assert r_cli.status_code == 200
        assert r_cli.json()["client"]["iban"] is None
        assert r_cli.json()["pressupostos"][0]["total"] == pytest.approx(500.00)
        assert r_cli.json()["factures"][0]["id"] == pre_id

        r_pdf_pre = await ac.get(
            f"/gestio/operativa-financera/factures/{pre_id}/pdf", headers=h_eng
        )
        assert r_pdf_pre.status_code == 200
        assert r_pdf_pre.content.startswith(b"%PDF")

        assert (await ac.get("/gestio/comptabilitat/factures", headers=h_eng)).status_code == 403

        # ── BLOC 3: BOSS EMET FACTURA FINAL VERI*FACTU ──
        r_emit = await ac.post(
            f"/gestio/comptabilitat/prefactures/{pre_id}/emetre",
            json={"serie": "F", "confirmacio_humana_hitl": True},
            headers=h_boss,
        )
        assert r_emit.status_code == 200, r_emit.text

        # Verificar transició automàtica del Disclaimer a FACTURADA i PDF final accessible a Enginyer
        r_conc_end = await ac.get(f"/gestio/feines/{ot_id}/conciliacio", headers=h_eng)
        assert r_conc_end.status_code == 200
        assert r_conc_end.json()["disclaimer"]["codi"] == "FACTURADA"
        assert r_conc_end.json()["factura"]["estat_document"] == "EMESA"

        r_pdf_final = await ac.get(
            f"/gestio/operativa-financera/factures/{pre_id}/pdf", headers=h_eng
        )
        assert r_pdf_final.status_code == 200
        assert r_pdf_final.content.startswith(b"%PDF")

    # ── BLOC 4: VERIFICACIÓ DIRECTA A POSTGRESQL (ESTOCS I MOVIMENTS) ──
    await set_tenant_context(admin_session, str(emp_id), role="BOSS")
    estoc_nau = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == emp_id,
                EstocMagatzem.magatzem_id == mag_nau_id,
                EstocMagatzem.article_id == art_nau_id,
            )
        )
    ).scalar_one()
    # 100 físics - 8 baixes (7 consum + 1 merma) = 92; quarantena = 1; reservat = 0
    assert float(estoc_nau.quantitat_fisica) == pytest.approx(92.0)
    assert float(estoc_nau.quantitat_cuarentena) == pytest.approx(1.0)
    assert float(estoc_nau.quantitat_virtual_reservada) == pytest.approx(0.0)

    estoc_van = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == emp_id,
                EstocMagatzem.magatzem_id == mag_van_id,
                EstocMagatzem.article_id == art_van_id,
            )
        )
    ).scalar_one()
    assert float(estoc_van.quantitat_fisica) == pytest.approx(17.0)

    movs = (
        await admin_session.execute(
            select(MovimentEstoc).where(MovimentEstoc.empresa_id == emp_id)
        )
    ).scalars().all()
    assert len(movs) >= 2
