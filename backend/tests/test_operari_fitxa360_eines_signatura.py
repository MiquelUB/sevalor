import base64
import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.models import (
    Article,
    Client,
    EinaCustodia,
    Empresa,
    EstocMagatzem,
    FullaPicking,
    Incidencia,
    LiniaPicking,
    Magatzem,
    OrdreTreball,
    OrdreTreballOperari,
    Usuari,
    Vehicle,
)

# 1x1 PNG real (Magic Bytes vàlids per validar desar_signatura_client_ot sense mocks)
VALID_PNG_1X1_B64 = (
    "data:image/png;base64,"
    + base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode("ascii")
)


def _crear_token(usuari_id: str, empresa_id: str, rol: str = "OPERARI") -> str:
    payload = {
        "sub": usuari_id,
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def _seed_tenant_fitxa360(admin_session, tag: str):
    uid = str(uuid.uuid4())[:8]
    emp_id = uuid.uuid4()
    cap_id = uuid.uuid4()
    ajudant_id = uuid.uuid4()

    empresa = Empresa(
        id=emp_id,
        nom=f"Empresa {tag} {uid}",
        nif=f"B{uid.upper()}",
        subdomini=f"f360-{tag}-{uid}",
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    cap = Usuari(
        id=cap_id,
        empresa_id=emp_id,
        nif=f"1{uid}C",
        nom="Cap Colla",
        rol="CAP_DE_COLLA",
        pin_hash="dummy_hash",
    )
    ajudant = Usuari(
        id=ajudant_id,
        empresa_id=emp_id,
        nif=f"2{uid}A",
        nom="Ajudant Camp",
        rol="OPERARI",
        pin_hash="dummy_hash",
    )
    admin_session.add_all([cap, ajudant])
    await admin_session.flush()

    veh_a = Vehicle(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        matricula=f"1111{uid[:3].upper()}",
        marca="Ford",
        model="Transit Custom",
        estat="OPERATIU",
        conductor_habitual_id=cap_id,
    )
    veh_b = Vehicle(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        matricula=f"2222{uid[:3].upper()}",
        marca="Renault",
        model="Master",
        estat="OPERATIU",
    )
    admin_session.add_all([veh_a, veh_b])
    await admin_session.flush()

    mag_van_b = Magatzem(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        nom=f"Furgoneta Master {uid}",
        tipus="FURGONETA",
        vehicle_id=veh_b.id,
    )
    mag_van_a = Magatzem(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        nom=f"Furgoneta Transit {uid}",
        tipus="FURGONETA",
        vehicle_id=veh_a.id,
    )
    admin_session.add_all([mag_van_a, mag_van_b])
    await admin_session.flush()

    art_mat = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari=f"MAT-{uid}",
        nom="Vàlvula motoritzada 2 polzades",
        unitat_mesura="UNITAT",
        familia="REG",
    )
    art_van = Article(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        referencia_inventari=f"VAN-{uid}",
        nom="Brida inoxidable DN50",
        unitat_mesura="UNITAT",
        familia="ACCESSORIS",
    )
    admin_session.add_all([art_mat, art_van])
    await admin_session.flush()

    admin_session.add_all(
        [
            EstocMagatzem(
                empresa_id=emp_id,
                magatzem_id=mag_van_b.id,
                article_id=art_van.id,
                quantitat_fisica=12.0,
                quantitat_virtual_reservada=0.0,
            ),
            EstocMagatzem(
                empresa_id=emp_id,
                magatzem_id=mag_van_a.id,
                article_id=art_mat.id,
                quantitat_fisica=5.0,
                quantitat_virtual_reservada=0.0,
            ),
        ]
    )
    await admin_session.flush()

    client = Client(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi=f"CLI-{uid}",
        rao_social=f"Agrícola {tag}",
        nif=f"J{uid.upper()}",
    )
    admin_session.add(client)
    await admin_session.flush()

    ot = OrdreTreball(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        codi=f"OT-{uid}",
        client_id=client.id,
        vehicle_id=veh_b.id,
        cap_de_colla_id=cap_id,
        titol="Reparació estació de bombament",
        estat="ASSIGNADA",
        adreca="Camí de l'Aigua s/n",
        data_planificacio=date.today(),
    )
    admin_session.add(ot)
    await admin_session.flush()

    admin_session.add_all(
        [
            OrdreTreballOperari(
                empresa_id=emp_id,
                ordre_treball_id=ot.id,
                operari_id=cap_id,
                es_cap_de_colla=True,
            ),
            OrdreTreballOperari(
                empresa_id=emp_id,
                ordre_treball_id=ot.id,
                operari_id=ajudant_id,
                es_cap_de_colla=False,
            ),
        ]
    )

    picking = FullaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        ordre_treball_id=ot.id,
        vehicle_id=veh_b.id,
        estat_picking="PENDENT",
    )
    admin_session.add(picking)
    await admin_session.flush()

    linia = LiniaPicking(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        picking_id=picking.id,
        article_id=art_mat.id,
        quantitat_prevista=4.0,
        quantitat_carregada_pick_in=2.0,
        quantitat_retornada_pick_out=0.0,
        quantitat_mermada=0.0,
    )
    admin_session.add(linia)

    eina_ot = EinaCustodia(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        nom="Trepant Percutor Hilti TE-30",
        model="TE-30-ATC",
        numero_serie=f"SN-OT-{uid}",
        estat="CUSTODIADA",
        custodiat_per_operari_id=cap_id,
        ordre_treball_id=ot.id,
    )
    eina_disp = EinaCustodia(
        id=uuid.uuid4(),
        empresa_id=emp_id,
        nom="Soldadora Electrofusió",
        model="EF-400",
        numero_serie=f"SN-DISP-{uid}",
        estat="DISPONIBLE",
    )
    admin_session.add_all([eina_ot, eina_disp])
    await admin_session.flush()

    return {
        "empresa_id": str(emp_id),
        "cap_id": str(cap_id),
        "ajudant_id": str(ajudant_id),
        "ot_id": str(ot.id),
        "veh_a_id": str(veh_a.id),
        "veh_b_id": str(veh_b.id),
        "mag_van_b_id": str(mag_van_b.id),
        "eina_ot_id": str(eina_ot.id),
        "eina_disp_id": str(eina_disp.id),
        "art_van_ref": art_van.referencia_inventari,
    }


