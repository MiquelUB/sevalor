"""Suite de tests per a la Fase 2 (Tasks T005 a T008) del CRM de Superadmin.

Cobreix:
- T005: `firecrawl_service.py` — Normalització de 3 vectors, deduplicació multi-validació
        (Domini, Adreça física, CIF) i investigació multi-canal.
- T006: `mx_shield_service.py` — Validació RFC 5322, bloqueig de dominis d'un sol ús,
        comprovació contra `saas_exclusio_rgpd` i resolució DNS MX en viu.
- T007: `openrouter_prospecting_service.py` — Avaluació amb Pydantic, Doble Bucle d'Aprenentatge
        (descarts humans + tancaments replicables lookalike) i seqüència de 3 correus amb tempo
        (prohibició estricta de WhatsApp; ús exclusiu de PWA + Telegram).
- T008: `stalwart_mail_service.py` — Planificació al Calendari Comercial, fil RFC 5322,
        enviament HITL, pausa automàtica per resposta entrant i processament d'objeccions/baixes.

Normativa estricta:
- PostgreSQL 16 real amb `create_savepoint` i sense mocks de BD.
- Absència total de `db.refresh()`.
- Generadors aleatoris amb UUID per a unicitat.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import (
    Empresa,
    SaasActivitatLead,
    SaasCorreuMissatge,
    SaasCriteriFeedback,
    SaasExclusioRgpd,
    SaasLead,
)
from app.services.firecrawl_service import (
    _desencriptar_cfemail,
    _extreure_adreca_amb_cp_de_text,
    _extreure_emails_empresa_i_gatekeeper_de_text,
    _extreure_gatekeeper_real_de_text,
    _extreure_metadades_html_brut,
    _extreure_telefon_de_text,
    _netejar_html_a_text,
    es_nom_persona_real,
    extreure_mapa_fonts_urls,
    firecrawl_service,
    formatar_fonts_verificables,
    normalitzar_adreca,
    normalitzar_cif,
    normalitzar_domini,
    validar_cp_en_adreca_fisica,
    validar_cp_o_municipi_en_adreca,
    verificar_duplicitat_multivector,
)
from app.services.mx_shield_service import (
    es_domini_temporal,
    validar_email_mx,
    validar_sintaxi_email,
    verificar_registres_dns_mx,
)
from app.services.openrouter_prospecting_service import (
    EmailStepSchema,
    LeadEvaluationSchema,
    _extreure_context_prioritari_ia,
    carregar_context_doble_bucle,
    qualificar_candidat_amb_openrouter,
)
from app.services.stalwart_mail_service import (
    aprovar_i_enviar_correu_calendari,
    processar_resposta_inbound,
    programar_campanya_3_emails,
)

# ==============================================================================
# TESTS T005: NORMALITZACIÓ I DEDUPLICACIÓ MULTI-VALIDACIÓ PER 3 VECTORS
# ==============================================================================

def test_t005_normalitzacio_vectors():
    """Verifica la normalització canònica dels 3 vectors: domini, adreça i CIF."""
    # 1. Domini
    assert normalitzar_domini("https://www.climasegria.cat/qui-som") == "climasegria.cat"
    assert normalitzar_domini("WWW.Electro-Segre.COM:443/") == "electro-segre.com"
    assert normalitzar_domini("http://instals.cat?utm=promo") == "instals.cat"

    # 2. Adreça física
    adreca_raw = "Pol. Ind. Camí dels Frares, Nau 14, C/ Major, Núm. 5"
    norm = normalitzar_adreca(adreca_raw)
    assert "poligon industrial" in norm
    assert "cami dels frares" in norm
    assert "carrer major" in norm
    assert "," not in norm
    assert "." not in norm

    # 3. CIF
    assert normalitzar_cif("B-25.123.456") == "B25123456"
    assert normalitzar_cif("a 25998877 ") == "A25998877"


@pytest.mark.asyncio
async def test_t005_deduplicacio_multivector_saas_leads(db_session: AsyncSession):
    """Verifica que un candidat es detecta com a duplicat si coincideix qualsevol dels 3 vectors a saas_leads."""
    suffix = uuid.uuid4().hex[:8]
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    lead_existent = SaasLead(
        id=lead_id,
        nom_empresa=f"Clima Ponent {suffix} SL",
        nom_contacte="Jordi Prat",
        email=f"jordi_{suffix}@climaponent.cat",
        domini_normalitzat=f"climaponent-{suffix}.cat",
        adreca_fisica="Polígon Industrial El Segre, Nau 5",
        adreca_normalitzada=f"poligon industrial el segre nau 5 {suffix}",
        cif=f"B{suffix.upper()}",
        vertical="ClimaPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead_existent)
    await db_session.flush()

    # Vector 1: Coincideix el Domini Web (fins i tot amb URL bruta)
    es_dup, vector, detall = await verificar_duplicitat_multivector(
        db=db_session,
        domini=f"https://www.climaponent-{suffix}.cat/serveis",
        adreca="Altra adreça diferent",
        cif="B99999999",
    )
    assert es_dup is True
    assert vector == "DOMINI_WEB"
    assert "Clima Ponent" in (detall or "")

    # Vector 2: Coincideix l'Adreça Física (fins i tot amb abreviatures diferents)
    es_dup2, vector2, detall2 = await verificar_duplicitat_multivector(
        db=db_session,
        domini="https://altre-web-nou.com",
        adreca=f"Pol. Ind. El Segre, Nau 5, {suffix}",
        cif="B88888888",
    )
    assert es_dup2 is True
    assert vector2 == "ADRECA_FISICA"

    # Vector 3: Coincideix el CIF
    es_dup3, vector3, detall3 = await verificar_duplicitat_multivector(
        db=db_session,
        domini="https://empresa-diferent.cat",
        adreca="Carrer Nou, 1",
        cif=f"B-{suffix.upper()}",
    )
    assert es_dup3 is True
    assert vector3 == "CIF"


@pytest.mark.asyncio
async def test_t005_deduplicacio_client_existent_i_rgpd(db_session: AsyncSession):
    """Verifica que el filtre detecta clients que ja estan a `empreses` o a `saas_exclusio_rgpd`."""
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    cif_client = f"A{suffix.upper()}"
    domini_exclos = f"optout-{suffix}.cat"

    # Crear empresa client existent a Sevalor
    emp = Empresa(
        id=uuid.uuid4(),
        nom=f"Client Existent {suffix}",
        nif=cif_client,
        subdomini=f"cli{suffix[:6]}",
        domini_custom=f"app.{suffix}.cat",
        created_at=now,
        updated_at=now,
    )
    # Crear registre a llista negra RGPD
    exclusio = SaasExclusioRgpd(
        id=uuid.uuid4(),
        email=f"baja@{domini_exclos}",
        domini=domini_exclos,
        motiu="OPTOUT_EXPLICIT",
        created_at=now,
    )
    db_session.add_all([emp, exclusio])
    await db_session.flush()

    # Detecció de client actiu de Sevalor
    es_dup_client, vec_client, _ = await verificar_duplicitat_multivector(
        db=db_session,
        cif=cif_client,
    )
    assert es_dup_client is True
    assert vec_client == "CIF"

    # Detecció de domini a la llista negra RGPD
    es_dup_rgpd, vec_rgpd, _ = await verificar_duplicitat_multivector(
        db=db_session,
        domini=f"https://www.{domini_exclos}/contacte",
    )
    assert es_dup_rgpd is True
    assert vec_rgpd == "DOMINI_WEB"


@pytest.mark.asyncio
async def test_t005_firecrawl_investigacio_multicanal():
    """Verifica l'extracció multi-canal amb enllaços directes comprovables i Gatekeeper real."""
    res = await firecrawl_service.investigar_empresa_completa(
        nom_empresa="Electrotècnica Segre SL",
        web_url="https://electrotecnicasegre.cat",
        codi_postal="25001",
        vertical="Instal·lacions Elèctriques REBT",
        dades_inicials={
            "decisor_nom": "Jordi Soler Prat",
            "decisor_carrec": "Director Tècnic",
            "linkedin_url": "https://www.linkedin.com/in/jordi-soler-prat",
            "instagram_url": "https://www.instagram.com/electrotecnicasegre/",
            "web_markdown": "Empresa d'instal·lacions elèctriques industrials al Pol. Ind. El Segre, 25001 Lleida.",
        },
    )
    assert "fonts_investigades" in res
    assert any(f.startswith("web|https://electrotecnicasegre.cat") for f in res["fonts_investigades"])
    assert any(f.startswith("linkedin|https://www.linkedin.com/") for f in res["fonts_investigades"])
    assert any(f.startswith("instagram|https://www.instagram.com/") for f in res["fonts_investigades"])
    assert res["gatekeeper_hints"].get("nom") == "Jordi Soler Prat"
    assert "web_markdown" in res


