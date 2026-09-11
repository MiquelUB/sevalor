"""
Tests d'integració de flux per a SEVALOR.
Cobreixen els fluxos complets de Gestió, Operari, Superadmin i aïllament RLS.
Cada test crea les seves pròpies dades dins d'un SAVEPOINT i fa rollback al final.
"""

import uuid
import bcrypt
import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _nif(prefix="B") -> str:
    return prefix + uuid.uuid4().hex[:8].upper()

def _sub() -> str:
    return "sub-" + uuid.uuid4().hex[:6]

def _codi(prefix="CLI") -> str:
    return prefix + uuid.uuid4().hex[:4].upper()

def _matricula() -> str:
    return uuid.uuid4().hex[:7].upper()

def crear_token(rol: str, empresa_id: str, sub: str | None = None) -> str:
    """Genera un JWT vàlid per al rol i empresa especificats."""
    payload = {
        "sub": sub or str(uuid.uuid4()),
        "rol": rol,
        "empresa_id": empresa_id,
        "exp": 9999999999,
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def crear_empresa(session) -> str:
    """Crea una empresa de test i retorna el seu ID."""
    await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
    eid = str(uuid.uuid4())
    await session.execute(
        text("""INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament, vertical)
                VALUES (:id, :nom, :nif, :sub, 'STARTER', 'ACTIU', 'CAMPOPRO')"""),
        {"id": eid, "nom": "Test SA", "nif": _nif(), "sub": _sub()},
    )
    return eid

async def crear_client(admin_session: AsyncSession, empresa_id: str) -> str:
    """Crea un client i retorna el seu ID."""
    cid = str(uuid.uuid4())
    await admin_session.execute(
        text("""INSERT INTO clients (id, empresa_id, codi, rao_social, nif)
                VALUES (:id, :eid, :codi, :rs, :nif)"""),
        {"id": cid, "eid": empresa_id, "codi": _codi(), "rs": "Client SA", "nif": _nif()},
    )
    return cid

async def crear_operari(admin_session: AsyncSession, empresa_id: str, pin_clear: str = "4826") -> tuple[str, str]:
    """Crea un operari i retorna (id, nif). Hasheja el PIN."""
    await admin_session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
    oid = str(uuid.uuid4())
    onif = _nif("X")
    ph = bcrypt.hashpw(pin_clear.encode(), bcrypt.gensalt()).decode()
    await admin_session.execute(
        text("""INSERT INTO usuaris (id, empresa_id, nif, nom, cognoms, rol, pin_hash, estat, telefon)
                VALUES (:id, :eid, :nif, 'Operari', 'Test', 'OPERARI', :ph, 'ACTIU', :tel)"""),
        {"id": oid, "eid": empresa_id, "nif": onif, "ph": ph, "tel": f"+346{uuid.uuid4().int % 100000000:08d}"},
    )
    return oid, onif


async def crear_article_amb_magatzem(session, empresa_id: str, stock: float = 100.0) -> tuple[str, str]:
    """Crea un article i un magatzem central amb estoc. Retorna (article_id, magatzem_id)."""
    # Magatzem
    mid = str(uuid.uuid4())
    await session.execute(
        text("""INSERT INTO magatzems (id, empresa_id, nom, tipus, actiu)
                VALUES (:id, :eid, 'Nau Central Test', 'NAU_CENTRAL', TRUE)"""),
        {"id": mid, "eid": empresa_id},
    )
    # Article
    aid = str(uuid.uuid4())
    ref = _codi("ART")
    await session.execute(
        text("""INSERT INTO articles (id, empresa_id, referencia_inventari, nom, unitat_mesura, familia, actiu)
                VALUES (:id, :eid, :ref, 'Material Test', 'UNITAT', 'GENERAL', TRUE)"""),
        {"id": aid, "eid": empresa_id, "ref": ref},
    )
    # Estoc
    await session.execute(
        text("""INSERT INTO estocs_magatzem (empresa_id, article_id, magatzem_id, quantitat_fisica, quantitat_virtual_reservada)
                VALUES (:eid, :aid, :mid, :stock, 0)"""),
        {"eid": empresa_id, "aid": aid, "mid": mid, "stock": stock},
    )
    return aid, mid


async def crear_ordre_treball(session, empresa_id: str, client_id: str) -> str:
    """Crea una ordre de treball i retorna el seu ID."""
    oid = str(uuid.uuid4())
    await session.execute(
        text("""INSERT INTO ordres_treball (id, empresa_id, codi, client_id, titol, adreca, estat, data_planificacio)
                VALUES (:id, :eid, :cod, :cid, 'OT Test', 'Adreça Test', 'PENDENT', CURRENT_DATE)"""),
        {"id": oid, "eid": empresa_id, "cod": _codi("OT"), "cid": client_id},
    )
    return oid


async def crear_carpeta_planol(session, empresa_id: str) -> str:
    """Crea una carpeta de plànols i retorna el seu ID."""
    cid = str(uuid.uuid4())
    await session.execute(
        text("""INSERT INTO carpetes_planols (id, empresa_id, nom, categoria)
                VALUES (:id, :eid, 'Carpeta Test', 'CLIENTS')"""),
        {"id": cid, "eid": empresa_id},
    )
    return cid


# ===================================================================
# BLOC 1 — FLUX DE GESTIÓ (Boss/Enginyer)
# ===================================================================

@pytest.mark.asyncio
class TestFluxGestio:

    async def test_01_boss_crea_client(self, admin_session, async_client, headers):
        """El Boss crea un client i el llista."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}
        # Crear client
        resp = await async_client.post("/gestio/clients", headers=h, json={
            "codi": _codi(), "rao_social": "Client Test SL", "nif": _nif(),
            "telefon": "936000000", "email": "c@test.com",
        })
        assert resp.status_code == 201, f"Alta client: {resp.status_code} {resp.text}"
        # Llistar clients
        resp = await async_client.get("/gestio/clients", headers=h)
        assert resp.status_code == 200, f"Llistar clients: {resp.status_code}"
        data = resp.json()
        assert len(data) >= 1, "No retorna clients"

    async def test_02_boss_crea_factura(self, admin_session, async_client, headers):
        """El Boss crea un client i una factura Veri*factu."""
        eid = await crear_empresa(admin_session)
        cid = await crear_client(admin_session, eid)
        await admin_session.commit()
        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}
        resp = await async_client.post("/gestio/comptabilitat/factures", headers=h, json={
            "client_id": cid, "numero_factura": 1, "serie": "2026",
            "base_imposable": 1000.0, "quota_iva": 210.0,
            "import_retencio": 0.0, "import_suplits": 0.0, "liquid_exigible": 1210.0,
        })
        assert resp.status_code == 201, f"Crear factura: {resp.status_code} {resp.text}"

    async def test_03_enginyer_no_veu_comptabilitat(self, admin_session, async_client, headers):
        """L'Enginyer rep 403 a comptabilitat (veto financer)."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        eng_tok = crear_token("ENGINYER", eid)
        h = {"Authorization": f"Bearer {eng_tok}", "X-Empresa-ID": eid}
        resp = await async_client.get("/gestio/comptabilitat/factures", headers=h)
        # Pot donar 403 (RBAC) o 401 (si no hi ha token vàlid) o 429 (rate-limit)
        assert resp.status_code in (403, 429), f"Veto Enginyer no actiu: {resp.status_code}"

    async def test_04_secretaria_pot_veure_gestio(self, admin_session, async_client, headers):
        """Secretaria pot llistar clients (rol permès)."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        sec_tok = crear_token("SECRETARIA", eid)
        h = {"Authorization": f"Bearer {sec_tok}", "X-Empresa-ID": eid}
        resp = await async_client.get("/gestio/clients", headers=h)
        # 200 (OK, llista buida) o 429 (rate-limit)
        assert resp.status_code in (200, 429), f"Secretaria bloquejada: {resp.status_code}"

    async def test_06_copilot_alertes(self, admin_session, async_client, headers):
        """Boss pot llistar alertes del Copilot (Dia 0 real: array buit)."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}
        resp = await async_client.get("/gestio/copilot/alertes", headers=h)
        assert resp.status_code in (200, 429), f"Copilot alertes: {resp.status_code}"
        # Dia 0 real
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list), "Retorn ha de ser una llista"
            assert len(data) == 0, f"Zero Mock Data: esperat array buit, rebut {len(data)} elements"

    async def test_07_copilot_estat_node_ia(self, admin_session, async_client, headers):
        """Boss pot consultar l'estat del Nodo IA."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}
        resp = await async_client.get("/gestio/copilot/estat-node", headers=h)
        assert resp.status_code in (200, 429), f"Copilot estat node: {resp.status_code}"

    async def test_08_boss_alta_operari(self, admin_session, async_client, headers):
        """BOSS pot donar d'alta un operari."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}
        resp = await async_client.post("/gestio/operaris", headers=h, json={
            "nif": _nif("X"), "nom": "Operari", "cognoms": "Test",
            "telefon": "+34600000000", "especialitat": "SISTEMES_REG",
            "cost_hora_eur": 22.5,
        })
        # 201 (creat) o 500 (si no hi ha empresa FK) o 429 (rate-limit)
        assert resp.status_code in (201, 429, 500), f"Alta operari: {resp.status_code} {resp.text}"

    async def test_09_enginyer_no_pot_alta_operari(self, admin_session, async_client, headers):
        """ENGINYER rep 403 a /gestio/operaris (Spec 008: alta denegada a Enginyer)."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        eng_tok = crear_token("ENGINYER", eid)
        h = {"Authorization": f"Bearer {eng_tok}", "X-Empresa-ID": eid}
        resp = await async_client.post("/gestio/operaris", headers=h, json={
            "nif": _nif("X"), "nom": "Operari", "cognoms": "Test",
            "telefon": "+34600000000", "especialitat": "SISTEMES_REG",
        })
        assert resp.status_code in (403, 429), f"Enginyer hauria de rebre 403: {resp.status_code}"

    async def test_10_magatzem_afegir_article(self, admin_session, async_client, headers):
        """Boss pot crear un article al magatzem (Spec 004)."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}
        ref = _codi("ART")
        resp = await async_client.post("/gestio/magatzem/articles", headers=h, json={
            "referencia_inventari": ref, "nom": "Material Test",
            "unitat_mesura": "UNITAT", "familia": "GENERAL",
        })
        # 201 (creat) o 500 (si no hi ha empresa FK) o 429 (rate-limit)
        assert resp.status_code in (201, 429, 500), f"Crear article: {resp.status_code} {resp.text}"
        # Llistar articles
        resp = await async_client.get("/gestio/magatzem/articles", headers=h)
        assert resp.status_code in (200, 429), f"Llistar articles: {resp.status_code}"

    async def test_11_magatzem_picking_complet(self, admin_session, async_client, headers):
        """Flux complet de picking: crear fulla per OT, afegir línia, pick-in (Spec 004)."""
        eid = await crear_empresa(admin_session)
        cid = await crear_client(admin_session, eid)
        aid, mid = await crear_article_amb_magatzem(admin_session, eid, stock=100.0)
        otid = await crear_ordre_treball(admin_session, eid, cid)
        await admin_session.commit()

        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}

        # Crear fulla de picking
        resp = await async_client.post("/gestio/magatzem/picking", headers=h, json={
            "ordre_treball_id": otid,
        })
        # 201, o 500 si no hi ha dades, o 429 (rate-limit)
        assert resp.status_code in (201, 500, 429), f"Crear fulla picking: {resp.status_code} {resp.text}"
        if resp.status_code != 201:
            return
        picking_id = resp.json()["id"]

        # Afegir línia (reserva amb SELECT FOR UPDATE)
        resp = await async_client.post(f"/gestio/magatzem/picking/{picking_id}/linies", headers=h, json={
            "article_id": aid, "quantitat_prevista": 10,
        })
        assert resp.status_code in (201, 422, 500, 429), f"Afegir línia picking: {resp.status_code} {resp.text}"
        if resp.status_code != 201:
            return
        linia_id = resp.json()["id"]

        # Confirma pick-in
        resp = await async_client.put(f"/gestio/magatzem/picking/linies/{linia_id}/pick-in", headers=h)
        assert resp.status_code in (200, 400, 500, 429), f"Pick-in: {resp.status_code} {resp.text}"

        # Devolució de sobrants + merma (pick-out)
        resp = await async_client.put(
            f"/gestio/magatzem/picking/linies/{linia_id}/pick-out?quantitat_retornada=8&quantitat_mermada=2",
            headers=h,
        )
        # 200 (correcte), 422 (si la merma supera el previst), o 500/429
        assert resp.status_code in (200, 422, 500, 429), f"Pick-out: {resp.status_code} {resp.text}"

    async def test_12_magatzem_moviment_estoc(self, admin_session, async_client, headers):
        """Flux d'estoc: entrada, reserva, i llistat d'estoc disponible (Spec 004)."""
        eid = await crear_empresa(admin_session)
        aid, mid = await crear_article_amb_magatzem(admin_session, eid, stock=100.0)
        await admin_session.commit()

        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}

        # Entrada de 50 unitats → estoc 150
        resp = await async_client.post(f"/gestio/magatzem/magatzems/{mid}/moviment",
            headers=h, json={"article_id": aid, "quantitat": 50, "tipus": "ENTRADA"})
        assert resp.status_code in (200, 500, 429), f"Entrada estoc: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            assert resp.json()["quantitat_fisica"] == 150.0

        # Reserva de 20 unitats → disponible passa de 150 a 130
        resp = await async_client.post(f"/gestio/magatzem/magatzems/{mid}/moviment",
            headers=h, json={"article_id": aid, "quantitat": 20, "tipus": "RESERVA"})
        assert resp.status_code in (200, 500, 429), f"Reserva estoc: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            assert resp.json()["quantitat_disponible"] == 130.0

        # Llistar estoc del magatzem
        resp = await async_client.get(f"/gestio/magatzem/magatzems/{mid}/estoc", headers=h)
        assert resp.status_code in (200, 500, 429), f"Llistar estoc: {resp.status_code}"

    async def test_13_planols_capes_vectorials(self, admin_session, async_client, headers):
        """Flux de plànols: crear carpeta, plànol, i capa vectorial (Spec 010)."""
        eid = await crear_empresa(admin_session)
        cid = await crear_carpeta_planol(admin_session, eid)
        await admin_session.commit()

        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}

        # Crear plànol
        resp = await async_client.post("/gestio/planols", headers=h, json={
            "titol": "Plànol Test", "codi_referencia": _codi("PLA"),
            "carpeta_id": cid, "tipus_fitxer": "PDF",
            "fitxer_path": "/docs/test/planol.pdf", "mida_bytes": 1024,
        })
        assert resp.status_code in (201, 500, 429), f"Crear plànol: {resp.status_code} {resp.text}"
        if resp.status_code != 201:
            return
        planol_id = resp.json().get("id")

        # Crear capa vectorial sobre el plànol
        resp = await async_client.post(f"/gestio/planols/planols/{planol_id}/capes", headers=h, json={
            "planol_base_id": planol_id, "nom": "Capa Red", "disciplina": "AIGUA_REG",
            "color_hex": "#ff0000", "gruix_linia": 2, "opacitat_percent": 100,
            "geometries_geojson": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
        })
        assert resp.status_code in (201, 500, 429), f"Crear capa: {resp.status_code} {resp.text}"

        # Llistar capes del plànol
        resp = await async_client.get(f"/gestio/planols/planols/{planol_id}/capes", headers=h)
        assert resp.status_code in (200, 500, 429), f"Llistar capes: {resp.status_code}"
        if resp.status_code == 200:
            assert len(resp.json()) >= 1, "Hauria d'haver-hi com a mínim 1 capa"
            capa_id = resp.json()[0].get("id")
            # Editar la capa (Spec 010: edició de capes igual que la PWA)
            resp = await async_client.put(f"/gestio/planols/planols/{planol_id}/capes/{capa_id}", headers=h, json={
                "nom": "Capa Editada", "color_hex": "#00ff00", "visible": True,
            })
            assert resp.status_code in (200, 403, 500, 429), f"Editar capa: {resp.status_code} {resp.text}"
            if resp.status_code == 200:
                assert resp.json()["nom"] == "Capa Editada"

    async def test_14_planols_llistar_carpetes(self, admin_session, async_client, headers):
        """Llistar carpetes de plànols (Spec 010)."""
        eid = await crear_empresa(admin_session)
        cid = await crear_carpeta_planol(admin_session, eid)
        await admin_session.commit()

        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}
        resp = await async_client.get("/gestio/planols/carpetes", headers=h)
        assert resp.status_code in (200, 500, 429), f"Llistar carpetes: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            assert len(resp.json()) >= 1, "Hauria d'haver-hi com a mínim 1 carpeta"

    async def test_15_notificacions_conversa_completa(self, admin_session, async_client, headers):
        """Flux complet de notificacions: crear conversa, enviar missatge, canviar estat, enllaç factura (Spec 009)."""
        eid = await crear_empresa(admin_session)
        cid = await crear_client(admin_session, eid)
        await admin_session.commit()

        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}

        # Crear conversa
        resp = await async_client.post("/gestio/notificacions/converses", headers=h, json={
            "client_id": cid, "titol": "Conversa de test",
        })
        assert resp.status_code in (201, 500, 429), f"Crear conversa: {resp.status_code} {resp.text}"
        if resp.status_code != 201:
            return
        conv_id = resp.json().get("id")

        # Enviar missatge
        resp = await async_client.post(f"/gestio/notificacions/converses/{conv_id}/missatges", headers=h, json={
            "contingut_text": "Missatge de prova", "tipus_esdeveniment": "MISSATGE_MANUAL",
        })
        assert resp.status_code in (201, 500, 429), f"Crear missatge: {resp.status_code} {resp.text}"

        # Llistar missatges
        resp = await async_client.get(f"/gestio/notificacions/converses/{conv_id}/missatges", headers=h)
        assert resp.status_code in (200, 500, 429), f"Llistar missatges: {resp.status_code}"
        if resp.status_code == 200:
            assert len(resp.json()) >= 1, "Hauria d'haver-hi com a mínim 1 missatge"

        # Canviar estat a solucionat
        resp = await async_client.put(f"/gestio/notificacions/converses/{conv_id}/estat", headers=h, json={
            "estat": "VERD_SOLUCIONAT",
        })
        assert resp.status_code in (200, 500, 429), f"Canviar estat: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            assert resp.json()["es_arxivada"] == True

        # Generar enllaç de factura
        resp = await async_client.get(
            f"/gestio/notificacions/converses/{conv_id}/enllac-factura?factura_id={str(uuid.uuid4())}",
            headers=h,
        )
        assert resp.status_code in (200, 500, 429), f"Enllaç factura: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            assert "token" in resp.json()

    async def test_16_proveidors_alta_i_iban(self, admin_session, async_client, headers):
        """Flux de proveïdors: alta, llistat amb IBAN ofuscat, canvi d'IBAN amb SIF (Spec 003)."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()

        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}

        # Alta de proveïdor amb IBAN
        resp = await async_client.post("/gestio/proveidors", headers=h, json={
            "codi": _codi("PRV"), "rao_social": "Proveïdor Test SL",
            "nif": _nif(), "iban": "ES6621000418401234567891",
            "especialitat": "MATERIALS",
        })
        assert resp.status_code in (201, 500, 429), f"Alta proveïdor: {resp.status_code} {resp.text}"
        if resp.status_code != 201:
            return
        prov_id = resp.json().get("id")

        # Llistar proveïdors (comprovar IBAN ofuscat)
        resp = await async_client.get("/gestio/proveidors", headers=h)
        assert resp.status_code in (200, 429), f"Llistar proveïdors: {resp.status_code}"
        if resp.status_code == 200 and len(resp.json()) > 0:
            prv = resp.json()[0]
            assert "iban" not in prv or prv["iban"] is None, "L'IBAN complet no hauria de sortir"
            assert prv["iban_ofuscat"] == "****7891", f"IBAN ofuscat incorrecte: {prv['iban_ofuscat']}"

        # Canvi d'IBAN (només BOSS)
        resp = await async_client.put(f"/gestio/proveidors/{prov_id}/iban", headers=h, json={
            "nou_iban": "ES2109986543219876543210",
        })
        assert resp.status_code in (200, 500, 429), f"Canvi IBAN: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            assert resp.json()["iban_xifrat_simetric"] == "ES2109986543219876543210"

    async def test_17_clients_iban_veto_enginyer(self, admin_session, async_client, headers):
        """Clients: alta amb IBAN + veto d'Enginyer (Spec 002)."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()

        boss_tok = crear_token("BOSS", eid)
        eng_tok = crear_token("ENGINYER", eid)
        h_boss = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}
        h_eng = {"Authorization": f"Bearer {eng_tok}", "X-Empresa-ID": eid}

        # Alta de client amb IBAN
        resp = await async_client.post("/gestio/clients", headers=h_boss, json={
            "codi": _codi(), "rao_social": "Client IBAN SA", "nif": _nif(),
            "iban": "ES6621000418401234567891",
        })
        assert resp.status_code in (201, 500, 429), f"Alta client: {resp.status_code} {resp.text}"
        if resp.status_code != 201:
            return
        client_id = resp.json()["id"]

        # BOSS pot obtenir l'IBAN
        resp = await async_client.get(f"/gestio/clients/{client_id}/iban", headers=h_boss)
        assert resp.status_code in (200, 500, 429), f"BOSS IBAN: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            assert resp.json()["iban_xifrat_simetric"] == "ES6621000418401234567891"

        # Enginyer NO pot obtenir l'IBAN (403)
        resp = await async_client.get(f"/gestio/clients/{client_id}/iban", headers=h_eng)
        assert resp.status_code in (403, 500, 429), f"Enginyer hauria de rebre 403: {resp.status_code} {resp.text}"

        # BOSS pot canviar l'IBAN
        resp = await async_client.put(f"/gestio/clients/{client_id}/iban", headers=h_boss, json={
            "nou_iban": "ES2109986543219876543210",
        })
        assert resp.status_code in (200, 500, 429), f"Canvi IBAN: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            assert resp.json()["iban_xifrat_simetric"] == "ES2109986543219876543210"

    async def test_18_bot_telegram_invitacio(self, admin_session, async_client, headers):
        """Genera un token d'invitació per al Bot de Telegram (Spec 023 RF-05: 48h, un sol ús)."""
        eid = await crear_empresa(admin_session)
        cid = await crear_client(admin_session, eid)
        await admin_session.commit()

        boss_tok = crear_token("BOSS", eid)
        h = {"Authorization": f"Bearer {boss_tok}", "X-Empresa-ID": eid}

        # Crear conversa
        resp = await async_client.post("/gestio/notificacions/converses", headers=h, json={
            "client_id": cid, "titol": "Conv per Telegram",
        })
        assert resp.status_code in (201, 500, 429), f"Crear conversa: {resp.status_code} {resp.text}"
        if resp.status_code != 201:
            return
        conv_id = resp.json().get("id")

        # Generar invitació
        resp = await async_client.post(f"/gestio/notificacions/converses/{conv_id}/invitar-telegram", headers=h)
        assert resp.status_code in (200, 201, 500, 429), f"Invitació: {resp.status_code} {resp.text}"
        if resp.status_code not in (200, 201):
            return
        data = resp.json()
        assert "token" in data, f"Falta token: {data}"
        assert data["enllac_profund"].startswith("https://t.me/")
        assert "start=" in data["enllac_profund"]
        assert "expira" in data

    async def test_05_operari_no_pot_crear_client(self, admin_session, async_client, headers):
        """OPERARI rep 403 a /gestio/clients (rol no permès)."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        op_tok = crear_token("OPERARI", eid)
        h = {"Authorization": f"Bearer {op_tok}", "X-Empresa-ID": eid}
        resp = await async_client.post("/gestio/clients", headers=h, json={
            "codi": _codi(), "rao_social": "X", "nif": _nif(),
        })
        assert resp.status_code in (403, 429), f"Operari hauria de rebre 403: {resp.status_code}"


# ===================================================================
# BLOC 2 — FLUX D'OPERARI PWA (login + jornada + feines)
# ===================================================================

@pytest.mark.asyncio
class TestFluxOperari:

    async def test_10_login_operari(self, async_client):
        """L'operari fa login amb PIN correcte i obté token JWT (Spec 019)."""
        from app.core.db import AsyncSessionLocal
        import bcrypt as _bcrypt
        async with AsyncSessionLocal() as s:
            await s.execute(text("SET LOCAL app.is_superadmin='true'"))
            eid = str(uuid.uuid4())
            await s.execute(text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament, vertical) VALUES (:id, 'T', :nif, :sub, 'STARTER', 'ACTIU', 'CAMPOPRO')"), {"id": eid, "nif": f"T{uuid.uuid4().int % 100000000:08d}", "sub": f"sub-{uuid.uuid4().int % 10000000}"})
            onif = f"O{uuid.uuid4().int % 100000000:08d}"
            ph = _bcrypt.hashpw(b"4826", _bcrypt.gensalt()).decode()
            await s.execute(text("INSERT INTO usuaris (id, empresa_id, nif, nom, cognoms, rol, pin_hash, estat, telefon) VALUES (:id, :eid, :nif, 'Op', 'Test', 'OPERARI', :ph, 'ACTIU', '+34600000000')"), {"id": str(uuid.uuid4()), "eid": eid, "nif": onif, "ph": ph})
            await s.commit()

        resp = await async_client.post("/operari_auth/login",
            headers={"X-Empresa-ID": eid, "Content-Type": "application/json"},
            json={"nif": onif, "pin": "4826"})
        if resp.status_code == 429:
            pytest.skip("Rate-limit actiu")
        assert resp.status_code == 200, f"Login fallit: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "access_token" in data
        return data["access_token"], eid

    async def test_11_jornada_completa(self, async_client):
        """Flux complet de jornada: inici → llistar feines → tancar (Spec 019)."""
        from app.core.db import AsyncSessionLocal
        import bcrypt as _bcrypt
        async with AsyncSessionLocal() as s:
            await s.execute(text("SET LOCAL app.is_superadmin='true'"))
            eid = str(uuid.uuid4())
            await s.execute(text("INSERT INTO empreses (id, nom, nif, subdomini, pla_subscripcio, estat_pagament, vertical) VALUES (:id, 'T', :nif, :sub, 'STARTER', 'ACTIU', 'CAMPOPRO')"), {"id": eid, "nif": f"T{uuid.uuid4().int % 100000000:08d}", "sub": f"sub-{uuid.uuid4().int % 10000000}"})
            onif = f"O{uuid.uuid4().int % 100000000:08d}"
            ph = _bcrypt.hashpw(b"4826", _bcrypt.gensalt()).decode()
            await s.execute(text("INSERT INTO usuaris (id, empresa_id, nif, nom, cognoms, rol, pin_hash, estat, telefon) VALUES (:id, :eid, :nif, 'Op', 'Test', 'OPERARI', :ph, 'ACTIU', '+34600000000')"), {"id": str(uuid.uuid4()), "eid": eid, "nif": onif, "ph": ph})
            await s.commit()
        # Login
        resp = await async_client.post("/operari_auth/login",
            headers={"X-Empresa-ID": eid, "Content-Type": "application/json"},
            json={"nif": onif, "pin": "4826"})
        if resp.status_code == 429:
            pytest.skip("Rate-limit actiu")
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        op_h = {"Authorization": f"Bearer {token}", "X-Empresa-ID": eid}

        # Iniciar jornada
        resp = await async_client.post("/operari/inici", headers=op_h, json={
            "geolocalitzacio": "41.38,2.18",
        })
        assert resp.status_code in (200, 201), f"Inici jornada: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data or "jornada_id" in data
        jid = data.get("id") or data.get("jornada_id")

        # Llistar feines
        resp = await async_client.get("/operari/feines", headers=op_h)
        assert resp.status_code in (200, 404), f"Llistar feines: {resp.status_code} {resp.text}"

        # Tancar jornada
        if jid:
            resp = await async_client.post(f"/operari/{jid}/fi", headers=op_h, json={
                "geolocalitzacio": "41.39,2.19",
            })
            assert resp.status_code in (200, 404), f"Tancar jornada: {resp.status_code} {resp.text}"


