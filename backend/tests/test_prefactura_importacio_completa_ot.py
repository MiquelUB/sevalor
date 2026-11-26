"""Tests de regressió: Importació completa de camps d'OT conciliada i Pressupost a Pre-factura."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.operari_auth import create_access_token
from app.main import app
from app.models.models import (
    Article,
    Client,
    Empresa,
    EstocMagatzem,
    FullaPicking,
    HistorialAssignacioVehicle,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    OrdreTreballTramTemps,
    Pressupost,
    TiquetDespesa,
    Usuari,
    Vehicle,
)
from app.services.pressupost_service import desar_detalls_pressupost_disc
from app.services.sovereign_storage import inicialitzar_arbre_carpetes_disc


async def _seed_tenant_pref(admin_session, disc_root: Path, label: str) -> Dict[str, Any]:
    inicialitzar_arbre_carpetes_disc(disc_root)
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    op_id = uuid.uuid4()
    cli_id = uuid.uuid4()
    mag_id = uuid.uuid4()
    veh_id = uuid.uuid4()
    art_picked_zero_cat_id = uuid.uuid4()
    art_unpicked_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=f"Sevalor PrefComplet {label} SL",
            nif="B" + emp_id.hex[:8].upper(),
            subdomini=f"prefc-{label.lower()}-{emp_id.hex[:6]}",
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
            node_ia_actiu=True,
        )
    )
    await admin_session.flush()

    for uid, nom_u, rol_u in [
        (boss_id, "Boss", "BOSS"),
        (eng_id, "Enginyer", "ENGINYER"),
        (op_id, "Operari", "OPERARI"),
    ]:
        admin_session.add(
            Usuari(
                id=uid,
                empresa_id=emp_id,
                nif=f"{rol_u[0]}{uid.hex[:7].upper()}P",
                nom=nom_u,
                cognoms=label,
                email=f"{rol_u.lower()}-{emp_id.hex[:6]}@sevalor.test",
                telefon="622333444",
                rol=rol_u,
                pin_hash="fake",
                password_hash="fake",
                estat="ACTIU",
                cost_hora_eur=22.0,
            )
        )

    admin_session.add(
        Client(
            id=cli_id,
            empresa_id=emp_id,
            codi=f"CLI-PC-{emp_id.hex[:5].upper()}",
            rao_social=f"Agrícola {label} S.L.",
            nif="A" + cli_id.hex[:8].upper(),
            adreca_fiscal="Carrer Major 10",
            actiu=True,
        )
    )
    admin_session.add(
        Magatzem(
            id=mag_id,
            empresa_id=emp_id,
            nom=f"Nau {label}",
            tipus="NAU",
            actiu=True,
        )
    )
    admin_session.add(
        Vehicle(
            id=veh_id,
            empresa_id=emp_id,
            matricula=f"{emp_id.hex[:4].upper()}ABC",
            marca="Ford",
            model="Transit",
            estat="ASSIGNAT",
            preu_km_exces_eur=0.60,
            odometre_acumulat=10050,
        )
    )
    admin_session.add_all(
        [
            Article(
                id=art_picked_zero_cat_id,
                empresa_id=emp_id,
                referencia_inventari=f"MAT1-{emp_id.hex[:4].upper()}",
                nom="Electrovàlvula 24V",
                unitat_mesura="UNITAT",
                preu_cost=12.00,
                preu_cost_mitja=12.00,
                pmp_actual=12.00,
                preu_venda=0.00,  # Catàleg a 0 € -> ha de prevaler el preu pactat del Pressupost!
                estoc_total_actual=50.0,
            ),
            Article(
                id=art_unpicked_id,
                empresa_id=emp_id,
                referencia_inventari=f"MAT2-{emp_id.hex[:4].upper()}",
                nom="Colze PE 63mm",
                unitat_mesura="UNITAT",
                preu_cost=5.00,
                preu_cost_mitja=5.00,
                pmp_actual=5.00,
                preu_venda=15.00,
                estoc_total_actual=100.0,
            ),
        ]
    )
    await admin_session.flush()

    admin_session.add_all(
        [
            EstocMagatzem(
                id=uuid.uuid4(),
                empresa_id=emp_id,
                magatzem_id=mag_id,
                article_id=art_picked_zero_cat_id,
                quantitat_fisica=50.0,
                quantitat_virtual_reservada=2.0,
                quantitat_cuarentena=0.0,
            ),
            EstocMagatzem(
                id=uuid.uuid4(),
                empresa_id=emp_id,
                magatzem_id=mag_id,
                article_id=art_unpicked_id,
                quantitat_fisica=100.0,
                quantitat_virtual_reservada=4.0,
                quantitat_cuarentena=0.0,
            ),
        ]
    )
    await admin_session.flush()

    def _hdr(uid: uuid.UUID, rol: str) -> Dict[str, str]:
        tok = create_access_token(str(uid), rol, str(emp_id), timedelta(minutes=30))
        return {"Authorization": f"Bearer {tok}", "X-Empresa-ID": str(emp_id)}

    return {
        "emp_id": emp_id,
        "boss_id": boss_id,
        "eng_id": eng_id,
        "op_id": op_id,
        "cli_id": cli_id,
        "mag_id": mag_id,
        "veh_id": veh_id,
        "art_picked_zero_cat_id": art_picked_zero_cat_id,
        "art_unpicked_id": art_unpicked_id,
        "headers_boss": _hdr(boss_id, "BOSS"),
        "headers_eng": _hdr(eng_id, "ENGINYER"),
    }


@pytest_asyncio.fixture
async def setup_pref_complet(admin_session, tmp_path: Path):
    ta = await _seed_tenant_pref(admin_session, tmp_path / "disc_pc_a", "A")
    tb = await _seed_tenant_pref(admin_session, tmp_path / "disc_pc_b", "B")
    await admin_session.commit()
    return {"a": ta, "b": tb}


@pytest.mark.asyncio
async def test_01_pressupost_a_ot_picking_parcial_i_prefactura_completa_460_eur(
    setup_pref_complet: Dict[str, Any],
    admin_session,
):
    """Verifica que passar-a-prefacturacio importa el 100% dels camps (460.20 €):
    mà d'obra, picking parcial sense perdre línies no picades, preu pactat pressupost,
    materials fora de picking, desplaçament, eines facturables i maquinària.
    """
    ta = setup_pref_complet["a"]
    emp_id = ta["emp_id"]

    pres = Pressupost(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=ta["cli_id"],
        numero=f"PRE-460-{emp_id.hex[:4].upper()}",
        total=460.20,
        estat="APROVAT",
    )
    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=ta["cli_id"],
        cap_de_colla_id=ta["op_id"],
        vehicle_id=ta["veh_id"],
        codi=f"OT-460-{emp_id.hex[:4].upper()}",
        titol="Instal·lació sector reg nord",
        adreca="Finca Nord, Parcel·la 12",
        estat="COMPLERT",
        data_planificacio=date.today(),
        data_finalitzacio_camp=date.today(),
        hora_inici_prevista=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        hora_fi_prevista=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        hores_imputades_facturables=4.0,
        preu_venda_hora_aplicat=45.00,
        km_imputats=40,
        import_pressupostat=460.20,
        import_pressupostat_net=380.33,
    )
    admin_session.add_all([pres, ot])
    await admin_session.flush()

    fp = FullaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        ordre_treball_id=ot.id,
        vehicle_id=ta["veh_id"],
        estat_picking="EN_CURS",
    )
    admin_session.add(fp)
    await admin_session.flush()

    # Picking parcial: 1 línia picada (amb preu_venda=0 al catàleg) i 1 línia sense pick-in (pick_in=0)
    lp_picked = LiniaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        picking_id=fp.id,
        article_id=ta["art_picked_zero_cat_id"],
        magatzem_id=ta["mag_id"],
        quantitat_prevista=2.0,
        quantitat_carregada_pick_in=2.0,
        quantitat_retornada_pick_out=0.0,
        quantitat_mermada=0.0,
        origen_estoc="NAU",
    )
    lp_unpicked = LiniaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        picking_id=fp.id,
        article_id=ta["art_unpicked_id"],
        magatzem_id=ta["mag_id"],
        quantitat_prevista=4.0,
        quantitat_carregada_pick_in=0.0,
        quantitat_retornada_pick_out=0.0,
        quantitat_mermada=0.0,
        origen_estoc="NAU",
    )
    admin_session.add_all([lp_picked, lp_unpicked])
    await admin_session.commit()

    # Desar detalls complets del pressupost vinculat al disc sobirà (total base = 380.33 €, IVA 21% = 79.87 €, total = 460.20 €)
    await desar_detalls_pressupost_disc(
        admin_session,
        emp_id,
        pres,
        {
            "ordre_treball_id": str(ot.id),
            "base_imposable": 380.33,
            "quota_iva": 79.87,
            "descompte_global_pct": 0.0,
            "desplacament_km": 40.0,
            "desplacament_preu_km": 0.50,
            "linies": [
                {
                    "tipus_linia": "MA_OBRA",
                    "seccio": "Mà d'obra i instal·lació",
                    "concepte": "Mà d'obra tècnica especialitzada",
                    "quantitat": 4.0,
                    "preu_unitari": 45.00,
                    "descompte_pct": 0.0,
                    "tipus_iva": 21.0,
                    "subtotal": 180.00,
                },
                {
                    "tipus_linia": "MATERIAL",
                    "article_id": str(ta["art_picked_zero_cat_id"]),
                    "seccio": "Materials i subministraments",
                    "concepte": "Electrovàlvula 24V",
                    "quantitat": 2.0,
                    "preu_unitari": 25.00,
                    "descompte_pct": 0.0,
                    "tipus_iva": 21.0,
                    "subtotal": 50.00,
                },
                {
                    "tipus_linia": "MATERIAL",
                    "article_id": str(ta["art_unpicked_id"]),
                    "seccio": "Materials i subministraments",
                    "concepte": "Colze PE 63mm",
                    "quantitat": 4.0,
                    "preu_unitari": 15.00,
                    "descompte_pct": 0.0,
                    "tipus_iva": 21.0,
                    "subtotal": 60.00,
                },
                {
                    "tipus_linia": "MATERIAL",
                    "seccio": "Materials i subministraments",
                    "concepte": "Junta especial tefló (fora catàleg)",
                    "quantitat": 1.0,
                    "preu_unitari": 30.00,
                    "descompte_pct": 0.0,
                    "tipus_iva": 21.0,
                    "subtotal": 30.00,
                },
                {
                    "tipus_linia": "DESPLACAMENT",
                    "seccio": "Desplaçament i vehicle",
                    "concepte": "Desplaçament Ford Transit",
                    "quantitat": 40.0,
                    "preu_unitari": 0.50,
                    "descompte_pct": 0.0,
                    "tipus_iva": 21.0,
                    "subtotal": 20.00,
                },
                {
                    "tipus_linia": "EINA",
                    "seccio": "Eines i maquinària",
                    "concepte": "Ús d'eina: Soldadora electrofusió",
                    "quantitat": 1.0,
                    "preu_unitari": 25.00,
                    "descompte_pct": 0.0,
                    "tipus_iva": 21.0,
                    "subtotal": 25.00,
                },
                {
                    "tipus_linia": "MAQUINARIA",
                    "seccio": "Desplaçament i vehicle",
                    "concepte": "Ús per hores miniexcavadora",
                    "quantitat": 1.0,
                    "preu_unitari": 15.33,
                    "descompte_pct": 0.0,
                    "tipus_iva": 21.0,
                    "subtotal": 15.33,
                },
            ],
        },
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        # 1. La conciliació previsualitza exactament totes les 7 partides (460.20 €)
        r_conc = await ac.get(f"/gestio/feines/{ot.id}/conciliacio", headers=ta["headers_eng"])
        assert r_conc.status_code == 200, r_conc.text
        c_data = r_conc.json()
        prop = c_data["proposta_prefactura"]
        assert len(prop["linies"]) == 7
        assert prop["base_imposable"] == pytest.approx(380.33, abs=0.02)
        assert prop["liquid_exigible"] == pytest.approx(460.20, abs=0.02)

        # 2. Validar conciliació confirmant 4.0h i 40 km
        r_val = await ac.put(
            f"/gestio/feines/{ot.id}/validar-conciliacio",
            json={
                "hores_imputades_facturables": 4.0,
                "km_imputats": 40,
                "checklist_conciliacio": {
                    "hores_revisades": True,
                    "materials_conciliats": True,
                    "evidencies_comprovades": True,
                    "incidencies_tiquets": True,
                },
            },
            headers=ta["headers_eng"],
        )
        assert r_val.status_code == 200, r_val.text
        assert r_val.json()["proposta_prefactura"]["liquid_exigible"] == pytest.approx(460.20, abs=0.02)

        # 3. Generar Pre-factura -> ha d'importar exactament les 7 partides i 460.20 €!
        r_pref = await ac.post(
            f"/gestio/feines/{ot.id}/passar-a-prefacturacio",
            json={"incloure_tiquets_camp": True},
            headers=ta["headers_eng"],
        )
        assert r_pref.status_code == 201, r_pref.text
        pref = r_pref.json()
        assert len(pref["linies"]) == 7
        assert float(pref["base_imposable"]) == pytest.approx(380.33, abs=0.02)
        assert float(pref["liquid_exigible"]) == pytest.approx(460.20, abs=0.02)


@pytest.mark.asyncio
async def test_02_wip_prefacturar_importa_trams_odometre_picking_parcial_i_tiquets(
    setup_pref_complet: Dict[str, Any],
    admin_session,
):
    """Verifica que /wip-control/{ot_id}/prefacturar importa trams de temps (fallback quan hores=0),
    km derivats d'odòmetre vehicle, picking parcial i tiquets de camp sense pèrdues.
    """
    ta = setup_pref_complet["a"]
    emp_id = ta["emp_id"]

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        client_id=ta["cli_id"],
        cap_de_colla_id=ta["op_id"],
        vehicle_id=ta["veh_id"],
        codi=f"OT-WIP-{emp_id.hex[:4].upper()}",
        titol="Reparació bomba hidràulica",
        adreca="Finca Sud",
        estat="TANCADA",
        data_planificacio=date.today(),
        data_finalitzacio_camp=date.today(),
        hores_imputades_facturables=0.0,  # Fallback a OrdreTreballTramTemps (2h = 7200s)
        preu_venda_hora_aplicat=50.00,
        km_imputats=0,  # Fallback a odòmetre (10050 - 10000 = 50 km * 0.60 = 30.00 €)
    )
    admin_session.add(ot)
    await admin_session.flush()

    now_utc = datetime.now(timezone.utc)
    admin_session.add(
        OrdreTreballTramTemps(
            id=uuid.uuid4(),
            empresa_id=emp_id,
            ordre_treball_id=ot.id,
            operari_id=ta["op_id"],
            hora_inici=now_utc - timedelta(hours=2),
            hora_fi=now_utc,
            durada_segons=7200,
        )
    )
    admin_session.add(
        HistorialAssignacioVehicle(
            id=uuid.uuid4(),
            empresa_id=emp_id,
            vehicle_id=ta["veh_id"],
            conductor_id=ta["op_id"],
            data_inici=now_utc - timedelta(hours=3),
            data_fi=now_utc,
            odometre_inici=10000,
            odometre_fi=10050,
        )
    )
    fp = FullaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        ordre_treball_id=ot.id,
        vehicle_id=ta["veh_id"],
        estat_picking="EN_CURS",
    )
    admin_session.add(fp)
    await admin_session.flush()

    admin_session.add(
        LiniaPicking(
            id=uuid.uuid4(),
            empresa_id=emp_id,
            picking_id=fp.id,
            article_id=ta["art_unpicked_id"],
            magatzem_id=ta["mag_id"],
            quantitat_prevista=3.0,
            quantitat_carregada_pick_in=0.0,
            quantitat_retornada_pick_out=0.0,
            quantitat_mermada=0.0,
            origen_estoc="NAU",
        )
    )
    admin_session.add(
        TiquetDespesa(
            id=uuid.uuid4(),
            empresa_id=emp_id,
            categoria="FERRETERIA",
            usuari_id=ta["op_id"],
            ordre_treball_id=ot.id,
            data_tiquet=date.today(),
            base_imposable=20.00,
            iva_pct=21.0,
            quota_iva=4.20,
            import_total=24.20,
            estat_aprovacio="APROVAT",
            estat_fiscal="PROCESSAT",
            nom_fitxer_visible="tiquet_wip.webp",
            foto_tiquet_path="08_tiquets/tiquet_wip.webp",
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1") as ac:
        r_pref = await ac.post(
            f"/gestio/comptabilitat/wip-control/{ot.id}/prefacturar",
            headers=ta["headers_boss"],
        )
        assert r_pref.status_code == 201, r_pref.text
        pref = r_pref.json()
        # Base = 2h*50 (100) + 3u*15 (45) + 50km*0.60 (30) + tiquet (20) = 195.00; IVA 21% = 40.95; Total = 235.95
        assert float(pref["liquid_exigible"]) == pytest.approx(235.95, abs=0.02)

        # RLS: Tenant B no pot veure la pre-factura del Tenant A
        tb = setup_pref_complet["b"]
        r_rls = await ac.get(
            f"/gestio/comptabilitat/factures/{pref['id']}",
            headers=tb["headers_boss"],
        )
        assert r_rls.status_code == 404