def test_t005_validacions_cp_adreca_gatekeeper_real_i_urls():
    """Verifica les 3 regles crítiques: CP en adreça física, Gatekeeper real (no genèric) i URLs directes."""
    # Regla 1: Codi Postal en adreça física real i flexibilització per municipi
    assert validar_cp_en_adreca_fisica("Avinguda Comtes de Pallars, 12, 25560 Sort", "25560") is True
    assert validar_cp_en_adreca_fisica("Pol. Ind. El Segre, Nau 4, 25001 Lleida", "25560") is False
    assert validar_cp_en_adreca_fisica("LinkedIn/Instagram: Nova instal·lació a la zona 25560", "25560") is False
    assert validar_cp_en_adreca_fisica("Zona Codi Postal 25560", "25560") is False
    assert validar_cp_o_municipi_en_adreca("Carrer Major, 10, 25560 Sort", "25560", municipi="Sort") is True
    # Spec 007: Mai es dóna per bo només el municipi sense el CP exacte a l'adreça
    assert validar_cp_o_municipi_en_adreca("Polígon Industrial El Segre, Nau 2, Lleida", "25001", municipi="Lleida") is False
    assert validar_cp_o_municipi_en_adreca("Avinguda Diagonal, 100, Barcelona", "25001", municipi="Lleida") is False

    # Regla 2: Nom i Cognom real de Gatekeeper (rebutjant tots els càrrecs i noms genèrics)
    assert es_nom_persona_real("Joan Marcet Vila") is True
    assert es_nom_persona_real("Antoni Vidal") is True
    assert es_nom_persona_real("Marta de la Torre") is True
    assert es_nom_persona_real("Responsable d'Operacions de Tècnics manteniment 25560 SL") is False
    assert es_nom_persona_real("Director Tècnic") is False
    assert es_nom_persona_real("Responsable Comercial") is False
    assert es_nom_persona_real("Gerent") is False
    assert es_nom_persona_real("Departament Tècnic") is False

    # Regla 3: Enllaços directes comprovables per canal
    fonts = formatar_fonts_verificables(
        {
            "linkedin": "https://www.linkedin.com/company/climasegre",
            "instagram": "https://www.instagram.com/climasegre/",
        },
        web_url="https://climasegre.cat",
    )
    mapa = extreure_mapa_fonts_urls(",".join(fonts))
    assert mapa["web"] == "https://climasegre.cat"
    assert mapa["linkedin"] == "https://www.linkedin.com/company/climasegre"
    assert mapa["instagram"] == "https://www.instagram.com/climasegre/"