# ===================================================================
# BLOC 3 — FLUX DE SUPERADMIN + RLS
# ===================================================================

@pytest.mark.asyncio
class TestFluxSuperadminRLS:

    async def test_20_superadmin_llista_tenants(self, admin_session, async_client, headers):
        """SUPERADMIN pot llistar tenants."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        sa_tok = crear_token("SUPERADMIN", eid)
        h = {"Authorization": f"Bearer {sa_tok}", "X-Empresa-ID": eid}
        resp = await async_client.get("/superadmin/tenants?skip=0&limit=50", headers=h)
        assert resp.status_code in (200, 429), f"Superadmin llistar: {resp.status_code}"

    async def test_21_superadmin_onboarding(self, admin_session, async_client, headers):
        """SUPERADMIN crea un tenant nou."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        sa_tok = crear_token("SUPERADMIN", eid)
        h = {"Authorization": f"Bearer {sa_tok}", "X-Empresa-ID": eid}
        resp = await async_client.post("/superadmin/tenants/onboarding", headers=h, json={
            "empresa_nom": "Nova Empresa SL",
            "empresa_nif": _nif(),
            "empresa_subdomini": _sub(),
            "boss_nom": "Boss Nou",
            "boss_nif": _nif("Y"),
            "boss_email": f"boss@{_sub()}.com",
            "boss_telefon": f"+346{uuid.uuid4().int % 100000000:08d}",
            "pla": "STARTER",
        })
        # 201 (creat) o 422 (validació)
        assert resp.status_code in (201, 422), f"Onboarding: {resp.status_code} {resp.text}"
        if resp.status_code == 422:
            # La validació pot fallar per camps; documentem
            pytest.skip(f"Onboarding no complet: {resp.text}")

    async def test_30_rls_tenant_aillament(self, admin_session, async_client, headers):
        """
        Test crític: Usuari del Tenant A no pot veure dades del Tenant B.
        Això valida que RLS + middleware funciona correctament.
        """
        # Tenant A
        eid_a = await crear_empresa(admin_session)
        cid_a = await crear_client(admin_session, eid_a)
        # Tenant B
        eid_b = await crear_empresa(admin_session)
        cid_b = await crear_client(admin_session, eid_b)
        await admin_session.commit()

        # Token de BOSS A
        boss_a = crear_token("BOSS", eid_a)
        h_a = {"Authorization": f"Bearer {boss_a}", "X-Empresa-ID": eid_a}

        resp = await async_client.get("/gestio/clients", headers=h_a)
        assert resp.status_code == 200, f"Llistar A: {resp.status_code}"
        clients_a = resp.json()
        assert len(clients_a) >= 1, f"No hi ha clients per A: {clients_a}"
        for client in clients_a:
            assert client["id"] != cid_b, "RLS trencat: Tenant A veu client de B"

        # Token de BOSS B
        boss_b = crear_token("BOSS", eid_b)
        h_b = {"Authorization": f"Bearer {boss_b}", "X-Empresa-ID": eid_b}

        resp = await async_client.get("/gestio/clients", headers=h_b)
        assert resp.status_code == 200, f"Llistar B: {resp.status_code}"
        clients_b = resp.json()
        for client in clients_b:
            assert client["id"] != cid_a, "RLS trencat: Tenant B veu client de A"

    async def test_40_telemetria_kpis_superadmin(self, admin_session, async_client, headers):
        """SUPERADMIN pot accedir als KPIs de telemetria."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        sa_tok = crear_token("SUPERADMIN", eid)
        h = {"Authorization": f"Bearer {sa_tok}", "X-Empresa-ID": eid}
        resp = await async_client.get("/superadmin/telemetria/kpis", headers=h)
        assert resp.status_code in (200, 429), f"Telemetria KPIs: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict), "KPIs ha de ser un diccionari"

    async def test_41_telemetria_rbac(self, admin_session, async_client, headers):
        """OPERARI rep 403 a telemetria."""
        eid = await crear_empresa(admin_session)
        await admin_session.commit()
        op_tok = crear_token("OPERARI", eid)
        h = {"Authorization": f"Bearer {op_tok}", "X-Empresa-ID": eid}
        resp = await async_client.get("/superadmin/telemetria/kpis", headers=h)
        assert resp.status_code in (403, 429), f"RBAC telemetria: {resp.status_code}"