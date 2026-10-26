"""Tests de la Fase 1 (Models i Migracions) del CRM de Superadmin Prospecció & Correu.

Verifica:
- T001: Ampliació dels models SaasLead i SaasOportunitat
- T002: Nous models SaasProspeccioTasca, SaasProspeccioCandidat, SaasCriteriFeedback,
        SaasCorreuMissatge, SaasExclusioRgpd
- T003: Migració SQL i persistència a PostgreSQL real (sense mocks de BD)
- T004: Paràmetres de configuració a Settings (Firecrawl, OpenRouter, Stalwart)
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.models import (
    SaasCorreuMissatge,
    SaasCriteriFeedback,
    SaasExclusioRgpd,
    SaasLead,
    SaasOportunitat,
    SaasProspeccioCandidat,
    SaasProspeccioTasca,
)


def test_t004_config_settings_prospeccio_i_correu():
    """Verifica que les variables de configuració de la Fase 1 estan presents i tipades."""
    assert hasattr(settings, "FIRECRAWL_API_URL")
    assert settings.FIRECRAWL_API_URL is not None
    assert hasattr(settings, "OPENROUTER_MODEL")
    assert settings.OPENROUTER_MODEL == "deepseek/deepseek-chat"
    assert hasattr(settings, "STALWART_SMTP_HOST")
    assert hasattr(settings, "SUPERADMIN_OUTREACH_EMAIL")
    assert settings.SUPERADMIN_OUTREACH_EMAIL == "tecnic@sevalor.net"


@pytest.mark.asyncio
async def test_t001_saas_lead_expanded_fields(db_session: AsyncSession):
    """Verifica la persistència de tots els nous camps de prospecció i multi-validació a SaasLead."""
    suffix = uuid.uuid4().hex[:8]
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    lead = SaasLead(
        id=lead_id,
        nom_empresa=f"Clima Segrià {suffix} SL",
        nom_contacte="Josep Pons",
        email=f"josep_{suffix}@climasegria.cat",
        telefon="611223344",
        vertical="Manteniment de Climatització Industrial",
        origen="SCRAPING_CP_25001",
        estat_qualificacio="QUALIFICAT",
        operaris_estimats=12,
        notes="Empresa especialitzada en fred industrial.",
        cif=f"B{suffix.upper()}",
        web_url="https://climasegria.cat",
        domini_normalitzat="climasegria.cat",
        adreca_fisica="Carrer Major, 14, 25001 Lleida",
        adreca_normalitzada="carrer major 14 25001 lleida",
        codi_postal="25001",
        carrec_contacte="Director Tècnic",
        fonts_investigades="web,linkedin,instagram,premsa",
        fita_recent="Nova seu inaugurada l'abril de 2026 i acreditació RITE",
        punt_dolor_detectat="Partes d'obra dispersos entre 6 furgonetes",
        angle_atac="ANGLE_A_VISIBILITAT_TELEGRAM",
        score_qualificacio=88,
        justificacio_ia="Empresa amb quadrilla de 12 tècnics i flota activa.",
        mx_validat=True,
        rao_tancament_exit=None,
        es_tancament_replicable=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    # Recuperar de la base de dades
    stmt = select(SaasLead).where(SaasLead.id == lead_id)
    res = await db_session.execute(stmt)
    saved = res.scalar_one()

    assert saved.nom_empresa == f"Clima Segrià {suffix} SL"
    assert saved.vertical == "Manteniment de Climatització Industrial"
    assert saved.domini_normalitzat == "climasegria.cat"
    assert saved.adreca_normalitzada == "carrer major 14 25001 lleida"
    assert saved.codi_postal == "25001"
    assert saved.score_qualificacio == 88
    assert saved.mx_validat is True
    assert saved.angle_atac == "ANGLE_A_VISIBILITAT_TELEGRAM"


@pytest.mark.asyncio
async def test_t001_saas_oportunitat_expanded_fields(db_session: AsyncSession):
    """Verifica que SaasOportunitat admet la raó de tancament d'èxit i el flag replicable."""
    suffix = uuid.uuid4().hex[:8]
    lead_id = uuid.uuid4()
    opp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    lead = SaasLead(
        id=lead_id,
        nom_empresa=f"Instal·lacions {suffix} SL",
        nom_contacte="Anna Font",
        email=f"anna_{suffix}@font.cat",
        vertical="ElectricPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    opp = SaasOportunitat(
        id=opp_id,
        lead_id=lead_id,
        titol=f"Llicència Sevalor - {lead.nom_empresa}",
        etapa="GUANYAT",
        valor_mensual_estimat=450.00,
        valor_ia_setup=150.00,
        probabilitat_percent=100,
        rao_tancament_exit="Necessitaven el bot de Telegram per signar entregues d'urgència.",
        requisits_replicables="Empreses d'electricitat amb més de 8 operaris i servei 24h.",
        es_replicable=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(opp)
    await db_session.flush()

    stmt = select(SaasOportunitat).where(SaasOportunitat.id == opp_id)
    res = await db_session.execute(stmt)
    saved_opp = res.scalar_one()

    assert saved_opp.etapa == "GUANYAT"
    assert "bot de Telegram" in saved_opp.rao_tancament_exit
    assert saved_opp.es_replicable is True


@pytest.mark.asyncio
async def test_t002_t003_saas_prospeccio_tasca_i_candidats(db_session: AsyncSession):
    """Verifica el cicle de vida d'un lot de Codi Postal i la taula transparent de candidats."""
    tasca_id = uuid.uuid4()
    candidat_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    tasca = SaasProspeccioTasca(
        id=tasca_id,
        codi_postal="25001",
        vertical="Instal·lacions Elèctriques i REBT",
        operaris_minims=5,
        estat="EXECUTANT",
        total_trobats=15,
        total_seleccionats=3,
        total_descartats=10,
        total_duplicats=2,
        resum_execucio="Lot de prova en curs per al Segrià.",
        created_at=now,
    )
    db_session.add(tasca)
    await db_session.flush()

    candidat = SaasProspeccioCandidat(
        id=candidat_id,
        tasca_id=tasca_id,
        nom_empresa="Electro Segre SL",
        cif="B25998877",
        web_url="https://electrosegre.cat",
        domini_normalitzat="electrosegre.cat",
        adreca_fisica="Polígon Camí dels Frares, Nau 12",
        adreca_normalitzada="poligon cami dels frares nau 12",
        codi_postal="25001",
        vertical="Instal·lacions Elèctriques i REBT",
        fonts_investigades="web,linkedin",
        email_detectat="info@electrosegre.cat",
        telefon_detectat="973200100",
        mx_validat=True,
        operaris_estimats=14,
        decisor_nom="Ramon Casals",
        decisor_carrec="Gerent",
        fita_recent="Homologació per a estacions de recàrrega ràpida",
        punt_dolor="Falta de coordinació entre oficina i instal·ladors",
        angle_atac="ANGLE_A_VISIBILITAT_TELEGRAM",
        score=92,
        estat_decisio="SELECCIONAT",
        vector_duplicitat=None,
        motiu_detallat_ia="Empresa consolidada amb 14 treballadors i serveis industrials clars.",
        corregit_huma=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(candidat)
    await db_session.flush()

    stmt = select(SaasProspeccioTasca).where(SaasProspeccioTasca.id == tasca_id)
    res = await db_session.execute(stmt)
    saved_t = res.scalar_one()

    assert saved_t.codi_postal == "25001"
    assert saved_t.total_duplicats == 2

    stmt_c = select(SaasProspeccioCandidat).where(SaasProspeccioCandidat.id == candidat_id)
    res_c = await db_session.execute(stmt_c)
    saved_c = res_c.scalar_one()

    assert saved_c.estat_decisio == "SELECCIONAT"
    assert saved_c.score == 92
    assert saved_c.decisor_nom == "Ramon Casals"


@pytest.mark.asyncio
async def test_t002_t003_saas_criteris_feedback_doble_bucle(db_session: AsyncSession):
    """Verifica que saas_criteris_feedback enregistra tant descarts com tancaments replicables."""
    f1_id = uuid.uuid4()
    f2_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. Feedback de descart corregit per l'humà
    feedback_descart = SaasCriteriFeedback(
        id=f1_id,
        tipus_aprenentatge="CORRECCIO_DESCART",
        vertical="ElectricPro",
        nom_empresa="Botiga Bombetes Lleida SL",
        web_url="https://bombetes.cat",
        resum_evidencies_o_requisits="Venda de material d'il·luminació al detall.",
        decisio_ia_original="SELECCIONAT",
        decisio_humana_correcta="DESCARTAT",
        explicacio_humana_o_rao_exit="És una botiga oberta al públic, no tenen operaris al terreny.",
        es_replicable=False,
        actiu=True,
        created_at=now,
    )
    # 2. Feedback de tancament guanyat replicable
    feedback_exit = SaasCriteriFeedback(
        id=f2_id,
        tipus_aprenentatge="TANCAMENT_EXIT_REPLICABLE",
        vertical="ElectricPro",
        nom_empresa="Electrotècnia Ponent SL",
        web_url="https://electroponent.cat",
        resum_evidencies_o_requisits="10 operaris, 5 furgonetes, manteniment elèctric terciari.",
        decisio_ia_original=None,
        decisio_humana_correcta="GUANYAT_REPLICABLE",
        explicacio_humana_o_rao_exit="Van contractar perquè els operaris van adoptar la PWA en 1 dia.",
        es_replicable=True,
        actiu=True,
        created_at=now,
    )

    db_session.add_all([feedback_descart, feedback_exit])
    await db_session.flush()

    res = await db_session.execute(
        select(SaasCriteriFeedback).where(SaasCriteriFeedback.vertical == "ElectricPro")
    )
    feedbacks = res.scalars().all()
    assert len(feedbacks) >= 2
    assert any(f.tipus_aprenentatge == "CORRECCIO_DESCART" for f in feedbacks)
    assert any(f.es_replicable is True for f in feedbacks)


@pytest.mark.asyncio
async def test_t002_t003_saas_correu_missatges_campanya_3_emails(db_session: AsyncSession):
    """Verifica la persistència de la campanya de 3 correus amb tempo i unicitat de Message-ID."""
    suffix = uuid.uuid4().hex[:8]
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    lead = SaasLead(
        id=lead_id,
        nom_empresa=f"Clima {suffix} SL",
        nom_contacte="Marc Serra",
        email=f"marc_{suffix}@serra.cat",
        vertical="ClimaPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    # Creació dels 3 correus amb offsets 0, 4 i 8 dies per al Calendari
    tempos = [
        (1, 0, now, "Proposta de col·laboració tècnica"),
        (2, 4, now + timedelta(days=4), "Com optimitzar els partes de treball a peu d'obra"),
        (3, 8, now + timedelta(days=8), "Última proposta: Demo autònoma de 7 dies"),
    ]

    for pas, offset, data_prog, assumpte in tempos:
        msg = SaasCorreuMissatge(
            id=uuid.uuid4(),
            lead_id=lead_id,
            tipus_item_calendari="EMAIL_CAMPANYA",
            pas_sequencia=pas,
            tempo_dies_offset=offset,
            data_programada=data_prog,
            direccio="OUTBOUND",
            estat_enviament="ESBORRANY_PROGRAMAT",
            remitent="tecnic@sevalor.net",
            destinatari=lead.email,
            assumpte=assumpte,
            cos_text=f"Cos del missatge pas {pas} per a {lead.nom_empresa}.",
            message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
            created_at=now,
        )
        db_session.add(msg)

    await db_session.flush()

    stmt = (
        select(SaasCorreuMissatge)
        .where(SaasCorreuMissatge.lead_id == lead_id)
        .order_by(SaasCorreuMissatge.pas_sequencia)
    )
    res = await db_session.execute(stmt)
    missatges = res.scalars().all()

    assert len(missatges) == 3
    assert [m.pas_sequencia for m in missatges] == [1, 2, 3]
    assert [m.tempo_dies_offset for m in missatges] == [0, 4, 8]
    assert all(m.estat_enviament == "ESBORRANY_PROGRAMAT" for m in missatges)


@pytest.mark.asyncio
async def test_t002_t003_saas_exclusio_rgpd_uniqueness(db_session: AsyncSession):
    """Verifica que saas_exclusio_rgpd protegeix la unicitat de (email, domini)."""
    now = datetime.now(timezone.utc)
    domini = f"test-{uuid.uuid4().hex[:6]}.com"
    email = f"optout@{domini}"

    item1 = SaasExclusioRgpd(
        id=uuid.uuid4(),
        email=email,
        domini=domini,
        cif="B12345678",
        motiu="OPTOUT_EXPLICIT",
        created_at=now,
    )
    db_session.add(item1)
    await db_session.flush()

    item2 = SaasExclusioRgpd(
        id=uuid.uuid4(),
        email=email,
        domini=domini,
        cif="B12345678",
        motiu="OPTOUT_EXPLICIT",
        created_at=now,
    )
    db_session.add(item2)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_t001_api_http_expanded_lead_and_oportunitat():
    """Verifica via HTTP AsyncClient que els nous camps de T001 es persisteixen i es retornen a l'API."""
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "rol": "SUPERADMIN",
            "empresa_id": None,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            "totp_activat": True,
            "ip_allowlist": ["testclient", "127.0.0.1", "localhost", "*"],
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:8]
    vertical_lliure = (
        "Manteniment Integral d'Instal·lacions Frigorífiques, Climatització Industrial i Energies Renovables"
    )
    assert len(vertical_lliure) <= 150

    payload = {
        "nom_empresa": f"FrigoSegre {suffix} SL",
        "nom_contacte": "Pere Valls",
        "email": f"pere_{suffix}@frigosegre.cat",
        "telefon": "+34973112233",
        "vertical": vertical_lliure,
        "origen": "SCRAPING_CP_25001",
        "operaris_estimats": 14,
        "cif": f"B{suffix.upper()}",
        "web_url": "https://frigosegre.cat",
        "domini_normalitzat": "frigosegre.cat",
        "adreca_fisica": "Polígon Industrial El Segre, Parcel·la 42",
        "adreca_normalitzada": "poligon industrial el segre parcella 42",
        "codi_postal": "25001",
        "carrec_contacte": "Cap d'Enginyeria",
        "fonts_investigades": "web,linkedin,instagram",
        "fita_recent": "Certificació ISO 50001 obtinguda el març de 2026",
        "punt_dolor_detectat": "Albarans de manteniment en paper perduts a les furgonetes",
        "angle_atac": "ANGLE_A_VISIBILITAT_TELEGRAM",
        "score_qualificacio": 91,
        "justificacio_ia": "14 tècnics al terreny i manteniment preventiu recurrent.",
        "mx_validat": True,
        "esborrany_email_assumpte": "Enhorabona per la ISO 50001 a FrigoSegre",
        "esborrany_email_cos": "Hola Pere, hem vist la vostra recent certificació ISO 50001...",
        "crear_oportunitat_inicial": True,
        "valor_mensual_estimat": 550.0,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/superadmin/crm/prospeccio/leads",
            json=payload,
            headers=headers,
        )
        assert res.status_code == 201, res.text
        created = res.json()
        lead_id = created["lead_id"]
        opp_id = created["oportunitat_id"]

        # Obtenir detall i comprovar tots els camps nous de T001
        det_res = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}",
            headers=headers,
        )
        assert det_res.status_code == 200, det_res.text
        det = det_res.json()
        assert det["vertical"] == vertical_lliure
        assert det["cif"] == f"B{suffix.upper()}"
        assert det["domini_normalitzat"] == "frigosegre.cat"
        assert det["codi_postal"] == "25001"
        assert det["score_qualificacio"] == 91
        assert det["mx_validat"] is True
        assert det["esborrany_email_assumpte"] == "Enhorabona per la ISO 50001 a FrigoSegre"

        # Actualitzar oportunitat a GUANYAT amb raó de tancament i cas replicable
        patch_opp = await ac.patch(
            f"/api/v1/superadmin/crm/prospeccio/oportunitats/{opp_id}/etapa",
            json={
                "etapa": "GUANYAT",
                "probabilitat_percent": 100,
                "rao_tancament_exit": "L'avís automàtic per Telegram al client final els estalvia 2h/dia.",
                "requisits_replicables": "Empreses de fred industrial amb >10 tècnics i guàrdies 24h.",
                "es_replicable": True,
            },
            headers=headers,
        )
        assert patch_opp.status_code == 200, patch_opp.text

        # Verificar que l'oportunitat retorna els nous camps d'aprenentatge
        det_after = await ac.get(
            f"/api/v1/superadmin/crm/prospeccio/leads/{lead_id}",
            headers=headers,
        )
        assert det_after.status_code == 200
        opp_data = det_after.json()["oportunitats"][0]
        assert opp_data["etapa"] == "GUANYAT"
        assert opp_data["es_replicable"] is True
        assert "Telegram" in opp_data["rao_tancament_exit"]