def test_t005_cloudflare_desencriptacio_mobils_i_context_ia():
    """Verifica la desencriptació Cloudflare cfemail, extracció de wa.me, raó social i context prioritari IA."""
    key = 0x1F
    plain_email = "gerencia@electroclima.cat"
    cf_hex = f"{key:02x}" + "".join(f"{(ord(c) ^ key):02x}" for c in plain_email)

    assert _desencriptar_cfemail(cf_hex) == plain_email
    assert _desencriptar_cfemail("invalid_hex_string") is None

    html_raw = f"""
    <html>
      <body>
        <h1>Instal·lacions del Pirineu SLU</h1>
        <p>Contacte: <a data-cfemail="{cf_hex}">[email&#160;protected]</a></p>
        <p>WhatsApp: <a href="https://wa.me/34655443322">Xat directe</a></p>
        <p>Centraleta: <a href="callto:+34973556677">Trucar</a></p>
      </body>
    </html>
    """
    meta = _extreure_metadades_html_brut(html_raw)
    assert plain_email in meta["mailtos"]
    assert "34655443322" in meta["tels"]
    assert "+34973556677" in meta["tels"]
    assert "Instal·lacions del Pirineu SLU" in (meta.get("rao_social_detectada") or "")

    # Context prioritari per a IA (DeepSeek 6000 caràcters)
    md_gran = "Capçalera Corporativa. " * 200 + " Administrador Únic: Pere Soler, CIF: B25888888, Nau 5 Polígon. " + " Peu de pàgina Legal. " * 300
    ctx = _extreure_context_prioritari_ia(md_gran, max_len=6000)
    assert len(ctx) <= 6000
    assert "administrador" in ctx.lower()
    assert "b25888888" in ctx.lower()


def test_t005_scraper_extraccio_adreca_email_gatekeeper_telefon_real():
    """Verifica que el scraper extreu adreça física real (amb abreviatures i JSON-LD),
    email real d'empresa i del Gatekeeper (`mailto:` i text), nom i càrrec real del Gatekeeper
    i telèfon real (`tel:` i text).
    """
    raw_html = """
    <html>
      <head>
        <title>Clima Pirineus SL - Instal·lacions</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "LocalBusiness",
          "name": "Clima Pirineus SL",
          "taxID": "B25987654",
          "email": "info@climapirineus.cat",
          "telephone": "+34 973 62 01 23",
          "address": {
            "@type": "PostalAddress",
            "streetAddress": "Pol. Ind. La Borda, Av. Generalitat, Núm. 14",
            "postalCode": "25560",
            "addressLocality": "Sort",
            "addressRegion": "Lleida"
          },
          "founder": {
            "@type": "Person",
            "name": "Jordi Soler Puig",
            "jobTitle": "Director Tècnic"
          }
        }
        </script>
      </head>
      <body>
        <div class="team">
          <h4>Jordi Soler Puig</h4>
          <p>Director Tècnic</p>
          <a href="mailto:j.soler@climapirineus.cat">Contactar amb Direcció</a>
          <a href="mailto:info@climapirineus.cat">Informació General</a>
          <a href="tel:+34654321987">Mòbil Urgències</a>
        </div>
        <address>
          Pol. Ind. La Borda, Av. Generalitat, Núm. 14, 25560 Sort (Lleida)
        </address>
      </body>
    </html>
    """
    meta = _extreure_metadades_html_brut(raw_html)
    text_net = _netejar_html_a_text(raw_html)

    # 1. Adreça física real amb CP 25560 i abreviatures (Pol. Ind., Av., Núm.)
    adreca = _extreure_adreca_amb_cp_de_text(
        text_net,
        "25560",
        adreces_estructurades=meta["adreces_estructurades"],
    )
    assert adreca is not None
    assert "25560" in adreca
    assert "Generalitat" in adreca

    # 2. Gatekeeper real (Nom i Cognom + Càrrec)
    nom_gk, carrec_gk = _extreure_gatekeeper_real_de_text(
        text_net,
        nom_jsonld=meta["gatekeeper_nom"],
        carrec_jsonld=meta["gatekeeper_carrec"],
    )
    assert nom_gk == "Jordi Soler Puig"
    assert carrec_gk == "Director Tècnic"

    # 3. Email real d'empresa + Email directe del Gatekeeper
    emails = _extreure_emails_empresa_i_gatekeeper_de_text(
        text_net,
        domini_preferit="climapirineus.cat",
        decisor_nom=nom_gk,
        mailtos_html=meta["mailtos"],
    )
    assert emails["email_empresa"] == "info@climapirineus.cat"
    assert emails["email_gatekeeper"] == "j.soler@climapirineus.cat"
    assert emails["email_principal"] == "j.soler@climapirineus.cat"

    # 4. Telèfon real (+34...)
    telefon = _extreure_telefon_de_text(text_net, tels_html=meta["tels"])
    assert telefon in ("+34973620123", "+34654321987")


# ==============================================================================
# TESTS T006: MX SHIELD I DELIVERABILITY DNS
# ==============================================================================

def test_t006_sintaxi_i_dominis_temporals():
    """Verifica la detecció de sintaxi RFC 5322 i el bloqueig de correus descartables."""
    assert validar_sintaxi_email("tecnic@sevalor.net") is True
    assert validar_sintaxi_email("josep.pons+rebt@clima-segria.cat") is True
    assert validar_sintaxi_email("correu_invalid_sense_arroba") is False
    assert validar_sintaxi_email("@sense_usuari.cat") is False

    assert es_domini_temporal("mailinator.com") is True
    assert es_domini_temporal("yopmail.com") is True
    assert es_domini_temporal("clima-segria.cat") is False


