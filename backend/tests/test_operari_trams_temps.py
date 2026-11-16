"""Tests d'integració reals (PostgreSQL + RLS) per al temporitzador multi-tram GPS de l'operari."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import (
    Client,
    Empresa,
    OrdreTreball,
    OrdreTreballTramTemps,
    Usuari,
)


def _crear_token(usuari_id: uuid.UUID, empresa_id: uuid.UUID, rol: str = "CAP_DE_COLLA") -> str:
    payload = {
        "sub": str(usuari_id),
        "empresa_id": str(empresa_id),
        "rol": rol,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.mark.asyncio
async def test_temporitzador_multi_tram_obrir_tancar_pausa_dinar(admin_session: AsyncSession):
    """Verifica el cicle complet Obrir -> Tancar (dinar) -> Obrir -> Tancar i acumulació d'hores facturables."""
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    client_id = uuid.uuid4()
    ot_id = uuid.uuid4()

    empresa = Empresa(
        id=emp_id,
        nom="Empresa Trams Test",
        nif=f"B{emp_id.hex[:8].upper()}",
        subdomini=f"trams-{emp_id.hex[:6]}",
    )
    admin_session.add(empresa)
    await admin_session.flush()

    operari = Usuari(
        id=op_id,
        empresa_id=emp_id,
        nom="Marc",
        cognoms="Soler",
        nif=f"OP{op_id.hex[:6].upper()}",
        rol="CAP_DE_COLLA",
        pin_hash="dummy",
    )
    admin_session.add(operari)

    client_ent = Client(
        id=client_id,
        empresa_id=emp_id,
        codi=f"CLI-{emp_id.hex[:4]}",
        rao_social="Client Multi-Tram SL",
        nif="B11223344",
    )
    admin_session.add(client_ent)
    await admin_session.flush()

    ot = OrdreTreball(
        id=ot_id,
        empresa_id=emp_id,
        codi=f"OT-{ot_id.hex[:5]}",
        client_id=client_id,
        cap_de_colla_id=op_id,
        titol="Instal·lació reg amb pausa de dinar",
        adreca="41.3851, 2.1734",
        estat="PENDENT",
        preu_venda_hora_aplicat=50.0,
    )
    admin_session.add(ot)
    await admin_session.commit()

    token = _crear_token(op_id, emp_id)
    headers = {"Authorization": f"Bearer {token}", "X-Empresa-ID": str(emp_id)}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        # 1. OBRIR TEMPS (Tram 1 - Matí) amb GPS dins geovalla
        res_open1 = await client.put(
            f"/operari/feines/{ot_id}/comencar",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=headers,
        )
        assert res_open1.status_code == 200, res_open1.text
        d1 = res_open1.json()
        assert d1["estat"] == "EN_CURS"
        assert d1["te_tram_obert"] is True
        assert d1["temps_acumulat_segons"] == 0
        assert len(d1["trams_temps"]) == 1

        # Simular 2 hores treballades al Tram 1
        tram1_id = uuid.UUID(d1["trams_temps"][0]["id"])
        await admin_session.execute(
            text("UPDATE ordres_treball_trams_temps SET hora_inici = now() - interval '2 hours' WHERE id = :tid"),
            {"tid": tram1_id},
        )
        await admin_session.commit()

        # 2. TANCAR TEMPS (Pausa per dinar) amb GPS
        res_close1 = await client.put(
            f"/operari/feines/{ot_id}/finalitzar-temps",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=headers,
        )
        assert res_close1.status_code == 200, res_close1.text
        c1 = res_close1.json()
        assert c1["estat"] == "PAUSADA"
        assert c1["te_tram_obert"] is False
        assert c1["hores_imputades_facturables"] == pytest.approx(2.0, abs=0.05)
        assert len(c1["trams_temps"]) == 1

        # 3. TORNAR A OBRIR TEMPS (Tram 2 - Tarda) sense GPS disponible (fallback resilient)
        res_open2 = await client.put(
            f"/operari/feines/{ot_id}/comencar",
            json={"lat": None, "lng": None},
            headers=headers,
        )
        assert res_open2.status_code == 200, res_open2.text
        d2 = res_open2.json()
        assert d2["estat"] == "EN_CURS"
        assert d2["te_tram_obert"] is True
        assert d2["temps_acumulat_segons"] >= 7190
        assert len(d2["trams_temps"]) == 2

        # Simular 1.5 hores treballades al Tram 2
        tram2_id = uuid.UUID(d2["trams_temps"][1]["id"])
        await admin_session.execute(
            text("UPDATE ordres_treball_trams_temps SET hora_inici = now() - interval '90 minutes' WHERE id = :tid"),
            {"tid": tram2_id},
        )
        await admin_session.commit()

        # 4. TANCAR TEMPS (Fi de feina)
        res_close2 = await client.put(
            f"/operari/feines/{ot_id}/finalitzar-temps",
            json={"lat": 41.3851, "lng": 2.1734},
            headers=headers,
        )
        assert res_close2.status_code == 200, res_close2.text
        c2 = res_close2.json()
        assert c2["estat"] == "PAUSADA"
        assert c2["te_tram_obert"] is False
        assert c2["hores_imputades_facturables"] == pytest.approx(3.5, abs=0.05)
        assert c2["total_facturable_estimat"] == pytest.approx(175.0, abs=2.5)
        assert len(c2["trams_temps"]) == 2

        # 5. Consultar detall de la feina i verificar acumulació persistent
        res_detail = await client.get(f"/operari/feines/{ot_id}", headers=headers)
        assert res_detail.status_code == 200
        det = res_detail.json()
        assert det["te_tram_obert"] is False
        assert det["hores_imputades_facturables"] == pytest.approx(3.5, abs=0.05)
        assert len(det["trams_temps"]) == 2