@pytest.mark.asyncio
async def test_fitxa360_vehicle_eines_signatura_i_trajecte(admin_session):
    """Valida Fitxa 360 completa: eines visibles per la colla, trajecte persistent, signatura inline i picking furgoneta."""
    s = await _seed_tenant_fitxa360(admin_session, "t1")
    token_ajudant = _crear_token(s["ajudant_id"], s["empresa_id"], rol="OPERARI")
    headers = {
        "Authorization": f"Bearer {token_ajudant}",
        "X-Empresa-ID": s["empresa_id"],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Fitxa 360 oberta per l'ajudant (no cap_de_colla) veu vehicle, picking i eines de l'OT
        res_detall = await ac.get(f"/api/v1/operari/feines/{s['ot_id']}", headers=headers)
        assert res_detall.status_code == 200
        d = res_detall.json()
        assert d["vehicle"]["id"] == s["veh_b_id"]
        assert d["vehicle"]["marca"] == "Renault"
        assert len(d["linies_picking"]) == 1
        assert d["linies_picking"][0]["unitat_mesura"] == "UNITAT"
        assert len(d["eines_assignades"]) == 1
        assert d["eines_assignades"][0]["id"] == s["eina_ot_id"]
        assert d["signatura_client_path"] is None

        # 2. Iniciar trajecte persisteix EN_RUTA a l'OT
        res_ruta = await ac.put(
            f"/api/v1/operari/feines/{s['ot_id']}/iniciar-trajecte",
            headers=headers,
        )
        assert res_ruta.status_code == 200
        assert res_ruta.json()["estat_vehicle"] == "EN_TRANSIT"

        res_detall_ruta = await ac.get(f"/api/v1/operari/feines/{s['ot_id']}", headers=headers)
        assert res_detall_ruta.status_code == 200
        assert res_detall_ruta.json()["estat"] == "EN_RUTA"

        # 3. Vehicle link (/operari/vehicles i /stock) filtra i prioritza el vehicle de l'OT (veh_b)
        res_vehs = await ac.get(
            f"/api/v1/operari/vehicles?vehicle_id={s['veh_b_id']}&ordre_treball_id={s['ot_id']}",
            headers=headers,
        )
        assert res_vehs.status_code == 200
        vehs = res_vehs.json()
        assert len(vehs) >= 2
        assert vehs[0]["id"] == s["veh_b_id"]

        res_stock = await ac.get(
            f"/api/v1/operari/vehicles/stock?vehicle_id={s['veh_b_id']}&ordre_treball_id={s['ot_id']}",
            headers=headers,
        )
        assert res_stock.status_code == 200
        stock_items = res_stock.json()
        assert len(stock_items) == 1
        assert stock_items[0]["referencia"] == s["art_van_ref"]

        # 4. Box 6: Signatura de conformitat inline del client (funciona abans de completar les 3 fotos QA)
        res_sig = await ac.put(
            f"/api/v1/operari/feines/{s['ot_id']}/signatura",
            json={
                "signatura_base64": VALID_PNG_1X1_B64,
                "nom_receptor": "Pere Soler",
                "dni_receptor": "12345678a",
                "observacions": "Instal·lació comprovada en presència del client.",
            },
            headers=headers,
        )
        assert res_sig.status_code == 200
        sig_data = res_sig.json()
        assert sig_data["signatura_client_path"]
        assert sig_data["nom_receptor"] == "Pere Soler"
        assert sig_data["dni_receptor"] == "12345678A"
        assert sig_data["data_signatura"] is not None

        # Verificar que GET detall retorna la signatura desada
        res_after = await ac.get(f"/api/v1/operari/feines/{s['ot_id']}", headers=headers)
        assert res_after.status_code == 200
        after_d = res_after.json()
        assert after_d["signatura_client_path"] == sig_data["signatura_client_path"]
        assert after_d["nom_receptor"] == "Pere Soler"
        assert after_d["dni_receptor"] == "12345678A"


@pytest.mark.asyncio
async def test_eines_pick_in_pick_out_i_rls(admin_session):
    """Valida Pick-In (operari/furgoneta), Pick-Out (OK i Avaria amb incidència) i aïllament RLS entre tenants."""
    s1 = await _seed_tenant_fitxa360(admin_session, "tenA")
    s2 = await _seed_tenant_fitxa360(admin_session, "tenB")

    headers_a = {
        "Authorization": f"Bearer {_crear_token(s1['cap_id'], s1['empresa_id'], rol='CAP_DE_COLLA')}",
        "X-Empresa-ID": s1["empresa_id"],
    }
    headers_b = {
        "Authorization": f"Bearer {_crear_token(s2['cap_id'], s2['empresa_id'], rol='CAP_DE_COLLA')}",
        "X-Empresa-ID": s2["empresa_id"],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Llistar eines per OT (1 assignada + 1 disponible)
        res_list = await ac.get(
            f"/api/v1/operari/picking/eines?ordre_treball_id={s1['ot_id']}",
            headers=headers_a,
        )
        assert res_list.status_code == 200
        data_list = res_list.json()
        assert [e["id"] for e in data_list["eines_assignades"]] == [s1["eina_ot_id"]]
        assert [e["id"] for e in data_list["eines_disponibles"]] == [s1["eina_disp_id"]]

        # 2. Pick-In d'eina disponible cap a la furgoneta de l'OT
        res_pin = await ac.post(
            f"/api/v1/operari/picking/eines/{s1['eina_disp_id']}/pick-in",
            json={
                "ordre_treball_id": s1["ot_id"],
                "desti": "EN_VEHICLE",
                "observacions": "Carregada al maleter lateral",
            },
            headers=headers_a,
        )
        assert res_pin.status_code == 200
        pin_d = res_pin.json()
        assert pin_d["estat"] == "EN_VEHICLE"
        assert pin_d["ordre_treball_id"] == s1["ot_id"]
        assert pin_d["magatzem_id"] == s1["mag_van_b_id"]

        # 3. Pick-Out OK de l'eina carregada -> torna a DISPONIBLE i neteja OT/operari
        res_pout_ok = await ac.post(
            f"/api/v1/operari/picking/eines/{s1['eina_disp_id']}/pick-out",
            json={"ordre_treball_id": s1["ot_id"], "estat_retorn": "DISPONIBLE"},
            headers=headers_a,
        )
        assert res_pout_ok.status_code == 200
        pout_ok = res_pout_ok.json()
        assert pout_ok["estat"] == "DISPONIBLE"
        assert pout_ok["ordre_treball_id"] is None
        assert pout_ok["custodiat_per_operari_id"] is None

        # 4. Pick-Out amb AVARIA de l'eina original de l'OT -> AVARIADA + Incidencia a BD
        res_pout_av = await ac.post(
            f"/api/v1/operari/picking/eines/{s1['eina_ot_id']}/pick-out",
            json={
                "ordre_treball_id": s1["ot_id"],
                "estat_retorn": "AVARIADA",
                "incidencia": "Portabroques bloquejat després de perforació",
            },
            headers=headers_a,
        )
        assert res_pout_av.status_code == 200
        pout_av = res_pout_av.json()
        assert pout_av["estat"] == "AVARIADA"
        assert "Portabroques bloquejat" in (pout_av["incidencies"] or "")

        inc_res = await admin_session.execute(
            select(Incidencia).where(
                Incidencia.empresa_id == uuid.UUID(s1["empresa_id"]),
                Incidencia.ordre_treball_id == uuid.UUID(s1["ot_id"]),
                Incidencia.ambit == "MAGATZEM",
            )
        )
        inc = inc_res.scalars().first()
        assert inc is not None
        assert "Portabroques bloquejat" in (inc.text_observacions or "")

        # 5. Aïllament RLS estricte: Tenant B NO pot tocar eines ni signar l'OT del Tenant A
        res_rls_pin = await ac.post(
            f"/api/v1/operari/picking/eines/{s1['eina_disp_id']}/pick-in",
            json={"ordre_treball_id": s2["ot_id"], "desti": "CUSTODIADA"},
            headers=headers_b,
        )
        assert res_rls_pin.status_code == 404

        res_rls_sig = await ac.put(
            f"/api/v1/operari/feines/{s1['ot_id']}/signatura",
            json={"signatura_base64": VALID_PNG_1X1_B64, "nom_receptor": "Intrus"},
            headers=headers_b,
        )
        assert res_rls_sig.status_code == 404