@pytest.mark.asyncio
async def test_t006_validacio_mx_shield_completa(db_session: AsyncSession):
    """Verifica la validació asíncrona de registres DNS MX i exclusió RGPD."""
    suffix = uuid.uuid4().hex[:8]
    domini_bloquejat = f"bloqueig-{suffix}.com"

    # Afegir a llista negra RGPD
    exclusio = SaasExclusioRgpd(
        id=uuid.uuid4(),
        email=f"info@{domini_bloquejat}",
        domini=domini_bloquejat,
        motiu="OPTOUT_EXPLICIT",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(exclusio)
    await db_session.flush()

    # 1. Comprovació de domini temporal bloquejat
    es_val, motiu = await validar_email_mx("test@mailinator.com", db=db_session)
    assert es_val is False
    assert motiu == "DOMINI_TEMPORAL"

    # 2. Comprovació de domini bloquejat a RGPD
    es_val_rgpd, motiu_rgpd = await validar_email_mx(f"info@{domini_bloquejat}", db=db_session)
    assert es_val_rgpd is False
    assert motiu_rgpd == "BLOQUEJAT_RGPD"

    # 3. Comprovació de sintaxi incorrecta
    es_val_bad, motiu_bad = await validar_email_mx("no-es-un-email", db=db_session)
    assert es_val_bad is False
    assert motiu_bad == "ERROR_SINTAXI"

    # 4. Comprovació de domini inexistent
    mx_ok, estat_dns, _ = await verificar_registres_dns_mx(f"domini-inventat-{suffix}-xyz123.cat")
    assert mx_ok is False
    assert estat_dns in ("DOMINI_INEXISTENT", "SENSE_REGISTRES_MX", "TIMEOUT_DNS")


# ==============================================================================
# TESTS T007: OPENROUTER, DOBLE BUCLE D'APRENENTATGE I CAMPANYA DE 3 EMAILS
# ==============================================================================

@pytest.mark.asyncio
async def test_t007_doble_bucle_aprenentatge_context(db_session: AsyncSession):
    """Verifica la càrrega del context de retroalimentació (descarts humans + tancaments lookalike)."""
    now = datetime.now(timezone.utc)
    suffix = uuid.uuid4().hex[:8]

    # Regla Bucle 1: Descart humà
    f1 = SaasCriteriFeedback(
        id=uuid.uuid4(),
        tipus_aprenentatge="CORRECCIO_DESCART",
        vertical="ElectricPro",
        nom_empresa=f"Botiga Llums {suffix}",
        resum_evidencies_o_requisits="Venda de material elèctric al detall.",
        decisio_humana_correcta="DESCARTAT",
        explicacio_humana_o_rao_exit="Sense instal·ladors al carrer, només mostrador.",
        actiu=True,
        created_at=now,
    )
    # Regla Bucle 2: Tancament d'èxit replicable
    f2 = SaasCriteriFeedback(
        id=uuid.uuid4(),
        tipus_aprenentatge="TANCAMENT_EXIT_REPLICABLE",
        vertical="ElectricPro",
        nom_empresa=f"Instal·lacions {suffix} SL",
        resum_evidencies_o_requisits="Empresa d'electricitat terciària amb 10 operaris i manteniment 24h.",
        decisio_humana_correcta="GUANYAT_REPLICABLE",
        explicacio_humana_o_rao_exit="Van comprar perquè la PWA els permet signar albarans d'urgència en 30s.",
        es_replicable=True,
        actiu=True,
        created_at=now,
    )
    db_session.add_all([f1, f2])
    await db_session.flush()

    ctx = await carregar_context_doble_bucle("ElectricPro", db_session)
    assert len(ctx["regles_descart"]) >= 1
    assert any("Sense instal·ladors" in r["motiu_descart_huma"] for r in ctx["regles_descart"])
    assert len(ctx["casos_exit_replicables"]) >= 1
    assert any("signar albarans" in c["rao_tancament_exit"] for c in ctx["casos_exit_replicables"])


@pytest.mark.asyncio
async def test_t007_qualificacio_i_campanya_3_emails_sense_whatsapp(db_session: AsyncSession):
    """Verifica la qualificació d'un prospecte, la generació dels 3 correus amb tempo i la prohibició de WhatsApp."""
    eval_result = await qualificar_candidat_amb_openrouter(
        nom_empresa="Clima i Fred Ponent SL",
        web_url="https://climafredponent.cat",
        codi_postal="25001",
        vertical="Manteniment de Climatització i Fred Industrial",
        operaris_minims=5,
        web_markdown="Empresa instal·ladora de fred industrial amb servei 24 hores i manteniment d'edificis.",
        fonts_investigades=["web", "linkedin", "instagram"],
        fita_recent="Renovació integral de la flota amb 8 noves furgonetes elèctriques",
        gatekeeper_hints={"carrec": "Gerent", "context": "Antoni Vidal"},
        db=db_session,
    )

    assert isinstance(eval_result, LeadEvaluationSchema)
    assert eval_result.estat_decisio == "SELECCIONAT"
    assert eval_result.score >= 70
    assert eval_result.operaris_estimats >= 5

    # Verificació de la campanya de 3 correus
    campanya = eval_result.campanya_3_emails
    assert len(campanya) == 3
    assert [c.pas for c in campanya] == [1, 2, 3]
    assert [c.tempo_offset_dies for c in campanya] == [0, 4, 8]

    # NORMA SUPREMA: PROHIBIT ESMENTAR 'WHATSAPP'
    for correu in campanya:
        text_combinat = (correu.assumpte + " " + correu.cos_text).lower()
        assert "whatsapp" not in text_combinat, "Error greu: S'ha trobat la paraula prohibida 'WhatsApp'."
        assert ("telegram" in text_combinat or "pwa" in text_combinat or "sevalor" in text_combinat)


# ==============================================================================
# TESTS T008: CALENDARI COMERCIAL, HITL I PAUSA PER RESPOSTA INBOUND
# ==============================================================================

@pytest.mark.asyncio
async def test_t008_programacio_calendari_i_enllaçat_threads(db_session: AsyncSession):
    """Verifica que els 3 correus es programen al Calendari i que el pas 2 i 3 enllacen amb In-Reply-To."""
    suffix = uuid.uuid4().hex[:8]
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    lead = SaasLead(
        id=lead_id,
        nom_empresa=f"Electricitat Segrià {suffix} SL",
        nom_contacte="Miquel Bosch",
        email=f"miquel_{suffix}@segriaelec.cat",
        vertical="ElectricPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    campanya = [
        EmailStepSchema(pas=1, tempo_offset_dies=0, assumpte="Pas 1: Salutació", cos_text="Cos pas 1 mínim 20 caràcters."),
        EmailStepSchema(pas=2, tempo_offset_dies=4, assumpte="Pas 2: Cas d'èxit", cos_text="Cos pas 2 mínim 20 caràcters."),
        EmailStepSchema(pas=3, tempo_offset_dies=8, assumpte="Pas 3: Demo 7 dies", cos_text="Cos pas 3 mínim 20 caràcters."),
    ]

    missatges = await programar_campanya_3_emails(
        lead_id=lead_id,
        campanya=campanya,
        db=db_session,
        data_base=now,
    )

    assert len(missatges) == 3
    # Comprovar dates programades (0, 4 i 8 dies)
    assert missatges[0].tempo_dies_offset == 0
    assert missatges[1].tempo_dies_offset == 4
    assert missatges[2].tempo_dies_offset == 8
    assert all(m.estat_enviament == "ESBORRANY_PROGRAMAT" for m in missatges)

    # Comprovar enllaç RFC 5322 In-Reply-To per al fil de conversa
    msg1_id = missatges[0].message_id
    assert missatges[0].in_reply_to is None
    assert missatges[1].in_reply_to == msg1_id
    assert missatges[2].in_reply_to == msg1_id

    # Comprovar que s'ha afegit el peu legal RGPD B2B
    assert "Art. 19 de la LOPDGDD" in missatges[0].cos_text


@pytest.mark.asyncio
async def test_t008_enviament_hitl_i_auditoria(db_session: AsyncSession):
    """Verifica que un correu només s'envia sota aprovació humana (HITL) i deixa traça a activitats."""
    suffix = uuid.uuid4().hex[:8]
    lead_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    lead = SaasLead(
        id=lead_id,
        nom_empresa=f"Climatització {suffix} SL",
        nom_contacte="Oriol Roig",
        email=f"oriol_{suffix}@clima.cat",
        vertical="ClimaPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    correu = SaasCorreuMissatge(
        id=msg_id,
        lead_id=lead_id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=1,
        tempo_dies_offset=0,
        data_programada=now,
        direccio="OUTBOUND",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent="tecnic@sevalor.net",
        destinatari=lead.email,
        assumpte="Proposta de col·laboració tècnica",
        cos_text="Hola Oriol, us presentem la solució Sevalor.",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=now,
    )
    db_session.add(correu)
    await db_session.flush()

    # Execució de l'acció HITL d'aprovació
    enviat = await aprovar_i_enviar_correu_calendari(
        correu_id=msg_id,
        db=db_session,
        aprovat_per_id=admin_id,
    )

    assert enviat.estat_enviament == "APROVAT_ENVIAT"
    assert enviat.sent_at is not None
    assert enviat.aprovat_per_id == admin_id

    # Comprovar registre a la línia de temps
    stmt_act = select(SaasActivitatLead).where(SaasActivitatLead.lead_id == lead_id)
    res_act = await db_session.execute(stmt_act)
    acts = res_act.scalars().all()
    assert any(a.tipus == "EMAIL" for a in acts)


@pytest.mark.asyncio
async def test_t008_pausa_sequencia_i_inbound_objeccio_temps(db_session: AsyncSession):
    """Verifica que una resposta entrant pausa automàticament els correus pendents i agenda un seguiment."""
    suffix = uuid.uuid4().hex[:8]
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    email_client = f"gerent_{suffix}@empresa.cat"

    lead = SaasLead(
        id=lead_id,
        nom_empresa=f"Empresa Test {suffix} SL",
        nom_contacte="Sergi Grau",
        email=email_client,
        vertical="ElectricPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    # Correu 1 enviat
    msg1_id_str = f"<{uuid.uuid4().hex}@sevalor.net>"
    m1 = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lead_id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=1,
        tempo_dies_offset=0,
        data_programada=now - timedelta(days=2),
        direccio="OUTBOUND",
        estat_enviament="APROVAT_ENVIAT",
        remitent="tecnic@sevalor.net",
        destinatari=email_client,
        assumpte="Contacte inicial",
        cos_text="Hola Sergi...",
        message_id=msg1_id_str,
        created_at=now - timedelta(days=2),
    )
    # Correus 2 i 3 programats al Calendari per a dies futurs
    m2 = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lead_id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=2,
        tempo_dies_offset=4,
        data_programada=now + timedelta(days=2),
        direccio="OUTBOUND",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent="tecnic@sevalor.net",
        destinatari=email_client,
        assumpte="Seguiment 1",
        cos_text="Hola Sergi...",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        in_reply_to=msg1_id_str,
        created_at=now,
    )
    m3 = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lead_id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=3,
        tempo_dies_offset=8,
        data_programada=now + timedelta(days=6),
        direccio="OUTBOUND",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent="tecnic@sevalor.net",
        destinatari=email_client,
        assumpte="Seguiment 2",
        cos_text="Hola Sergi...",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        in_reply_to=msg1_id_str,
        created_at=now,
    )
    db_session.add_all([m1, m2, m3])
    await db_session.flush()

    # Entra una resposta del client amb una objecció de temps: "Parleu-nos el mes que ve"
    resposta = await processar_resposta_inbound(
        remitent=email_client,
        assumpte="Re: Contacte inicial",
        cos_text="Hola, ara estem en plena campanya d'obres. Si us plau parleu-nos el mes que ve.",
        in_reply_to=msg1_id_str,
        db=db_session,
    )

    assert resposta.direccio == "INBOUND"
    assert resposta.intencio_ia == "OBJECCIO_TEMPS"

    # Comprovar que m2 i m3 s'han pausat immediatament
    stmt_pendents = select(SaasCorreuMissatge).where(
        SaasCorreuMissatge.lead_id == lead_id,
        SaasCorreuMissatge.direccio == "OUTBOUND",
    )
    res_p = await db_session.execute(stmt_pendents)
    tots_outbound = res_p.scalars().all()
    outbound_futurs = [m for m in tots_outbound if m.pas_sequencia in (2, 3)]
    assert all(m.estat_enviament == "PAUSAT_PER_RESPOSTA" for m in outbound_futurs)

    # Comprovar que s'ha creat l'esdeveniment SEGUIMENT_CALENDARI al Calendari Comercial
    stmt_seg = select(SaasCorreuMissatge).where(
        SaasCorreuMissatge.lead_id == lead_id,
        SaasCorreuMissatge.tipus_item_calendari == "SEGUIMENT_CALENDARI",
    )
    res_seg = await db_session.execute(stmt_seg)
    seguiment = res_seg.scalars().first()
    assert seguiment is not None
    assert seguiment.data_programada > now