@pytest.mark.asyncio
async def test_trams_temps_aillament_rls_multi_tenant(admin_session: AsyncSession):
    """Verifica que l'aïllament RLS impedeix que una segona empresa accedeixi als trams d'una altra."""
    emp_a = uuid.uuid4()
    emp_b = uuid.uuid4()
    op_a = uuid.uuid4()
    op_b = uuid.uuid4()
    cli_a = uuid.uuid4()
    ot_a = uuid.uuid4()

    admin_session.add_all([
        Empresa(id=emp_a, nom="Emp A", nif=f"A{emp_a.hex[:8].upper()}", subdomini=f"a-{emp_a.hex[:6]}"),
        Empresa(id=emp_b, nom="Emp B", nif=f"B{emp_b.hex[:8].upper()}", subdomini=f"b-{emp_b.hex[:6]}"),
    ])
    await admin_session.flush()

    admin_session.add_all([
        Usuari(id=op_a, empresa_id=emp_a, nom="Op A", nif=f"NA{op_a.hex[:5].upper()}", rol="OPERARI", pin_hash="x"),
        Usuari(id=op_b, empresa_id=emp_b, nom="Op B", nif=f"NB{op_b.hex[:5].upper()}", rol="OPERARI", pin_hash="x"),
        Client(id=cli_a, empresa_id=emp_a, codi="CA1", rao_social="Cli A", nif="B99001122"),
    ])
    await admin_session.flush()

    admin_session.add(
        OrdreTreball(
            id=ot_a,
            empresa_id=emp_a,
            codi=f"OT-{ot_a.hex[:5]}",
            client_id=cli_a,
            cap_de_colla_id=op_a,
            titol="OT A",
            adreca="41.3851, 2.1734",
            estat="PENDENT",
        )
    )
    await admin_session.commit()

    tok_a = _crear_token(op_a, emp_a, "OPERARI")
    tok_b = _crear_token(op_b, emp_b, "OPERARI")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        res_a = await client.put(
            f"/operari/feines/{ot_a}/comencar",
            json={"lat": 41.3851, "lng": 2.1734},
            headers={"Authorization": f"Bearer {tok_a}", "X-Empresa-ID": str(emp_a)},
        )
        assert res_a.status_code == 200

        # Empresa B intenta obrir/tancar o veure la feina de l'Empresa A -> 404
        res_b = await client.put(
            f"/operari/feines/{ot_a}/comencar",
            json={"lat": 41.3851, "lng": 2.1734},
            headers={"Authorization": f"Bearer {tok_b}", "X-Empresa-ID": str(emp_b)},
        )
        assert res_b.status_code == 404

    # Verificació RLS directa a nivell de sessió PostgreSQL sota rol sevalor_app
    await admin_session.execute(text("SET LOCAL ROLE sevalor_app"))
    await admin_session.execute(
        text("SELECT set_config('app.current_empresa_id', :eid, true)"),
        {"eid": str(emp_b)},
    )
    rows_b = (
        await admin_session.execute(select(OrdreTreballTramTemps))
    ).scalars().all()
    assert len(rows_b) == 0
    await admin_session.execute(text("RESET ROLE"))
