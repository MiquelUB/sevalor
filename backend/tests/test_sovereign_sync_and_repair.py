"""Tests d'integració Zero Mock: Reconciliació Sobirana, Auto-Reparació i Filtratge de Flota.

Valida contra PostgreSQL real + Túnel WSS real (`live_empresa_wss_context`):
1. Reconciliació completa (`sincronitzar_entitats_empresa_al_disc`) per a vehicles, operaris
   (sense exposar `password_hash`, `pin_hash` ni `secret_2fa`), clients, finques, articles+estoc,
   eines, OTs i pressupostos.
2. Aïllament estricte multi-tenant (Tenant A mai escriu ni veu registres del Tenant B).
3. Auto-reparació en calent (`BaseSubagent.read_sovereign_category`) quan una carpeta del disc
   sobirà és buida però existeixen registres reals a PostgreSQL: escriu al disc via WSS i el
   subagent llegeix les fitxes verificades amb HMAC.
4. Filtratge estricte de `08_flota_i_operaris/vehicles/` davant fitxers auxiliars (`doc_*`,
   `manteniment_*`, `operari_*`) + `sincronitzar_operari_al_disc_empresa` només escriu a `operaris`.
5. Control RBAC a `POST /api/v1/gestio/copilot/sincronitzar-disc` (BOSS 200 vs ENGINYER 403).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.models import (
    Article,
    Client,
    EinaCustodia,
    Empresa,
    EstocMagatzem,
    Finca,
    Magatzem,
    MantenimentVehicle,
    OrdreTreball,
    Pressupost,
    Usuari,
    Vehicle,
)
from app.services.flota_service import sincronitzar_operari_al_disc_empresa
from app.services.sovereign_storage import SovereignStorageGateway
from app.services.sovereign_sync_service import (
    reset_read_repair_state,
    sincronitzar_entitats_empresa_al_disc,
)
from app.services.subagents.subagent_flota_despatx import SubagentFlotaDespatx
from app.services.subagents.subagent_general_rag import SubagentGeneralRag
from app.services.subagents.subagent_logistica_estoc import SubagentLogisticaEstoc
from tests.wss_test_helpers import live_empresa_wss_context


def _make_empresa(emp_id: uuid.UUID, tag: str, vault_token: str) -> Empresa:
    return Empresa(
        id=emp_id,
        nom=f"Empresa Sync {tag}",
        nif="B" + uuid.uuid4().hex[:8].upper(),
        subdomini=f"sync-{tag.lower()}-{uuid.uuid4().hex[:6]}",
        pla_subscripcio="PRO",
        estat_pagament="ACTIU",
        disc_dur_url=f"wss-tunnel://{emp_id}",
        node_ia_url=f"wss-tunnel://{emp_id}",
        vault_token=vault_token,
        node_ia_actiu=True,
        feature_copilot_ia=True,
    )


@pytest.mark.asyncio
async def test_sync_reconciler_multi_tenant_and_zero_secret_leak(admin_session, tmp_path: Path):
    """Sincronitza totes les entitats del Tenant A al seu disc WSS sense filtrar secrets ni barrejar Tenant B."""
    reset_read_repair_state()
    emp_a = uuid.uuid4()
    emp_b = uuid.uuid4()
    boss_a = uuid.uuid4()
    op_a = uuid.uuid4()
    cli_a = uuid.uuid4()
    cli_b = uuid.uuid4()
    finca_a = uuid.uuid4()
    mag_a = uuid.uuid4()
    art_a = uuid.uuid4()
    eina_a = uuid.uuid4()
    veh_a = uuid.uuid4()
    veh_b = uuid.uuid4()
    ot_a = uuid.uuid4()
    pres_a = uuid.uuid4()

    # 1. Empreses primer (FK pare)
    vault_tok_a = f"svlt_sync_a_{uuid.uuid4().hex[:12]}"
    vault_tok_b = f"svlt_sync_b_{uuid.uuid4().hex[:12]}"
    admin_session.add_all(
        [_make_empresa(emp_a, "A", vault_tok_a), _make_empresa(emp_b, "B", vault_tok_b)]
    )
    await admin_session.flush()

    # 2. Entitats base (Usuaris, Clients, Magatzems, Articles)
    admin_session.add_all(
        [
            Usuari(
                id=boss_a,
                empresa_id=emp_a,
                nif=f"11{uuid.uuid4().hex[:6].upper()}A",
                nom="Joan",
                cognoms="Director",
                email=f"boss-{uuid.uuid4().hex[:6]}@sync-a.cat",
                password_hash="SUPER_SECRET_BCRYPT_HASH_DO_NOT_EXPORT",
                pin_hash="SUPER_SECRET_PIN_HASH_DO_NOT_EXPORT",
                secret_2fa="SUPER_SECRET_TOTP_SEED",
                rol="BOSS",
                estat="ACTIU",
            ),
            Usuari(
                id=op_a,
                empresa_id=emp_a,
                nif=f"22{uuid.uuid4().hex[:6].upper()}B",
                nom="Marc",
                cognoms="Tècnic",
                email=f"marc-{uuid.uuid4().hex[:6]}@sync-a.cat",
                password_hash="OP_SECRET_HASH",
                pin_hash="OP_PIN_HASH",
                rol="OPERARI",
                estat="ACTIU",
            ),
            Client(
                id=cli_a,
                empresa_id=emp_a,
                codi="CLI-SYNC-A",
                rao_social="Agrícola Ponent SL",
                nif="B11223344",
                telefon="600111222",
                actiu=True,
            ),
            Client(
                id=cli_b,
                empresa_id=emp_b,
                codi="CLI-SYNC-B",
                rao_social="Client Privat Tenant B SA",
                nif="B99887766",
                actiu=True,
            ),
            Magatzem(
                id=mag_a,
                empresa_id=emp_a,
                nom="Nau Central",
                tipus="CENTRAL",
                actiu=True,
            ),
            Article(
                id=art_a,
                empresa_id=emp_a,
                referencia_inventari="REF-TUB-32",
                nom="Tub PE-100 32mm",
                unitat_mesura="METRES_LINEALS",
                familia="REG",
                estoc_minim=20.0,
                estoc_optim=100.0,
                preu_cost=1.2,
                preu_venda=2.5,
                actiu=True,
            ),
        ]
    )
    await admin_session.flush()

    # 3. Entitats dependents (Finques, Estoc, Eines, Vehicles, Pressupostos)
    admin_session.add_all(
        [
            Finca(
                id=finca_a,
                empresa_id=emp_a,
                client_id=cli_a,
                nom="Finca Les Garrigues Nord",
                adreca="Camí Vell s/n, Lleida",
                superficie_ha=14.5,
            ),
            EstocMagatzem(
                id=uuid.uuid4(),
                empresa_id=emp_a,
                article_id=art_a,
                magatzem_id=mag_a,
                quantitat_fisica=180.0,
                quantitat_virtual_reservada=30.0,
            ),
            EinaCustodia(
                id=eina_a,
                empresa_id=emp_a,
                nom="Trepant Percutor Hilti",
                model="TE-30",
                numero_serie="SN-SYNC-001",
                estat="DISPONIBLE",
                magatzem_id=mag_a,
            ),
            Vehicle(
                id=veh_a,
                empresa_id=emp_a,
                matricula="4567-MNT",
                marca="Ford",
                model="Transit Custom",
                tipus="DIESEL",
                estat="OPERATIU",
                conductor_habitual_id=op_a,
                odometre_acumulat=84200,
                data_proxima_itv=date.today() + timedelta(days=12),
                estat_itv="VIGENT",
                consum_l_100km=7.4,
            ),
            Vehicle(
                id=veh_b,
                empresa_id=emp_b,
                matricula="9999-ZZZ",
                marca="Renault",
                model="Kangoo Tenant B",
                tipus="DIESEL",
                estat="OPERATIU",
            ),
            Pressupost(
                id=pres_a,
                empresa_id=emp_a,
                client_id=cli_a,
                numero=f"PRE-SYNC-{uuid.uuid4().hex[:4].upper()}",
                total=1450.0,
                estat="PENDENT",
            ),
        ]
    )
    await admin_session.flush()

    # 4. Manteniments i Ordres de Treball (dependents de Finca i Vehicle)
    admin_session.add_all(
        [
            MantenimentVehicle(
                id=uuid.uuid4(),
                empresa_id=emp_a,
                vehicle_id=veh_a,
                data_manteniment=date.today() - timedelta(days=5),
                tipus="REVISIO",
                descripcio="Canvi d'oli i filtres",
                taller="Tallers Lleida",
                cost_euros=240.0,
            ),
            OrdreTreball(
                id=ot_a,
                empresa_id=emp_a,
                codi=f"OT-SYNC-{uuid.uuid4().hex[:5].upper()}",
                client_id=cli_a,
                finca_id=finca_a,
                titol="Reparació bomba principal",
                adreca="Camí Vell s/n, Lleida",
                estat="EN_CURS",
                cap_de_colla_id=op_a,
                vehicle_id=veh_a,
                data_planificacio=date.today(),
            ),
        ]
    )
    await admin_session.flush()

    disk_a = tmp_path / "disk_a"
    async with live_empresa_wss_context(emp_a, vault_tok_a, disk_a, start_llm=False):
        stats = await sincronitzar_entitats_empresa_al_disc(
            admin_session, emp_a, only_missing=True
        )
        assert stats["online"] is True
        assert stats["total_errors"] == 0
        assert stats["categories"]["vehicles"]["escrits"] == 1
        assert stats["categories"]["clients"]["escrits"] == 1
        assert stats["categories"]["finques"]["escrits"] == 1
        assert stats["categories"]["magatzem_articles"]["escrits"] >= 1
        assert stats["categories"]["magatzem_eines"]["escrits"] == 1
        assert stats["categories"]["operaris"]["escrits"] == 2
        assert stats["categories"]["ots_actives"]["escrits"] == 1
        assert stats["categories"]["pressupostos"]["escrits"] == 1

        # Verificar que els fitxers JSON d'operaris NO contenen cap secret
        operaris_dir = disk_a / "08_flota_i_operaris" / "operaris"
        op_files = list(operaris_dir.glob("*.json"))
        assert len(op_files) == 2
        for fp in op_files:
            raw = fp.read_text(encoding="utf-8")
            assert "password_hash" not in raw
            assert "pin_hash" not in raw
            assert "secret_2fa" not in raw
            assert "SUPER_SECRET" not in raw

        # Verificar aïllament multi-tenant: cap registre del Tenant B al disc del Tenant A
        veh_items = await SovereignStorageGateway.llegir_entitats_json(
            admin_session, emp_a, "vehicles"
        )
        assert [v["matricula"] for v in veh_items] == ["4567-MNT"]
        cli_items = await SovereignStorageGateway.llegir_entitats_json(
            admin_session, emp_a, "clients"
        )
        assert [c["codi"] for c in cli_items] == ["CLI-SYNC-A"]

        # Idempotència: una segona passada only_missing=True escriu 0 fitxers nous
        stats2 = await sincronitzar_entitats_empresa_al_disc(
            admin_session, emp_a, only_missing=True
        )
        assert stats2["total_escrits"] == 0

        # Verificar que els subagents troben les dades sincronitzades del disc
        sub_flota = SubagentFlotaDespatx()
        fleet = await sub_flota.tool_get_fleet_status(admin_session, emp_a)
        assert fleet["trobat"] is True
        assert fleet["total_vehicles"] == 1
        assert fleet["vehicles"][0]["matricula"] == "4567-MNT"
        assert fleet["vehicles"][0]["conductor"] == "Marc Tècnic"

        sub_log = SubagentLogisticaEstoc()
        stock = await sub_log.tool_get_real_stock(admin_session, emp_a, "Tub PE-100")
        assert stock["trobat"] is True
        assert stock["total_disponible"] == pytest.approx(150.0)

        sub_rag = SubagentGeneralRag()
        cli_res = await sub_rag.tool_search_clients(admin_session, emp_a, "Ponent")
        assert cli_res["trobat"] is True
        assert cli_res["clients"][0]["codi"] == "CLI-SYNC-A"


@pytest.mark.asyncio
async def test_read_repair_heals_empty_disk_category_and_filters_auxiliary_files(
    admin_session, tmp_path: Path
):
    """Quan la carpeta `vehicles` és buida al disc però el vehicle existeix a BD, read-repair el sincronitza via WSS."""
    reset_read_repair_state()
    emp_id = uuid.uuid4()
    op_id = uuid.uuid4()
    veh_id = uuid.uuid4()

    vault_tok = f"svlt_repair_{uuid.uuid4().hex[:12]}"
    admin_session.add(_make_empresa(emp_id, "REPAIR", vault_tok))
    await admin_session.flush()

    op_model = Usuari(
        id=op_id,
        empresa_id=emp_id,
        nif=f"33{uuid.uuid4().hex[:6].upper()}C",
        nom="Pere",
        cognoms="Conductor",
        email=f"pere-{uuid.uuid4().hex[:6]}@repair.cat",
        password_hash="HASH_X",
        rol="OPERARI",
        estat="ACTIU",
    )
    admin_session.add(op_model)
    await admin_session.flush()

    veh_model = Vehicle(
        id=veh_id,
        empresa_id=emp_id,
        matricula="7788-SEV",
        marca="Peugeot",
        model="Partner",
        tipus="DIESEL",
        estat="OPERATIU",
        conductor_habitual_id=op_id,
        odometre_acumulat=51000,
    )
    admin_session.add(veh_model)
    await admin_session.flush()

    disk_dir = tmp_path / "disk_repair"
    async with live_empresa_wss_context(emp_id, vault_tok, disk_dir, start_llm=False):
        # 1. Confirmem que la carpeta vehicles està inicialment buida al disc
        veh_dir = disk_dir / "08_flota_i_operaris" / "vehicles"
        assert not veh_dir.exists() or list(veh_dir.glob("*.json")) == []

        # 2. Cridem directament el subagent de flota: read-repair ha d'omplir el disc i retornar el vehicle
        sub_flota = SubagentFlotaDespatx()
        res = await sub_flota.tool_get_fleet_status(admin_session, emp_id)
        assert res["trobat"] is True
        assert res["total_vehicles"] == 1
        assert res["vehicles"][0]["matricula"] == "7788-SEV"

        # 3. Verifiquem que el fitxer JSON s'ha desat físicament amb HMAC al disc dur
        saved_json = veh_dir / f"{veh_id}.json"
        assert saved_json.is_file()
        parsed = json.loads(saved_json.read_text(encoding="utf-8"))
        assert parsed["matricula"] == "7788-SEV"
        assert parsed["_sovereign_meta"]["empresa_id"] == str(emp_id)
        assert parsed["_sovereign_meta"]["hmac_tenant"]

        # 4. Injectem fitxers auxiliars (doc_*, manteniment_*) dins la carpeta vehicles per provar el filtratge
        await SovereignStorageGateway.desar_entitat_json(
            admin_session,
            emp_id,
            "vehicles",
            "doc_fake_1",
            {
                "id": "doc_fake_1",
                "vehicle_id": str(veh_id),
                "tipus_document": "ITV",
                "nom_arxiu": "itv_2026.pdf",
                "data_document": "2026-01-15",
            },
        )
        await SovereignStorageGateway.desar_entitat_json(
            admin_session,
            emp_id,
            "vehicles",
            "manteniment_fake_1",
            {
                "id": "manteniment_fake_1",
                "vehicle_id": str(veh_id),
                "data_manteniment": "2026-02-10",
                "tipus": "REPARACIO",
                "descripcio": "Substitució corretja distribució",
            },
        )

        # 5. Verifiquem que sincronitzar_operari_al_disc_empresa NO contamina la carpeta vehicles
        await sincronitzar_operari_al_disc_empresa(admin_session, emp_id, op_model)
        assert not (veh_dir / f"operari_{op_id}.json").exists()
        assert (disk_dir / "08_flota_i_operaris" / "operaris" / f"operari_{op_id}.json").is_file()

        # 6. `get_fleet_status` només compta el vehicle real (1, mai 3 ni matricula=None)
        res_clean = await sub_flota.tool_get_fleet_status(admin_session, emp_id)
        assert res_clean["total_vehicles"] == 1
        assert [v["matricula"] for v in res_clean["vehicles"]] == ["7788-SEV"]

        # 7. `get_vehicle_maintenance` recupera el manteniment auxiliar associat
        maint = await sub_flota.tool_get_vehicle_maintenance(admin_session, emp_id, matricula="7788-SEV")
        assert maint["trobat"] is True
        assert maint["total"] == 1
        assert "corretja" in maint["manteniments"][0]["historial_reparacions"].lower()


@pytest.mark.asyncio
async def test_endpoint_sincronitzar_disc_rbac_and_execution(admin_session, tmp_path: Path):
    """`POST /api/v1/gestio/copilot/sincronitzar-disc`: 403 per ENGINYER i 200 per BOSS amb sync real."""
    reset_read_repair_state()
    emp_id = uuid.uuid4()
    boss_id = uuid.uuid4()
    eng_id = uuid.uuid4()
    veh_id = uuid.uuid4()

    vault_tok = f"svlt_api_{uuid.uuid4().hex[:12]}"
    admin_session.add(_make_empresa(emp_id, "API", vault_tok))
    await admin_session.flush()

    admin_session.add_all(
        [
            Usuari(
                id=boss_id,
                empresa_id=emp_id,
                nif=f"44{uuid.uuid4().hex[:6].upper()}D",
                nom="Boss",
                cognoms="Sync",
                email=f"boss-api-{uuid.uuid4().hex[:6]}@sync.cat",
                password_hash="H",
                rol="BOSS",
                estat="ACTIU",
            ),
            Usuari(
                id=eng_id,
                empresa_id=emp_id,
                nif=f"55{uuid.uuid4().hex[:6].upper()}E",
                nom="Eng",
                cognoms="Sync",
                email=f"eng-api-{uuid.uuid4().hex[:6]}@sync.cat",
                password_hash="H",
                rol="ENGINYER",
                estat="ACTIU",
            ),
            Vehicle(
                id=veh_id,
                empresa_id=emp_id,
                matricula="1122-API",
                marca="Volkswagen",
                model="Caddy",
                tipus="DIESEL",
                estat="OPERATIU",
            ),
        ]
    )
    await admin_session.flush()

    async def _override_get_db():
        yield admin_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        tok_eng = create_access_token(
            {"sub": str(eng_id), "empresa_id": str(emp_id), "rol": "ENGINYER"}
        )
        tok_boss = create_access_token(
            {"sub": str(boss_id), "empresa_id": str(emp_id), "rol": "BOSS"}
        )

        async with live_empresa_wss_context(emp_id, vault_tok, tmp_path / "disk_api", start_llm=False):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                r_eng = await client.post(
                    "/api/v1/gestio/copilot/sincronitzar-disc",
                    headers={"Authorization": f"Bearer {tok_eng}"},
                    json={"only_missing": False, "categories": ["vehicles"]},
                )
                assert r_eng.status_code == 403

                r_boss = await client.post(
                    "/api/v1/gestio/copilot/sincronitzar-disc",
                    headers={"Authorization": f"Bearer {tok_boss}"},
                    json={"only_missing": False, "categories": ["vehicles", "operaris"]},
                )
                assert r_boss.status_code == 200
                body = r_boss.json()
                assert body["online"] is True
                assert body["categories"]["vehicles"]["escrits"] == 1
                assert body["categories"]["operaris"]["escrits"] == 2
    finally:
        app.dependency_overrides.pop(get_db, None)