@pytest.mark.asyncio
async def test_t008_inbound_baixa_optout_rgpd(db_session: AsyncSession):
    """Verifica que una resposta de baixa afegeix el domini a `saas_exclusio_rgpd` i descarta el lead."""
    suffix = uuid.uuid4().hex[:8]
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    email_client = f"baixa_{suffix}@empresa-baixa.cat"

    lead = SaasLead(
        id=lead_id,
        nom_empresa=f"Empresa Baixa {suffix} SL",
        nom_contacte="Pau Casals",
        email=email_client,
        vertical="CampoPro",
        created_at=now,
        updated_at=now,
    )
    db_session.add(lead)
    await db_session.flush()

    correu_futur = SaasCorreuMissatge(
        id=uuid.uuid4(),
        lead_id=lead_id,
        tipus_item_calendari="EMAIL_CAMPANYA",
        pas_sequencia=2,
        tempo_dies_offset=4,
        data_programada=now + timedelta(days=4),
        direccio="OUTBOUND",
        estat_enviament="ESBORRANY_PROGRAMAT",
        remitent="tecnic@sevalor.net",
        destinatari=email_client,
        assumpte="Seguiment programat",
        cos_text="Hola Pau...",
        message_id=f"<{uuid.uuid4().hex}@sevalor.net>",
        created_at=now,
    )
    db_session.add(correu_futur)
    await db_session.flush()

    # Processar petició expressa de baixa (i verificar idempotència si arriba per duplicat)
    resposta = await processar_resposta_inbound(
        remitent=email_client,
        assumpte="Re: Informació",
        cos_text="Sol·licitem la baixa immediata de les vostres comunicacions segons la LOPD.",
        in_reply_to=None,
        db=db_session,
    )

    assert resposta.intencio_ia == "BAIXA_OPTOUT"

    # Verificar que el correu programat al Calendari s'ha CANCEL_LAT definitivament
    res_cal = await db_session.execute(
        select(SaasCorreuMissatge).where(SaasCorreuMissatge.id == correu_futur.id)
    )
    assert res_cal.scalar_one().estat_enviament == "CANCEL_LAT"

    # Verificar que el domini s'ha guardat a saas_exclusio_rgpd
    stmt_excl = select(SaasExclusioRgpd).where(SaasExclusioRgpd.email == email_client)
    res_excl = await db_session.execute(stmt_excl)
    excl = res_excl.scalars().first()
    assert excl is not None
    assert excl.motiu == "OPTOUT_EXPLICIT"

    # Verificar que el lead ha passat a DESCARTAT
    stmt_lead = select(SaasLead).where(SaasLead.id == lead_id)
    res_lead = await db_session.execute(stmt_lead)
    lead_actualitzat = res_lead.scalars().first()
    assert lead_actualitzat is not None
    assert lead_actualitzat.estat_qualificacio == "DESCARTAT"


