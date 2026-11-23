"""Tests del BLOC 4 — Magatzem, Codi de barres, Estoc Disponible, Picking per magatzem, Recompra HITL i Zero-Storage."""

import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.models import (
    AlbaraProveidor,
    AlertaGarantiaRecompra,
    Article,
    Client,
    Empresa,
    EstocMagatzem,
    FullaPicking,
    LiniaPicking,
    Magatzem,
    MovimentEstoc,
    OrdreTreball,
    Proveidor,
    Usuari,
)
from app.services.sovereign_storage import inicialitzar_arbre_carpetes_disc


def _make_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str) -> str:
    payload: dict[str, Any] = {
        "sub": str(usuari_id),
        "rol": rol,
        "empresa_id": str(empresa_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def _seed_empresa_amb_usuaris(
    admin_session,
    disc_root: Path,
    nom: str = "Empresa Bloc4 S.L.",
):
    inicialitzar_arbre_carpetes_disc(disc_root)
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()

    admin_session.add(
        Empresa(
            id=emp_id,
            nom=nom,
            nif="B" + uuid.uuid4().hex[:8].upper(),
            subdomini="b4-" + uuid.uuid4().hex[:6],
            pla_subscripcio="PRO",
            estat_pagament="ACTIU",
            disc_dur_url=str(disc_root),
        )
    )
    await admin_session.flush()

    admin_session.add(
        Usuari(
            id=boss_id,
            empresa_id=emp_id,
            nif=f"1{boss_id.hex[:7].upper()}A",
            nom="Maria",
            cognoms="Direcció",
            email=f"boss-{emp_id.hex[:6]}@sevalor.test",
            telefon="600111222",
            rol="BOSS",
            pin_hash="fake",
            password_hash="fake",
            estat="ACTIU",
        )
    )
    admin_session.add(
        Usuari(
            id=eng_id,
            empresa_id=emp_id,
            nif=f"2{eng_id.hex[:7].upper()}B",
            nom="Jordi",
            cognoms="Enginyeria",
            email=f"eng-{eng_id.hex[:6]}@sevalor.test",
            telefon="600333444",
            rol="ENGINYER",
            pin_hash="fake",
            password_hash="fake",
            estat="ACTIU",
        )
    )

    nau = Magatzem(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        nom="Nau Central",
        tipus="NAU_CENTRAL",
        actiu=True,
    )
    furgo = Magatzem(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        nom="Furgoneta 01",
        tipus="FURGONETA",
        actiu=True,
    )
    admin_session.add_all([nau, furgo])
    await admin_session.commit()

    boss_headers = {
        "Authorization": f"Bearer {_make_token(boss_id, emp_id, 'BOSS')}",
        "X-Empresa-ID": str(emp_id),
    }
    eng_headers = {
        "Authorization": f"Bearer {_make_token(eng_id, emp_id, 'ENGINYER')}",
        "X-Empresa-ID": str(emp_id),
    }
    return emp_id, nau, furgo, boss_headers, eng_headers


@pytest.mark.asyncio
async def test_bloc4_alta_article_estoc_inicial_codi_barres_sense_qr_i_sync_disc(
    admin_session, tmp_path: Path
):
    """Alta d'article valida codi de barres no-QR, crea estoc_inicial i sincronitza al disc 03_magatzem."""
    disc_root = tmp_path / "disc_b4_art"
    emp_id, nau, _furgo, boss_headers, _eng_headers = await _seed_empresa_amb_usuaris(
        admin_session, disc_root
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Rebutjar QR (FR-007)
        res_qr = await ac.post(
            "/api/v1/gestio/magatzem/articles",
            json={
                "referencia_inventari": "ART-QR-01",
                "codi_barres": "qr:https://example.com/item",
                "nom": "Article invàlid QR",
                "unitat_mesura": "UNITAT",
                "estoc_inicial": 10,
                "magatzem_id": str(nau.id),
            },
            headers=boss_headers,
        )
        assert res_qr.status_code == 422, res_qr.text

        # 2. Alta vàlida amb EAN13 + estoc_inicial = 50 a Nau Central
        res_ok = await ac.post(
            "/api/v1/gestio/magatzem/articles",
            json={
                "referencia_inventari": "TUB-PE100-50",
                "codi_barres": "8412345000012",
                "nom": "Tub PE-100 Ø50mm",
                "unitat_mesura": "METRES_LINEALS",
                "familia": "TUBERIA",
                "estoc_optim": 100.0,
                "estoc_minim": 15.0,
                "preu_cost": 4.5,
                "descompte_proveidor": 10.0,
                "marge_guanys": 25.0,
                "preu_venda": 5.06,
                "estoc_inicial": 50.0,
                "magatzem_id": str(nau.id),
            },
            headers=boss_headers,
        )
        assert res_ok.status_code == 201, res_ok.text
        body = res_ok.json()
        assert body["codi_barres"] == "8412345000012"
        assert body["estoc_fisic"] == 50.0
        assert body["estoc_reservat"] == 0.0
        assert body["estoc_disponible"] == 50.0
        assert body["estoc_real"] == 50.0

    art_id = uuid.UUID(body["id"])
    estoc_db = (
        await admin_session.execute(
            select(EstocMagatzem).where(
                EstocMagatzem.empresa_id == emp_id,
                EstocMagatzem.article_id == art_id,
                EstocMagatzem.magatzem_id == nau.id,
            )
        )
    ).scalars().first()
    assert estoc_db is not None
    assert float(estoc_db.quantitat_fisica) == 50.0

    mov_db = (
        await admin_session.execute(
            select(MovimentEstoc).where(
                MovimentEstoc.empresa_id == emp_id,
                MovimentEstoc.article_id == art_id,
                MovimentEstoc.magatzem_id == nau.id,
            )
        )
    ).scalars().first()
    assert mov_db is not None
    assert mov_db.tipus_moviment == "ENTRADA"
    assert float(mov_db.quantitat) == 50.0

    fitxer_disc = disc_root / "03_magatzem" / "articles_i_estoc" / f"{art_id}.json"
    assert fitxer_disc.exists(), f"Manca JSON sobirà a {fitxer_disc}"
    disc_data = json.loads(fitxer_disc.read_text(encoding="utf-8"))
    assert disc_data["codi_barres"] == "8412345000012"
    assert disc_data["estoc_disponible"] == 50.0


@pytest.mark.asyncio
async def test_bloc4_picking_pick_in_pick_out_per_magatzem_descompta_consum_real_i_hud(
    admin_session, tmp_path: Path
):
    """Picking reserva i descompta el consum real (50 -> 43) al magatzem exacte i actualitza HUD critical_stock."""
    disc_root = tmp_path / "disc_b4_pick"
    emp_id, nau, furgo, boss_headers, _eng_headers = await _seed_empresa_amb_usuaris(
        admin_session, disc_root
    )

    client_id = uuid.uuid4()
    ot_id = uuid.uuid4()
    art_id = uuid.uuid4()
    art_hud_id = uuid.uuid4()

    admin_session.add(
        Client(
            id=client_id,
            empresa_id=emp_id,
            codi="CLI-PICK",
            rao_social="Agrícola Nord S.L.",
            nif="B22334455",
        )
    )
    await admin_session.flush()
    admin_session.add(
        OrdreTreball(
            id=ot_id,
            empresa_id=emp_id,
            codi="OT-B4-001",
            client_id=client_id,
            titol="Sector reg Nord",
            adreca="Finca Sector Nord, Lleida",
            estat="PENDENT",
        )
    )
    admin_session.add_all(
        [
            Article(
                id=art_id,
                empresa_id=emp_id,
                referencia_inventari="VALV-090",
                codi_barres="8400000000901",
                nom="Vàlvula Ø90",
                unitat_mesura="UNITAT",
                estoc_minim=5.0,
                estoc_optim=60.0,
                preu_cost=10.0,
                preu_venda=20.0,
            ),
            Article(
                id=art_hud_id,
                empresa_id=emp_id,
                referencia_inventari="HUD-MIN-10",
                nom="Sensor Crític HUD",
                unitat_mesura="UNITAT",
                estoc_minim=10.0,
                estoc_optim=30.0,
                preu_cost=15.0,
                preu_venda=30.0,
            ),
        ]
    )
    await admin_session.flush()
    admin_session.add_all(
        [
            EstocMagatzem(
                empresa_id=emp_id,
                magatzem_id=nau.id,
                article_id=art_id,
                quantitat_fisica=50.0,
                quantitat_virtual_reservada=0.0,
            ),
            EstocMagatzem(
                empresa_id=emp_id,
                magatzem_id=furgo.id,
                article_id=art_id,
                quantitat_fisica=20.0,
                quantitat_virtual_reservada=0.0,
            ),
            EstocMagatzem(
                empresa_id=emp_id,
                magatzem_id=nau.id,
                article_id=art_hud_id,
                quantitat_fisica=15.0,
                quantitat_virtual_reservada=0.0,
            ),
        ]
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # HUD inicial: 15 disponibles vs mínim 10 -> 0 crítics
        hud_before = await ac.get("/api/v1/gestio/dashboard/hud", headers=boss_headers)
        assert hud_before.status_code == 200, hud_before.text
        assert hud_before.json()["critical_stock"] == 0

        # Crear fulla de picking
        res_fp = await ac.post(
            "/api/v1/gestio/magatzem/picking",
            json={"ordre_treball_id": str(ot_id)},
            headers=boss_headers,
        )
        assert res_fp.status_code == 201, res_fp.text
        picking_id = res_fp.json()["id"]

        # Reservar 10 unitats a Nau Central (50 físics, 20 a Furgoneta intactes)
        res_lin = await ac.post(
            f"/api/v1/gestio/magatzem/picking/{picking_id}/linies",
            json={
                "article_id": str(art_id),
                "magatzem_id": str(nau.id),
                "quantitat_prevista": 10.0,
            },
            headers=boss_headers,
        )
        assert res_lin.status_code == 201, res_lin.text
        lin_body = res_lin.json()
        assert lin_body["magatzem_id"] == str(nau.id)
        linia_id = lin_body["id"]

        # Reservar 6 unitats del sensor HUD (15 físics - 6 reservats = 9 <= 10 mínim!)
        res_hud_lin = await ac.post(
            f"/api/v1/gestio/magatzem/picking/{picking_id}/linies",
            json={
                "article_id": str(art_hud_id),
                "magatzem_id": str(nau.id),
                "quantitat_prevista": 6.0,
            },
            headers=boss_headers,
        )
        assert res_hud_lin.status_code == 201, res_hud_lin.text

        # Verificar que /dashboard/hud detecta critical_stock == 1 per estoc disponible
        hud_after_reserve = await ac.get("/api/v1/gestio/dashboard/hud", headers=boss_headers)
        assert hud_after_reserve.status_code == 200
        assert hud_after_reserve.json()["critical_stock"] == 1

        # Verificar estoc Nau Central vs consolidat després de reservar 10
        res_nau_estoc = await ac.get(
            f"/api/v1/gestio/magatzem/magatzems/{nau.id}/estoc", headers=boss_headers
        )
        assert res_nau_estoc.status_code == 200
        estoc_nau_valv = next(x for x in res_nau_estoc.json() if x["article_id"] == str(art_id))
        assert estoc_nau_valv["quantitat_fisica"] == 50.0
        assert estoc_nau_valv["quantitat_virtual_reservada"] == 10.0
        assert estoc_nau_valv["quantitat_disponible"] == 40.0

        # Pick-in (carregar 10 unitats)
        res_in = await ac.put(
            f"/api/v1/gestio/magatzem/picking/linies/{linia_id}/pick-in", headers=boss_headers
        )
        assert res_in.status_code == 200, res_in.text
        assert res_in.json()["quantitat_carregada_pick_in"] == 10.0

        # Pick-out amb retorn de 3 unitats -> consum real = 7 -> Nau Central passa de 50 a 43!
        res_out = await ac.put(
            f"/api/v1/gestio/magatzem/picking/linies/{linia_id}/pick-out",
            params={"quantitat_retornada": 3.0, "quantitat_mermada": 0.0},
            headers=boss_headers,
        )
        assert res_out.status_code == 200, res_out.text

        res_nau_final = await ac.get(
            f"/api/v1/gestio/magatzem/magatzems/{nau.id}/estoc", headers=boss_headers
        )
        estoc_nau_final = next(x for x in res_nau_final.json() if x["article_id"] == str(art_id))
        assert estoc_nau_final["quantitat_fisica"] == 43.0
        assert estoc_nau_final["quantitat_virtual_reservada"] == 0.0
        assert estoc_nau_final["quantitat_disponible"] == 43.0

        # Furgoneta ha de continuar intacta amb 20.0
        res_furgo_final = await ac.get(
            f"/api/v1/gestio/magatzem/magatzems/{furgo.id}/estoc", headers=boss_headers
        )
        estoc_furgo_final = next(x for x in res_furgo_final.json() if x["article_id"] == str(art_id))
        assert estoc_furgo_final["quantitat_fisica"] == 20.0

    # Verificar columna a023 linies_picking.magatzem_id i MovimentEstoc SORTIDA = 7.0 a PostgreSQL
    linia_db = (
        await admin_session.execute(
            select(LiniaPicking).where(LiniaPicking.id == uuid.UUID(linia_id))
        )
    ).scalars().first()
    assert linia_db is not None
    assert linia_db.magatzem_id == nau.id

    mov_sortida = (
        await admin_session.execute(
            select(MovimentEstoc).where(
                MovimentEstoc.empresa_id == emp_id,
                MovimentEstoc.article_id == art_id,
                MovimentEstoc.magatzem_id == nau.id,
                MovimentEstoc.tipus_moviment == "SORTIDA",
            )
        )
    ).scalars().first()
    assert mov_sortida is not None
    assert float(mov_sortida.quantitat) == 7.0

    # Sync sobirà a 03_magatzem
    picking_json = disc_root / "03_magatzem" / "picking_fulles" / f"{picking_id}.json"
    art_json = disc_root / "03_magatzem" / "articles_i_estoc" / f"{art_id}.json"
    assert picking_json.exists()
    assert art_json.exists()
    assert json.loads(art_json.read_text(encoding="utf-8"))["estoc_disponible"] == 63.0


@pytest.mark.asyncio
async def test_bloc4_enginyer_oculta_costos_i_no_sobreescriu_preu_cost_en_put(
    admin_session, tmp_path: Path
):
    """ENGINYER rep camps de cost emmascarats (None) i no els pot sobreescriure per PUT."""
    disc_root = tmp_path / "disc_b4_eng"
    emp_id, nau, _furgo, boss_headers, eng_headers = await _seed_empresa_amb_usuaris(
        admin_session, disc_root
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_c = await ac.post(
            "/api/v1/gestio/magatzem/articles",
            json={
                "referencia_inventari": "BOMBA-3CV",
                "codi_barres": "8411111222333",
                "nom": "Bomba Submergible 3CV",
                "unitat_mesura": "UNITAT",
                "preu_cost": 420.0,
                "descompte_proveidor": 15.0,
                "marge_guanys": 30.0,
                "preu_venda": 464.1,
                "estoc_inicial": 3.0,
                "magatzem_id": str(nau.id),
            },
            headers=boss_headers,
        )
        assert res_c.status_code == 201, res_c.text
        art_id = res_c.json()["id"]

        # GET com ENGINYER: costos None, preu_venda i estoc_disponible visibles
        res_list_eng = await ac.get("/api/v1/gestio/magatzem/articles", headers=eng_headers)
        assert res_list_eng.status_code == 200
        art_eng = next(x for x in res_list_eng.json() if x["id"] == art_id)
        assert art_eng["preu_cost"] is None
        assert art_eng["pmp_actual"] is None
        assert art_eng["descompte_proveidor"] is None
        assert art_eng["marge_guanys"] is None
        assert art_eng["preu_venda"] == 464.1
        assert art_eng["estoc_disponible"] == 3.0

        # PUT com ENGINYER enviant preu_cost=0 -> no pot destruir el cost real de BD
        res_put_eng = await ac.put(
            f"/api/v1/gestio/magatzem/articles/{art_id}",
            json={
                "referencia_inventari": "BOMBA-3CV",
                "codi_barres": "8411111999888",
                "nom": "Bomba Submergible 3CV Rev2",
                "unitat_mesura": "UNITAT",
                "preu_cost": 0.0,
                "descompte_proveidor": 0.0,
                "marge_guanys": 0.0,
                "preu_venda": 464.1,
            },
            headers=eng_headers,
        )
        assert res_put_eng.status_code == 200, res_put_eng.text
        put_eng_body = res_put_eng.json()
        assert put_eng_body["codi_barres"] == "8411111999888"
        assert put_eng_body["preu_cost"] is None
        assert put_eng_body["pmp_actual"] is None

        # BOSS confirma que el cost i marge originals s'han preservat
        res_list_boss = await ac.get("/api/v1/gestio/magatzem/articles", headers=boss_headers)
        art_boss = next(x for x in res_list_boss.json() if x["id"] == art_id)
        assert art_boss["preu_cost"] == 420.0
        assert art_boss["descompte_proveidor"] == 15.0
        assert art_boss["marge_guanys"] == 30.0
        assert art_boss["codi_barres"] == "8411111999888"


@pytest.mark.asyncio
async def test_bloc4_recompra_stock_hitl_sense_autoenviament_i_veto_enginyer(
    admin_session, tmp_path: Path
):
    """Escaneig genera esborrany RECOMPRA_STOCK HITL sense auto-enviar; només BOSS/SECRETARIA aproven."""
    disc_root = tmp_path / "disc_b4_rec"
    emp_id, nau, _furgo, boss_headers, eng_headers = await _seed_empresa_amb_usuaris(
        admin_session, disc_root
    )

    prov_id = uuid.uuid4()
    admin_session.add(
        Proveidor(
            id=prov_id,
            empresa_id=emp_id,
            codi="PRV-REC",
            rao_social="Subministraments Industrials S.A.",
            nif="A88776655",
            email="comandes@subministraments.test",
            especialitat="MATERIALS",
        )
    )
    await admin_session.flush()

    art_id = uuid.uuid4()
    admin_session.add(
        Article(
            id=art_id,
            empresa_id=emp_id,
            referencia_inventari="ASP-25",
            nom="Aspersor Sectorial 3/4",
            unitat_mesura="UNITAT",
            estoc_minim=15.0,
            estoc_optim=40.0,
            preu_cost=12.0,
            preu_venda=24.0,
            proveidor_id=prov_id,
        )
    )
    await admin_session.flush()
    admin_session.add(
        EstocMagatzem(
            empresa_id=emp_id,
            magatzem_id=nau.id,
            article_id=art_id,
            quantitat_fisica=4.0,
            quantitat_virtual_reservada=0.0,
        )
    )
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_scan = await ac.post("/api/v1/gestio/magatzem/recompra/escanejar", headers=boss_headers)
        assert res_scan.status_code == 201, res_scan.text
        scan_body = res_scan.json()
        assert scan_body["esborranys_generats"] == 1
        alerta = scan_body["alertes"][0]
        assert alerta["estat"] == "ACTIVA"
        assert alerta["enviat_automaticament"] is False
        assert alerta["dades_comanda_proposta"]["enviat_automaticament"] is False
        assert alerta["dades_comanda_proposta"]["requereix_aprovacio_humana"] is True
        assert alerta["dades_comanda_proposta"]["quantitat_proposada"] == 36.0
        alerta_id = alerta["id"]

        # ENGINYER pot veure la safata però amb imports ocults i 403 en intentar aprovar
        res_eng_get = await ac.get("/api/v1/gestio/magatzem/recompra", headers=eng_headers)
        assert res_eng_get.status_code == 200
        eng_alerta = res_eng_get.json()[0]
        assert eng_alerta["dades_comanda_proposta"]["preu_unitari_estimat"] is None
        assert eng_alerta["dades_comanda_proposta"]["import_estimat"] is None

        res_eng_patch = await ac.patch(
            f"/api/v1/gestio/magatzem/recompra/{alerta_id}",
            json={"accio": "APROVAR", "quantitat_aprovada": 36.0},
            headers=eng_headers,
        )
        assert res_eng_patch.status_code == 403

        # BOSS aprova manualment l'esborrany HITL (sense auto-enviament)
        res_boss_patch = await ac.patch(
            f"/api/v1/gestio/magatzem/recompra/{alerta_id}",
            json={"accio": "APROVAR", "quantitat_aprovada": 35.0, "notes": "Validat per BOSS"},
            headers=boss_headers,
        )
        assert res_boss_patch.status_code == 200, res_boss_patch.text
        approved = res_boss_patch.json()
        assert approved["estat"] == "APROVADA"
        assert approved["enviat_automaticament"] is False
        assert approved["dades_comanda_proposta"]["quantitat_aprovada"] == 35.0
        assert approved["dades_comanda_proposta"]["enviat_automaticament"] is False


@pytest.mark.asyncio
async def test_bloc4_albara_confirmar_zero_storage_sense_tmp_data(
    admin_session, tmp_path: Path
):
    """Confirmar albarà OCR usa SovereignStorageGateway (vault://) i mai escriu a /tmp/data."""
    disc_root = tmp_path / "disc_b4_alb"
    emp_id, _nau, _furgo, boss_headers, _eng_headers = await _seed_empresa_amb_usuaris(
        admin_session, disc_root
    )
    tmp_legacy_dir = Path(f"/tmp/data/{emp_id}")
    if tmp_legacy_dir.exists():
        shutil.rmtree(tmp_legacy_dir, ignore_errors=True)

    payload = {
        "proveidor": {
            "nif": "B55443322",
            "nom": "Proveïdor ZeroStorage S.L.",
            "telefon": "930001122",
            "email": "prov@zerostorage.test",
        },
        "numero_document": "ALB-ZS-2026-01",
        "tipus_document": "ALBARA",
        "data_document": "2026-11-17",
        "linies": [
            {
                "referencia": "PE-COLZE-50",
                "nom": "Colze Electrosoldable 50mm",
                "quantitat": 20.0,
                "preu": 8.5,
                "descompte_percent": 10.0,
                "tipus": "MATERIAL",
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/gestio/magatzem/albara/confirmar", json=payload, headers=boss_headers
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["estat"] == "OK"
        assert not str(body["carpeta"]).startswith("/tmp/data"), body["carpeta"]
        assert str(disc_root) in str(body["carpeta"]) or str(body["carpeta"]).startswith("vault://")
        assert "02_proveidors/fitxes" in str(body["carpeta"])

    assert not tmp_legacy_dir.exists(), "/tmp/data no pot existir amb Zero-Storage"
    prov_files = list((disc_root / "02_proveidors" / "fitxes").glob("*.json"))
    alb_files = list((disc_root / "03_magatzem" / "albarans_compra").glob("*.json"))
    art_files = list((disc_root / "03_magatzem" / "articles_i_estoc").glob("*.json"))
    assert len(prov_files) == 1
    assert len(alb_files) == 1
    assert len(art_files) == 1


@pytest.mark.asyncio
async def test_bloc4_aillament_rls_multitenant_magatzem_i_picking(
    admin_session, tmp_path: Path
):
    """Tenant B no pot llegir, modificar ni reservar articles/pickings/alertes de Tenant A."""
    disc_a = tmp_path / "disc_a"
    disc_b = tmp_path / "disc_b"
    emp_a, nau_a, _furgo_a, boss_a, _eng_a = await _seed_empresa_amb_usuaris(
        admin_session, disc_a, nom="Tenant A S.L."
    )
    emp_b, _nau_b, _furgo_b, boss_b, _eng_b = await _seed_empresa_amb_usuaris(
        admin_session, disc_b, nom="Tenant B S.L."
    )

    art_a = Article(
        id=uuid.uuid4(),
        empresa_id=emp_a,
        referencia_inventari="PRIV-A-01",
        codi_barres="8499990000011",
        nom="Article Confidencial A",
        unitat_mesura="UNITAT",
        estoc_minim=10.0,
        preu_cost=50.0,
        preu_venda=90.0,
    )
    client_a = Client(
        id=uuid.uuid4(),
        empresa_id=emp_a,
        codi="CLI-A",
        rao_social="Client Privat A",
        nif="B99988877",
    )
    admin_session.add_all([art_a, client_a])
    await admin_session.flush()

    ot_a = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_a,
        codi="OT-PRIV-A",
        client_id=client_a.id,
        titol="Feina A",
        adreca="Carrer Privat A, 1",
        estat="PENDENT",
    )
    admin_session.add(ot_a)
    await admin_session.flush()

    picking_a = FullaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_a,
        ordre_treball_id=ot_a.id,
        estat_picking="PENDENT",
    )
    alerta_a = AlertaGarantiaRecompra(
        id=uuid.uuid4(),
        empresa_id=emp_a,
        tipus_alerta="RECOMPRA_STOCK",
        article_id=art_a.id,
        missatge="Alerta privada A",
        estat="ACTIVA",
        dades_comanda_proposta={"enviat_automaticament": False},
    )
    estoc_a = EstocMagatzem(
        empresa_id=emp_a,
        magatzem_id=nau_a.id,
        article_id=art_a.id,
        quantitat_fisica=20.0,
        quantitat_virtual_reservada=0.0,
    )
    admin_session.add_all([picking_a, alerta_a, estoc_a])
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_list_b = await ac.get("/api/v1/gestio/magatzem/articles", headers=boss_b)
        assert res_list_b.status_code == 200
        assert all(x["id"] != str(art_a.id) for x in res_list_b.json())

        res_put_b = await ac.put(
            f"/api/v1/gestio/magatzem/articles/{art_a.id}",
            json={
                "referencia_inventari": "HACKED",
                "nom": "Intent Intrús",
                "unitat_mesura": "UNITAT",
            },
            headers=boss_b,
        )
        assert res_put_b.status_code == 404

        res_pick_b = await ac.post(
            f"/api/v1/gestio/magatzem/picking/{picking_a.id}/linies",
            json={"article_id": str(art_a.id), "magatzem_id": str(nau_a.id), "quantitat_prevista": 1.0},
            headers=boss_b,
        )
        assert res_pick_b.status_code == 404

        res_rec_list_b = await ac.get("/api/v1/gestio/magatzem/recompra", headers=boss_b)
        assert res_rec_list_b.status_code == 200
        assert all(x["id"] != str(alerta_a.id) for x in res_rec_list_b.json())

        res_rec_patch_b = await ac.patch(
            f"/api/v1/gestio/magatzem/recompra/{alerta_a.id}",
            json={"accio": "APROVAR"},
            headers=boss_b,
        )
        assert res_rec_patch_b.status_code == 404

        # Tenant A sí que conserva tot intacte
        res_list_a = await ac.get("/api/v1/gestio/magatzem/articles", headers=boss_a)
        assert any(x["id"] == str(art_a.id) for x in res_list_a.json())


@pytest.mark.asyncio
async def test_bloc4_auto_alerta_en_sortida_filtre_trencament_i_resolucio_auto(
    admin_session, tmp_path: Path
):
    """Una sortida sota estoc_minim genera alerta + email draft al moment, HUD/filtre només retornen trencaments i reposar resol l'alerta."""
    emp_id, nau, _, boss_headers, eng_headers = await _seed_empresa_amb_usuaris(
        admin_session, tmp_path / "disc_auto_breach"
    )
    prov = Proveidor(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="PROV-AUTO-01",
        rao_social="Subministraments Lleida S.L.",
        nif="B11223344",
        email="comandes@ferreteria-test.cat",
    )
    admin_session.add(prov)
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_breach = await ac.post(
            "/api/v1/gestio/magatzem/articles",
            json={
                "referencia_inventari": "MAT-BREACH-01",
                "nom": "Tub PE 32mm",
                "unitat_mesura": "METRE",
                "familia": "TUBERIA",
                "estoc_optim": 30.0,
                "estoc_minim": 10.0,
                "estoc_inicial": 12.0,
                "magatzem_id": str(nau.id),
                "preu_cost": 2.5,
                "preu_venda": 5.0,
                "proveidor_id": str(prov.id),
            },
            headers=boss_headers,
        )
        assert r_breach.status_code == 201
        art_breach_id = r_breach.json()["id"]

        r_ok = await ac.post(
            "/api/v1/gestio/magatzem/articles",
            json={
                "referencia_inventari": "MAT-OK-01",
                "nom": "Brida Inox",
                "unitat_mesura": "UNITAT",
                "familia": "ACCESSORIS",
                "estoc_optim": 60.0,
                "estoc_minim": 5.0,
                "estoc_inicial": 50.0,
                "magatzem_id": str(nau.id),
                "preu_cost": 0.4,
                "preu_venda": 1.0,
            },
            headers=boss_headers,
        )
        assert r_ok.status_code == 201

        # Estat inicial sense trencaments
        r_filtre_init = await ac.get(
            "/api/v1/gestio/magatzem/articles?nomes_trencament=true", headers=boss_headers
        )
        assert r_filtre_init.status_code == 200
        assert r_filtre_init.json() == []

        r_hud_init = await ac.get("/api/v1/gestio/dashboard/hud", headers=boss_headers)
        assert r_hud_init.status_code == 200
        assert r_hud_init.json()["critical_stock"] == 0
        assert r_hud_init.json()["critical_stock_items"] == []

        # Sortida de 5 unitats -> stock baixa a 7 <= 10 (trencament automàtic)
        r_sortida = await ac.post(
            f"/api/v1/gestio/magatzem/magatzems/{nau.id}/moviment",
            json={"article_id": art_breach_id, "tipus": "SORTIDA", "quantitat": 5.0},
            headers=boss_headers,
        )
        assert r_sortida.status_code == 200

        # Sense cridar /escanejar, ja existeix l'alerta ACTIVA amb esborrany d'email
        r_rec = await ac.get("/api/v1/gestio/magatzem/recompra?estat=ACTIVA", headers=boss_headers)
        assert r_rec.status_code == 200
        alertes = r_rec.json()
        assert len(alertes) == 1
        assert alertes[0]["article_id"] == art_breach_id
        assert alertes[0]["proveidor_email"] == "comandes@ferreteria-test.cat"
        assert alertes[0]["enviat_automaticament"] is False
        assert "Tub PE 32mm" in (alertes[0]["esborrany_email_assumpte"] or "")
        assert "23" in (alertes[0]["esborrany_email_cos"] or "")
        assert (alertes[0]["mailto_url"] or "").startswith("mailto:comandes@ferreteria-test.cat")

        # El filtre nomes_trencament=true NOMÉS torna l'article en trencament
        r_filtre = await ac.get(
            "/api/v1/gestio/magatzem/articles?nomes_trencament=true", headers=boss_headers
        )
        assert r_filtre.status_code == 200
        filtrats = r_filtre.json()
        assert len(filtrats) == 1
        assert filtrats[0]["id"] == art_breach_id

        # Dashboard HUD reflecteix l'article crític sense exposar costos a ENGINYER
        r_hud_eng = await ac.get("/api/v1/gestio/dashboard/hud", headers=eng_headers)
        assert r_hud_eng.status_code == 200
        hud_eng = r_hud_eng.json()
        assert hud_eng["critical_stock"] == 1
        assert len(hud_eng["critical_stock_items"]) == 1
        assert hud_eng["critical_stock_items"][0]["id"] == art_breach_id
        assert "preu_cost" not in hud_eng["critical_stock_items"][0]

        # Reposició d'estoc -> resol automàticament l'alerta
        r_entrada = await ac.post(
            f"/api/v1/gestio/magatzem/magatzems/{nau.id}/moviment",
            json={"article_id": art_breach_id, "tipus": "ENTRADA", "quantitat": 15.0},
            headers=boss_headers,
        )
        assert r_entrada.status_code == 200

        r_filtre_post = await ac.get(
            "/api/v1/gestio/magatzem/articles?nomes_trencament=true", headers=boss_headers
        )
        assert r_filtre_post.status_code == 200
        assert r_filtre_post.json() == []

        r_resoltes = await ac.get(
            "/api/v1/gestio/magatzem/recompra?estat=RESOLTA_ESTOC", headers=boss_headers
        )
        assert r_resoltes.status_code == 200
        assert len(r_resoltes.json()) == 1


@pytest.mark.asyncio
async def test_bloc4_recompra_agrupada_proveidor_enviar_email_hitl_i_validacio_headers(
    admin_session, tmp_path: Path
):
    """Agrupa trencaments pel mateix proveïdor, aplica veto ENGINYER, blinda injecció CRLF i enregistra HITL MAILTO."""
    disc_root = tmp_path / "disc_email_hitl"
    emp_id, nau, _, boss_headers, eng_headers = await _seed_empresa_amb_usuaris(
        admin_session, disc_root
    )
    prov = Proveidor(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi="PROV-GRP-01",
        rao_social="Electro Subministraments S.A.",
        nif="A88776655",
        email="compres@subministrador.cat",
    )
    admin_session.add(prov)
    await admin_session.flush()

    art1 = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari="GRP-001",
        nom="Magnetotèrmic 16A",
        unitat_mesura="UNITAT",
        familia="QUADRES",
        estoc_optim=20.0,
        estoc_minim=8.0,
        preu_cost=12.0,
        preu_venda=24.0,
        proveidor_id=prov.id,
    )
    art2 = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari="GRP-002",
        nom="Diferencial 40A",
        unitat_mesura="UNITAT",
        familia="QUADRES",
        estoc_optim=10.0,
        estoc_minim=4.0,
        preu_cost=35.0,
        preu_venda=65.0,
        proveidor_id=prov.id,
    )
    admin_session.add_all([art1, art2])
    await admin_session.flush()

    admin_session.add_all([
        EstocMagatzem(
            empresa_id=emp_id,
            magatzem_id=nau.id,
            article_id=art1.id,
            quantitat_fisica=2.0,
            quantitat_virtual_reservada=0.0,
        ),
        EstocMagatzem(
            empresa_id=emp_id,
            magatzem_id=nau.id,
            article_id=art2.id,
            quantitat_fisica=1.0,
            quantitat_virtual_reservada=0.0,
        ),
    ])
    await admin_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_grp_boss = await ac.get(
            "/api/v1/gestio/magatzem/recompra/agrupades-proveidor", headers=boss_headers
        )
        assert r_grp_boss.status_code == 200
        grups = r_grp_boss.json()
        assert len(grups) == 1
        assert grups[0]["total_articles"] == 2
        assert grups[0]["proveidor_email"] == "compres@subministrador.cat"
        assert grups[0]["import_total_estimat"] is not None
        assert "GRP-001" in grups[0]["esborrany_email_cos"]
        assert "GRP-002" in grups[0]["esborrany_email_cos"]

        # Veto Principi VI: ENGINYER no veu import_total_estimat ni pot enviar email
        r_grp_eng = await ac.get(
            "/api/v1/gestio/magatzem/recompra/agrupades-proveidor", headers=eng_headers
        )
        assert r_grp_eng.status_code == 200
        assert r_grp_eng.json()[0]["import_total_estimat"] is None

        payload_email = {
            "alerta_ids": grups[0]["alerta_ids"],
            "proveidor_id": str(prov.id),
            "destinatari_email": "compres@subministrador.cat",
            "assumpte": grups[0]["esborrany_email_assumpte"],
            "cos_missatge": grups[0]["esborrany_email_cos"],
            "canal": "MAILTO",
        }
        r_send_eng = await ac.post(
            "/api/v1/gestio/magatzem/recompra/enviar-email",
            json=payload_email,
            headers=eng_headers,
        )
        assert r_send_eng.status_code == 403

        # Validació anti injecció de capçaleres CRLF
        r_crlf = await ac.post(
            "/api/v1/gestio/magatzem/recompra/enviar-email",
            json={**payload_email, "destinatari_email": "ok@prov.cat\r\nBcc:evil@x.com"},
            headers=boss_headers,
        )
        assert r_crlf.status_code == 422

        # Aprovació i preparació HITL MAILTO pel BOSS
        r_send_boss = await ac.post(
            "/api/v1/gestio/magatzem/recompra/enviar-email",
            json=payload_email,
            headers=boss_headers,
        )
        assert r_send_boss.status_code == 200
        body = r_send_boss.json()
        assert len(body["alertes_aprovades"]) == 2
        assert body["mailto_url"].startswith("mailto:compres@subministrador.cat")

        # Els grups pendents queden nets un cop aprovats
        r_grp_after = await ac.get(
            "/api/v1/gestio/magatzem/recompra/agrupades-proveidor", headers=boss_headers
        )
        assert r_grp_after.status_code == 200
        assert r_grp_after.json() == []

        # Evidència desada al disc sobirà 03_magatzem
        recompra_files = list((disc_root / "03_magatzem").rglob("*recompra_email_*.json"))
        assert len(recompra_files) == 1


@pytest.mark.asyncio
async def test_bloc4_albara_pendent_auditoria_i_consolidacio_estoc(
    admin_session, tmp_path: Path
):
    """FR-009: desar albarà en PENDENT_AUDITORIA no augmenta l'estoc fins que es consolida."""
    _, _, _, boss_headers, _ = await _seed_empresa_amb_usuaris(
        admin_session, tmp_path / "disc_albara_pendent"
    )
    payload_albara = {
        "proveidor": {
            "nif": "B55443322",
            "nom": "Proveïdor Pendent S.L.",
            "email": "facturacio@pendent.cat",
        },
        "numero_document": "ALB-PEND-2026-01",
        "tipus_document": "ALBARA",
        "data_document": "2026-11-18",
        "linies": [
            {
                "referencia": "REF-PEND-001",
                "nom": "Vàlvula Motoritzada DN25",
                "quantitat": 12.0,
                "preu": 42.0,
                "descompte_percent": 0.0,
                "tipus": "MATERIAL",
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_pendent = await ac.post(
            "/api/v1/gestio/magatzem/albarans/desar-pendent",
            json=payload_albara,
            headers=boss_headers,
        )
        assert r_pendent.status_code == 201
        alb_data = r_pendent.json()
        assert alb_data["estat"] == "PENDENT_AUDITORIA"
        albara_id = alb_data["id"]

        # L'article NO s'ha d'haver creat ni sumat a estoc mentre és pendent
        r_arts_abans = await ac.get("/api/v1/gestio/magatzem/articles", headers=boss_headers)
        assert r_arts_abans.status_code == 200
        assert not any(a["referencia_inventari"] == "REF-PEND-001" for a in r_arts_abans.json())

        r_llista_alb = await ac.get(
            "/api/v1/gestio/magatzem/albarans?estat=PENDENT_AUDITORIA", headers=boss_headers
        )
        assert r_llista_alb.status_code == 200
        assert any(a["id"] == albara_id for a in r_llista_alb.json())

        # Consolidació humana: crea article i incrementa estoc
        r_cons = await ac.post(
            f"/api/v1/gestio/magatzem/albarans/{albara_id}/consolidar",
            headers=boss_headers,
        )
        assert r_cons.status_code == 200
        assert r_cons.json()["estat"] == "CONSOLIDAT"

        r_arts_despres = await ac.get("/api/v1/gestio/magatzem/articles", headers=boss_headers)
        creats = [a for a in r_arts_despres.json() if a["referencia_inventari"] == "REF-PEND-001"]
        assert len(creats) == 1
        assert creats[0]["estoc_disponible"] == 12.0

        # Segon intent de consolidació queda rebutjat
        r_cons_dup = await ac.post(
            f"/api/v1/gestio/magatzem/albarans/{albara_id}/consolidar",
            headers=boss_headers,
        )
        assert r_cons_dup.status_code == 400

    alb_db = (
        await admin_session.execute(
            select(AlbaraProveidor).where(AlbaraProveidor.id == uuid.UUID(albara_id))
        )
    ).scalar_one()
    assert alb_db.estat == "CONSOLIDAT"


@pytest.mark.asyncio
async def test_bloc4_material_continu_i_suggeriment_merma(admin_session, tmp_path: Path):
    """FR-008: es_material_continu i suggeriment de % de merma basat en historial."""
    _, nau, _, boss_headers, _ = await _seed_empresa_amb_usuaris(
        admin_session, tmp_path / "disc_merma_cont"
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_art = await ac.post(
            "/api/v1/gestio/magatzem/articles",
            json={
                "referencia_inventari": "CAB-CONT-10",
                "nom": "Cable RZ1-K 3x2.5mm",
                "unitat_mesura": "METRE",
                "familia": "CABLES",
                "es_material_continu": True,
                "estoc_optim": 200.0,
                "estoc_minim": 20.0,
                "estoc_inicial": 100.0,
                "magatzem_id": str(nau.id),
                "preu_cost": 1.2,
                "preu_venda": 2.4,
            },
            headers=boss_headers,
        )
        assert r_art.status_code == 201
        art_data = r_art.json()
        assert art_data["es_material_continu"] is True
        art_id = art_data["id"]

        r_merma = await ac.post(
            "/api/v1/gestio/magatzem/mermes",
            json={
                "article_id": art_id,
                "magatzem_id": str(nau.id),
                "quantitat_mermada": 8.0,
                "motiu": "TRENCAMENT_NAU",
            },
            headers=boss_headers,
        )
        assert r_merma.status_code == 201

        r_sugg = await ac.get(
            f"/api/v1/gestio/magatzem/articles/{art_id}/suggeriment-merma",
            headers=boss_headers,
        )
        assert r_sugg.status_code == 200
        sugg = r_sugg.json()
        assert sugg["es_material_continu"] is True
        assert sugg["merma_suggerida_pct"] > 0
        assert sugg["total_mermes_registrades"] == 1
        assert sugg["quantitat_total_mermada"] == 8.0


@pytest.mark.asyncio
async def test_bloc4_celery_task_comprovar_trencament_estoc():
    """La tasca periòdica comprovar_trencament_estoc detecta trencaments sense alerta i redacta esborranys HITL."""
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.workers.tasks import comprovar_trencament_estoc

    emp_id = uuid.uuid4()
    nau_id = uuid.uuid4()
    art_id = uuid.uuid4()
    engine = create_async_engine(settings.get_database_url(), poolclass=NullPool)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_maker() as session:
            session.add(
                Empresa(
                    id=emp_id,
                    nom="Empresa Celery Stock Test",
                    nif="B" + uuid.uuid4().hex[:8].upper(),
                    subdomini="cel-" + uuid.uuid4().hex[:6],
                    pla_subscripcio="PRO",
                    estat_pagament="ACTIU",
                )
            )
            await session.flush()
            session.add(
                Magatzem(
                    id=nau_id,
                    empresa_id=emp_id,
                    nom="Nau Celery",
                    tipus="NAU_CENTRAL",
                    actiu=True,
                )
            )
            session.add(
                Article(
                    id=art_id,
                    empresa_id=emp_id,
                    referencia_inventari="CEL-BR-01",
                    nom="Sensor Pressió 4-20mA",
                    unitat_mesura="UNITAT",
                    familia="GENERAL",
                    estoc_optim=15.0,
                    estoc_minim=10.0,
                    preu_cost=20.0,
                    preu_venda=45.0,
                )
            )
            await session.flush()
            session.add(
                EstocMagatzem(
                    empresa_id=emp_id,
                    magatzem_id=nau_id,
                    article_id=art_id,
                    quantitat_fisica=3.0,
                    quantitat_virtual_reservada=0.0,
                )
            )
            await session.commit()

        res = comprovar_trencament_estoc(str(emp_id))
        assert isinstance(res, list)
        assert res == [str(art_id)]

        async with session_maker() as session:
            alertes_db = (
                await session.execute(
                    select(AlertaGarantiaRecompra).where(
                        AlertaGarantiaRecompra.empresa_id == emp_id,
                        AlertaGarantiaRecompra.article_id == art_id,
                    )
                )
            ).scalars().all()
            assert len(alertes_db) == 1
            assert alertes_db[0].estat == "ACTIVA"
            assert (alertes_db[0].dades_comanda_proposta or {}).get("enviat_automaticament") is False
    finally:
        async with session_maker() as session:
            await session.execute(delete(Empresa).where(Empresa.id == emp_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_bloc4_revisar_pendent_via_confirmar_i_antiduplicat_stock(
    admin_session, tmp_path: Path
):
    """
    1. Si un albarà és PENDENT_AUDITORIA i es revisa/confirma via /albara/confirmar (amb o sense albara_id),
       actualitza el registre existent a CONSOLIDAT sense deixar cap PENDENT_AUDITORIA ni duplicar estoc.
    2. Si un albarà PENDENT_AUDITORIA ja tenia MovimentEstoc d'ENTRADA aplicat al magatzem, consolidar-lo
       actualitza l'estat a CONSOLIDAT sense incrementar ni duplicar l'estoc.
    """
    emp_id, nau, _, boss_headers, _ = await _seed_empresa_amb_usuaris(
        admin_session, tmp_path / "disc_alb_dup"
    )
    payload_pend = {
        "proveidor": {
            "nif": "B77889900",
            "nom": "Hidràulica Segrià S.L.",
            "email": "alb@segria.cat",
        },
        "numero_document": "ALB-REV-2026-01",
        "tipus_document": "ALBARA",
        "data_document": "2026-11-20",
        "linies": [
            {
                "referencia": "REF-NODUP-01",
                "nom": "Comptador Woltman DN50",
                "quantitat": 5.0,
                "preu": 120.0,
                "descompte_percent": 0.0,
                "tipus": "MATERIAL",
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Desem com a PENDENT_AUDITORIA
        r_pend = await ac.post(
            "/api/v1/gestio/magatzem/albarans/desar-pendent",
            json=payload_pend,
            headers=boss_headers,
        )
        assert r_pend.status_code == 201, r_pend.text
        alb_id = r_pend.json()["id"]

        # 2. Revisar-lo/confirmar-lo directament via /albara/confirmar passant albara_id -> passa a CONSOLIDAT
        r_conf = await ac.post(
            "/api/v1/gestio/magatzem/albara/confirmar",
            json={
                **payload_pend,
                "albara_id": alb_id,
                "linies": [
                    {
                        **payload_pend["linies"][0],
                        "quantitat": 6.0,
                    }
                ],
            },
            headers=boss_headers,
        )
        assert r_conf.status_code == 201, r_conf.text
        assert r_conf.json()["albara_id"] == alb_id

        # No ha de quedar cap PENDENT_AUDITORIA i l'estoc ha de ser exactament 6.0 (mai 12.0)
        r_pend_list = await ac.get(
            "/api/v1/gestio/magatzem/albarans?estat=PENDENT_AUDITORIA", headers=boss_headers
        )
        assert r_pend_list.status_code == 200
        assert not any(a["id"] == alb_id for a in r_pend_list.json())

        r_arts = await ac.get("/api/v1/gestio/magatzem/articles", headers=boss_headers)
        art = next(a for a in r_arts.json() if a["referencia_inventari"] == "REF-NODUP-01")
        assert art["estoc_fisic"] == 6.0

        # Intentar consolidar o tornar a confirmar després -> 400 sense duplicar
        r_cons_dup = await ac.post(
            f"/api/v1/gestio/magatzem/albarans/{alb_id}/consolidar", headers=boss_headers
        )
        assert r_cons_dup.status_code == 400

        # 3. Cas llegat: un albarà PENDENT_AUDITORIA que ja té MovimentEstoc d'ENTRADA aplicat
        prov_id = uuid.UUID(r_pend.json()["proveidor_id"])
        alb_legacy = AlbaraProveidor(
            empresa_id=emp_id,
            proveidor_id=prov_id,
            numero_albara="ALB-LEGACY-99",
            data_albara=date(2026, 11, 10),
            estat="PENDENT_AUDITORIA",
        )
        admin_session.add(alb_legacy)
        admin_session.add(
            MovimentEstoc(
                empresa_id=emp_id,
                magatzem_id=nau.id,
                article_id=uuid.UUID(art["id"]),
                tipus_moviment="ENTRADA",
                quantitat=4.0,
                referencia_document="ALB-LEGACY-99",
                notes="Albarà Proveïdor OCR",
            )
        )
        await admin_session.flush()

        # Llistat indica ja_te_stock_aplicat=True
        r_list_all = await ac.get("/api/v1/gestio/magatzem/albarans", headers=boss_headers)
        legacy_row = next(a for a in r_list_all.json() if a["id"] == str(alb_legacy.id))
        assert legacy_row["estat"] == "PENDENT_AUDITORIA"
        assert legacy_row["ja_te_stock_aplicat"] is True

        # En consolidar, passa a CONSOLIDAT sense tornar a sumar estoc
        r_cons_leg = await ac.post(
            f"/api/v1/gestio/magatzem/albarans/{alb_legacy.id}/consolidar",
            headers=boss_headers,
        )
        assert r_cons_leg.status_code == 200, r_cons_leg.text
        d_leg = r_cons_leg.json()
        assert d_leg["estat"] == "CONSOLIDAT"
        assert d_leg["stock_duplicat_evitat"] is True
        assert d_leg["moviments_realitzats"] == 0

        r_arts_after = await ac.get("/api/v1/gestio/magatzem/articles", headers=boss_headers)
        art_after = next(a for a in r_arts_after.json() if a["referencia_inventari"] == "REF-NODUP-01")
        assert art_after["estoc_fisic"] == 6.0


@pytest.mark.asyncio
async def test_bloc4_albara_aplica_marge_automatic_si_coincideix_proveidor_i_referencia(
    admin_session, tmp_path: Path
):
    """
    Si en entrar un nou albarà coincideixen proveïdor (proveidor_id) i referència del producte,
    s'aplica automàticament el marge_guanys de l'article per recalcular preu_venda.
    Si el proveïdor és diferent, NO sobreescriu el preu_venda.
    """
    emp_id, nau, _, boss_headers, _ = await _seed_empresa_amb_usuaris(
        admin_session, tmp_path / "disc_alb_marge"
    )
    prov_a = Proveidor(
        empresa_id=emp_id,
        codi="PRV-MRG-A",
        rao_social="Proveïdor Marge A S.L.",
        nif="B11223399",
    )
    prov_b = Proveidor(
        empresa_id=emp_id,
        codi="PRV-MRG-B",
        rao_social="Proveïdor Alien B S.L.",
        nif="B99887711",
    )
    admin_session.add_all([prov_a, prov_b])
    await admin_session.flush()

    art_match = Article(
        empresa_id=emp_id,
        referencia_inventari="REF-MARGE-01",
        nom="Electrovalvula 2 polzades",
        unitat_mesura="UNITAT",
        familia="REG",
        proveidor_id=prov_a.id,
        estoc_optim=20.0,
        estoc_minim=2.0,
        preu_cost=100.0,
        marge_guanys=30.0,
        preu_venda=130.0,
    )
    art_altre_prov = Article(
        empresa_id=emp_id,
        referencia_inventari="REF-MARGE-ALTRE",
        nom="Tub PE100 DN63",
        unitat_mesura="METRE",
        familia="TUBERIA",
        proveidor_id=prov_b.id,
        estoc_optim=50.0,
        estoc_minim=5.0,
        preu_cost=10.0,
        marge_guanys=40.0,
        preu_venda=14.0,
    )
    admin_session.add_all([art_match, art_altre_prov])
    await admin_session.flush()

    # Estoc previ = 10 unitats a 100 EUR -> valor = 1000 EUR
    admin_session.add(
        EstocMagatzem(
            empresa_id=emp_id,
            magatzem_id=nau.id,
            article_id=art_match.id,
            quantitat_fisica=10.0,
            quantitat_virtual_reservada=0.0,
        )
    )
    await admin_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Entrem nou albarà de Proveïdor A amb 10 unitats de REF-MARGE-01 a 120 EUR (descompte 0%)
        # PMP nou = (10*100 + 10*120) / 20 = 110.00 EUR -> PVP amb marge 30% = 110 * 1.30 = 143.00 EUR
        # I una línia per REF-MARGE-ALTRE (que pertany a Proveïdor B): NO ha de tocar el preu_venda 14.0
        r_conf = await ac.post(
            "/api/v1/gestio/magatzem/albara/confirmar",
            json={
                "proveidor": {
                    "nif": "B11223399",
                    "nom": "Proveïdor Marge A S.L.",
                },
                "numero_document": "ALB-MRG-2026-01",
                "tipus_document": "ALBARA",
                "data_document": "2026-11-23",
                "linies": [
                    {
                        "referencia": "REF-MARGE-01",
                        "nom": "Electrovalvula 2 polzades",
                        "quantitat": 10.0,
                        "preu": 120.0,
                        "descompte_percent": 0.0,
                        "tipus": "MATERIAL",
                    },
                    {
                        "referencia": "REF-MARGE-ALTRE",
                        "nom": "Tub PE100 DN63",
                        "quantitat": 10.0,
                        "preu": 20.0,
                        "descompte_percent": 0.0,
                        "tipus": "MATERIAL",
                    },
                ],
            },
            headers=boss_headers,
        )
        assert r_conf.status_code == 201, r_conf.text

        r_arts = await ac.get("/api/v1/gestio/magatzem/articles", headers=boss_headers)
        assert r_arts.status_code == 200
        arts_by_ref = {a["referencia_inventari"]: a for a in r_arts.json()}

        assert arts_by_ref["REF-MARGE-01"]["preu_cost"] == pytest.approx(110.0)
        assert arts_by_ref["REF-MARGE-01"]["marge_guanys"] == pytest.approx(30.0)
        assert arts_by_ref["REF-MARGE-01"]["preu_venda"] == pytest.approx(143.0)

        # Proveïdor no coincident: conserva el PVP original 14.0
        assert arts_by_ref["REF-MARGE-ALTRE"]["preu_venda"] == pytest.approx(14.0)