@pytest.mark.asyncio
async def test_t007_resiliencia_schema_llm_i_openrouter_payload():
    """Verifica que LeadEvaluationSchema normalitza toleradament respostes de l'LLM amb camps absents o alternatius."""
    # Cas 1: Payload de l'error real de CampoPro amb camps 'empresa' i 'campanya_emails' sense operaris_estimats ni motiu_detallat_ia
    payload_error_campopro = {
        "empresa": "CampoPro",
        "campanya_emails": [],
    }
    schema_campopro = LeadEvaluationSchema.model_validate(payload_error_campopro)
    assert schema_campopro.operaris_estimats >= 0
    assert len(schema_campopro.motiu_detallat_ia) >= 10
    assert "CampoPro" in schema_campopro.motiu_detallat_ia
    assert schema_campopro.campanya_3_emails == []

    # Cas 2: Payload amb camps alternatius ('operaris', 'justificacio', 'campanya_emails', 'subject', 'body')
    payload_alternatiu = {
        "empresa": "CampoPro Instal·lacions SL",
        "operaris": "14",
        "justificacio": "Empresa agrícola i de reg amb quadrilles actives al terreny",
        "estat": "SELECCIONAT",
        "score": 82,
        "campanya_emails": [
            {
                "subject": "Optimització de reg per a CampoPro",
                "body": "Hola equip directiu,\n\nUs contactem des de Sevalor Suite per connectar furgonetes i oficina via Telegram.",
            }
        ],
    }
    schema_alt = LeadEvaluationSchema.model_validate(payload_alternatiu)
    assert schema_alt.operaris_estimats == 14
    assert schema_alt.estat_decisio == "SELECCIONAT"
    assert schema_alt.score == 82
    assert "reg" in schema_alt.motiu_detallat_ia
    assert len(schema_alt.campanya_3_emails) == 1
    assert schema_alt.campanya_3_emails[0].pas == 1
    assert schema_alt.campanya_3_emails[0].tempo_offset_dies == 0
    assert schema_alt.campanya_3_emails[0].assumpte == "Optimització de reg per a CampoPro"
    assert "Sevalor Suite" in schema_alt.campanya_3_emails[0].cos_text


@pytest.mark.asyncio
async def test_t007_openrouter_reintent_429_i_recuperacio(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """Verifica que si OpenRouter retorna 429 pel proveïdor preferent, es reintenta automàticament sense restricció de proveïdor."""
    comptador = 0

    async def mock_post(self, url, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal comptador
        comptador += 1
        if comptador == 1:
            # Simulació del codi 429 d'upstream Baidu
            return httpx.Response(
                status_code=429,
                json={
                    "error": {
                        "message": "Provider returned error",
                        "code": 429,
                        "metadata": {"raw": "deepseek/deepseek-v4.1-flash is temporarily rate-limited upstream", "provider_name": "Baidu"},
                    }
                },
            )
        else:
            # Reintent reeixit amb deepseek-chat i payload normalitzat
            return httpx.Response(
                status_code=200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({
                                    "empresa": "CampoPro",
                                    "decisor_nom": "Miquel Utgé",
                                    "decisor_carrec": "Gerent",
                                    "operaris": 12,
                                    "justificacio": "Empresa agrícola idònia per a Sevalor Suite",
                                    "estat": "SELECCIONAT",
                                    "score": 85,
                                    "campanya_emails": [
                                        {
                                            "pas": 1,
                                            "tempo_offset_dies": 0,
                                            "assumpte": "Optimització agrícola",
                                            "cos_text": "Hola equip directiu,\n\nUs contactem des de Sevalor Suite via Telegram.",
                                        }
                                    ],
                                })
                            }
                        }
                    ]
                },
            )

    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-real-key-for-test")
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    resultat = await qualificar_candidat_amb_openrouter(
        nom_empresa="CampoPro",
        web_url="https://campopro.cat",
        codi_postal="25001",
        vertical="Agricultura i Reg",
        operaris_minims=5,
        web_markdown="Empresa agrícola i de reg amb quadrilles al terreny.",
        fonts_investigades=["web"],
        fita_recent=None,
        gatekeeper_hints={"nom": "Miquel Utgé", "carrec": "Gerent"},
        db=db_session,
    )

    assert comptador == 2, "Hauria d'haver fet 2 intents: primer fallada 429 i segon reintent sense restricció"
    assert isinstance(resultat, LeadEvaluationSchema)
    assert resultat.estat_decisio == "SELECCIONAT"
    assert resultat.operaris_estimats == 12
    assert resultat.score == 85
    assert len(resultat.campanya_3_emails) == 1


@pytest.mark.asyncio
async def test_t007_arquitectura_multi_agent_i_orquestrador(db_session: AsyncSession):
    """Verifica el flux complet de l'Arquitectura Multi-Agent (Agent 1, Agent 2, Agent 3 i Orquestrador)."""
    from app.services.prospeccio_agents_service import prospeccio_orchestrator

    # 1. Candidat òptim amb Gatekeeper, contacte operatiu i xarxes socials
    item_optim = {
        "nom_empresa": "Solar i Reg del Pallars SL",
        "web_url": "https://solarpallars.cat",
        "adreca_fisica": "Polígon Industrial Els Raiers, Nau 7, 25500 La Pobla de Segur",
        "cif": "B25889900",
        "email": "gerencia@solarpallars.cat",
        "telefon": "+34655443322",
        "decisor_nom": "Arnau Subirà",
        "decisor_carrec": "Director Tècnic",
        "linkedin_url": "https://www.linkedin.com/company/solarpallars",
        "instagram_url": "https://www.instagram.com/solarpallars/",
        "web_markdown": (
            "Solar i Reg del Pallars SL disposa de 12 tècnics instal·ladors de camp per a bombament solar "
            "i automatització de reg agrícola a la comarca del Pallars."
        ),
        "fita_recent": "Nova adjudicació de bombament solar de 150 kWp a la Conca de Tremp",
    }

    res_optim = await prospeccio_orchestrator.executar_pipeline_candidat(
        item_candidat=item_optim,
        codi_postal="25500",
        vertical="Energia Solar i Reg Agrícola",
        operaris_minims=5,
        municipi_esperat="La Pobla de Segur",
        db=db_session,
    )

    assert res_optim.agent1.passa_tallafocs_1 is True
    assert res_optim.agent1.gatekeeper_nom == "Arnau Subirà"
    assert res_optim.agent1.te_contacte_operatiu is True
    assert res_optim.agent2.passa_tallafocs_2 is True
    assert res_optim.agent2.operaris_estimats == 12
    assert any("linkedin|" in f for f in res_optim.agent3.fonts_investigades)
    assert any("instagram|" in f for f in res_optim.agent3.fonts_investigades)
    assert res_optim.avaluacio_final.estat_decisio == "SELECCIONAT"
    assert res_optim.avaluacio_final.decisor_nom == "Arnau Subirà"
    assert len(res_optim.avaluacio_final.campanya_3_emails) == 3
    assert "Arnau Subirà" in res_optim.avaluacio_final.campanya_3_emails[0].cos_text
    assert all("whatsapp" not in c.cos_text.lower() for c in res_optim.avaluacio_final.campanya_3_emails)

    # 2. Candidat botiga al detall -> Descartat per Agent 2 (Tallafocs 2)
    item_botiga = {
        "nom_empresa": "Botiga Venda Detall Solar Pallars SL",
        "web_url": "https://botigasolarpallars.cat",
        "adreca_fisica": "Av. Verdaguer 10, 25500 La Pobla de Segur",
        "email": "info@botigasolarpallars.cat",
        "telefon": "+34973680011",
        "web_markdown": "Botiga de venda al detall de bateries i material elèctric de mostrador.",
    }

    res_botiga = await prospeccio_orchestrator.executar_pipeline_candidat(
        item_candidat=item_botiga,
        codi_postal="25500",
        vertical="Energia Solar",
        operaris_minims=5,
        municipi_esperat="La Pobla de Segur",
        db=db_session,
    )
    assert res_botiga.agent2.es_botiga_detall is True
    assert res_botiga.agent2.passa_tallafocs_2 is False
    assert res_botiga.avaluacio_final.estat_decisio == "DESCARTAT"
    assert res_botiga.avaluacio_final.campanya_3_emails == []


@pytest.mark.asyncio
async def test_t007_curtcircuit_fast_fail_orquestrador(db_session: AsyncSession) -> None:
    """Verifica el Curtcircuit (Fast-Fail) a l'Orquestrador Multi-Agent per estalviar cerques i LLM."""
    from app.services.prospeccio_agents_service import prospeccio_orchestrator

    # 1. Curtcircuit 1: Falla Quality Gate 1 per ubicació aliena (Madrid vs Lleida 25001)
    res_cc1 = await prospeccio_orchestrator.processar_candidat_complet(
        nom_empresa="Instal·lacions Centro Madrid SL",
        web_url="https://centromadrid.es",
        codi_postal="25001",
        municipi="Lleida",
        vertical="ElectricPro",
        operaris_minims=5,
        dades_inicials={
            "adreca_fisica": "Paseo de la Castellana 100, 28046 Madrid",
            "email": "madrid@centromadrid.es",
            "telefon": "+34912345678",
            "web_markdown": "Instal·lacions d'alta tensió a la comunitat de Madrid.",
        },
        db=db_session,
    )

    assert res_cc1["avaluacio"].estat_decisio == "DESCARTAT"
    assert res_cc1["avaluacio"].score == 20
    assert "Quality Gate 1" in res_cc1["avaluacio"].motiu_detallat_ia
    assert res_cc1["fita_recent"] is None
    assert res_cc1["avaluacio"].campanya_3_emails == []

    # 2. Curtcircuit 2: Falla Agent 2 per botiga física / venda al detall de mostrador
    res_cc2 = await prospeccio_orchestrator.processar_candidat_complet(
        nom_empresa="Ferreteria i Botiga Lleida SL",
        web_url="https://botigalleida.cat",
        codi_postal="25001",
        municipi="Lleida",
        vertical="ElectricPro",
        operaris_minims=5,
        dades_inicials={
            "adreca_fisica": "Carrer Major 12, 25001 Lleida",
            "email": "vendes@botigalleida.cat",
            "telefon": "+34973223344",
            "web_markdown": "Botiga de mostrador i venda al detall de subministraments elèctrics.",
        },
        db=db_session,
    )

    assert res_cc2["avaluacio"].estat_decisio == "DESCARTAT"
    assert res_cc2["avaluacio"].score == 25
    assert "Agent 2" in res_cc2["avaluacio"].motiu_detallat_ia
    assert res_cc2["avaluacio"].punt_dolor == "Model enfocat a botiga física / mostrador sense tècnics de camp"
    assert res_cc2["avaluacio"].campanya_3_emails == []

    # 3. Candidat Viable: Passa Gate 1 i Gate 2, executa Agent 3 i genera els correus
    res_viable = await prospeccio_orchestrator.processar_candidat_complet(
        nom_empresa="Electrotècnia del Segre SL",
        web_url="https://electrotecniasegre.cat",
        codi_postal="25001",
        municipi="Lleida",
        vertical="ElectricPro",
        operaris_minims=5,
        dades_inicials={
            "adreca_fisica": "Polígon El Segre, Carrer Indústria 5, 25001 Lleida",
            "email": "contacte@electrotecniasegre.cat",
            "telefon": "+34973556677",
            "decisor_nom": "Jordi Farré",
            "decisor_carrec": "Director Tècnic",
            "fonts_urls": {"linkedin": "https://linkedin.com/company/electrotecnia-segre"},
            "web_markdown": (
                "Electrotècnia del Segre SL compta amb 8 operaris qualificats per a manteniments i quadres elèctrics "
                "industrials a la demarcació de Lleida."
            ),
            "fita_recent": "Certificació ISO 9001 i nou contracte amb el Parc Científic de Lleida",
        },
        db=db_session,
    )

    assert res_viable["avaluacio"].estat_decisio == "SELECCIONAT"
    assert res_viable["avaluacio"].score >= 65
    assert len(res_viable["avaluacio"].campanya_3_emails) == 3
    assert all("whatsapp" not in c.cos_text.lower() for c in res_viable["avaluacio"].campanya_3_emails)





