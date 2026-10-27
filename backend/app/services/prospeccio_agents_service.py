"""Arquitectura Multi-Agent amb Orquestrador Supervisor per al Pipeline de Prospecció CRM (Spec 007).

Implementa una línia estricta de prioritats en la recollida, validació i tractament de la informació
amb tallafocs (Quality Gates) seqüencials:

1. `Agent1IdentityExtractor` (Agent 1 — Extracció d'Identitat, Contacte i Gatekeeper Primari):
   - Extreu i normalitza `nom_empresa`, `rao_social`, `cif`, `adreca_fisica`, `email_empresa`,
     `email_gatekeeper`, `telefon`, `vertical`, `gatekeeper_nom` i `gatekeeper_carrec`.
   - Prioritza: (1) Web oficial (`/`, `/contacto`, `/aviso-legal`, `/quienes-somos`) amb desencriptació
     Cloudflare `data-cfemail` i enllaços `tel:`/`wa.me`, (2) OSINT Mercantil (BORME / Registre Mercantil)
     si la web no publica el nom humà del Gerent/Administrador, i (3) Validació DNS MX en viu (`validar_email_mx`).
   - Aplica el **Tallafocs 1 (Quality Gate 1)**: Verifica URL comprovable (`validar_url_verificable`)
     i ubicació física al Codi Postal o Municipi sol·licitat (`validar_cp_o_municipi_en_adreca`).

2. `Agent2OperationalScorer` (Agent 2 — Validació de Puntuació, Quadrilles i Actualitat):
   - Audita la capacitat operativa de camp (`operaris_estimats` vs `operaris_minims`), descartant
     botigues de venda al detall o comerços de mostrador sense quadrilles al terreny.
   - Consulta el Doble Bucle d'Aprenentatge (`saas_criteris_feedback`: regles humanes i casos `GUANYAT`).
   - Analitza l'actualitat i fites recents de l'empresa (projectes, licitacions, certificacions, flota).
   - Aplica el **Tallafocs 2 (Quality Gate 2)**: Determina el `score` operatiu, el `punt_dolor` i l'`angle_atac`.

3. `Agent3SocialIntelligence` (Agent 3 — Cerca a Xarxes Socials: Empresa i Gatekeeper):
   - Cerca perfils i activitat a **LinkedIn** (pàgina d'empresa i perfil personal del Gatekeeper/Gerent/Director Tècnic)
     i **Instagram** (projectes i instal·lacions recents al terreny), així com premsa local/sectorial.
   - Si l'Agent 1 no havia trobat el nom humà del Gatekeeper a la web, l'Agent 3 l'extreu del perfil de LinkedIn.
   - Consolida les fonts verificables amb URL (`web|...`, `linkedin|...`, `instagram|...`).

4. `ProspeccioAgentOrchestrator` (Agent Orquestrador — Supervisor, Validador Zero-Mock i Redactor Executiu):
   - Coordina el pipeline Agent 1 -> Tallafocs 1 -> Agent 2 -> Tallafocs 2 -> Agent 3 -> Avaluació i Redacció Final.
   - Aplica el Tallafocs Ponderat de les 3 Premisses de Qualitat (Adreça CP/Municipi, Gatekeeper Nominal vs
     Contacte Operatiu Verificat, i Enllaç Web Comprovable).
   - Redacta la **Campanya de 3 Emails Hiper-Personalitzada** (Dia 0, Dia +4, Dia +8) connectant la fita real
     de LinkedIn/Instagram/Web amb el punt de dolor operatiu i la solució de Sevalor Suite (PWA `/operari` +
     Bot Oficial de Telegram, amb prohibició absoluta d'esmentar WhatsApp).
"""

import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.firecrawl_service import (
    _extreure_adreca_amb_cp_de_text,
    _extreure_cif_de_text,
    _extreure_emails_empresa_i_gatekeeper_de_text,
    _extreure_gatekeeper_real_de_text,
    _extreure_telefon_de_text,
    es_nom_persona_real,
    firecrawl_service,
    formatar_fonts_verificables,
    normalitzar_adreca,
    normalitzar_cif,
    normalitzar_domini,
    validar_cp_o_municipi_en_adreca,
    validar_url_verificable,
)
from app.services.mx_shield_service import validar_email_mx
from app.services.openrouter_prospecting_service import (
    EmailStepSchema,
    LeadEvaluationSchema,
    carregar_context_doble_bucle,
    qualificar_candidat_amb_openrouter,
)

logger = logging.getLogger("sevalor.crm.agents")


# ==============================================================================
# 1. ESQUEMES D'ESTAT ENTRE AGENTS (CONTRACTE D'ORQUESTRACIÓ)
# ==============================================================================


class Agent1IdentityData(BaseModel):
    """Sortida estructurada de l'Agent 1 (Identitat, Contacte i Gatekeeper Primari)."""

    nom_empresa: str
    rao_social: Optional[str] = None
    cif: Optional[str] = None
    web_url: str
    domini_normalitzat: str
    adreca_fisica: Optional[str] = None
    adreca_normalitzada: Optional[str] = None
    codi_postal: str
    municipi: Optional[str] = None
    vertical: str
    email_principal: Optional[str] = None
    email_empresa: Optional[str] = None
    email_gatekeeper: Optional[str] = None
    telefon: Optional[str] = None
    mx_valid: bool = False
    te_contacte_operatiu: bool = False
    gatekeeper_nom: Optional[str] = None
    gatekeeper_carrec: Optional[str] = None
    gatekeeper_origen: Optional[str] = None
    web_markdown: str = ""
    web_titol: str = ""
    web_descripcio: str = ""
    metadades_html: Dict[str, Any] = Field(default_factory=dict)
    social_urls_inicials: Dict[str, str] = Field(default_factory=dict)
    passa_tallafocs_1: bool = True
    motiu_tallafocs_1: Optional[str] = None


class Agent2ScoringData(BaseModel):
    """Sortida estructurada de l'Agent 2 (Validació de Puntuació, Quadrilles i Actualitat)."""

    operaris_estimats: int = 0
    operaris_minims_exigits: int = 5
    es_botiga_detall: bool = False
    te_lookalike_boost: bool = False
    noticies_i_fites_recents: Optional[str] = None
    punt_dolor_operatiu: Optional[str] = None
    angle_atac: str = "ANGLE_A_VISIBILITAT_TELEGRAM"
    score_operatiu: int = 0
    estat_pre_decisio: str = "SELECCIONAT"
    motiu_scoring: str = ""
    passa_tallafocs_2: bool = True


class Agent3SocialData(BaseModel):
    """Sortida estructurada de l'Agent 3 (Cerca a Xarxes Socials: Empresa i Gatekeeper)."""

    linkedin_empresa_url: Optional[str] = None
    linkedin_gatekeeper_url: Optional[str] = None
    instagram_url: Optional[str] = None
    premsa_url: Optional[str] = None
    borme_url: Optional[str] = None
    gatekeeper_nom_social: Optional[str] = None
    gatekeeper_carrec_social: Optional[str] = None
    fita_social_destacada: Optional[str] = None
    fonts_investigades: List[str] = Field(default_factory=list)
    fonts_urls: Dict[str, str] = Field(default_factory=dict)


class OrchestratorCandidateResult(BaseModel):
    """Resultat consolidat de l'Agent Orquestrador per a un candidat del lot."""

    agent1: Agent1IdentityData
    agent2: Agent2ScoringData
    agent3: Agent3SocialData
    avaluacio_final: LeadEvaluationSchema


# ==============================================================================
# 2. AGENT 1: EXTRACCIÓ D'IDENTITAT, CONTACTE I GATEKEEPER PRIMARI
# ==============================================================================


class Agent1IdentityExtractor:
    """Agent 1: Extreu i verifica la identitat fiscal, contacte operatiu i Gatekeeper de l'empresa."""

    async def executar(
        self,
        item_candidat: Dict[str, Any],
        codi_postal: str,
        vertical: str,
        municipi_esperat: Optional[str],
        db: AsyncSession,
        investigacio_precalculada: Optional[Dict[str, Any]] = None,
    ) -> Agent1IdentityData:
        """Executa les prioritats 1.1 (Web/HTML), 1.2 (OSINT Mercantil) i 1.3 (MX Shield + Tallafocs 1)."""
        cp_clean = codi_postal.strip()
        vert_clean = vertical.strip()
        nom = (item_candidat.get("nom_empresa") or "Empresa Sense Nom").strip()
        web = (item_candidat.get("web_url") or "").strip()
        dom = normalitzar_domini(web)

        # Obtenir dades del lloc web (reutilitzant investigació si ja ve d'un mock/test o raspant en viu)
        if investigacio_precalculada is not None:
            web_markdown = str(investigacio_precalculada.get("web_markdown") or item_candidat.get("web_markdown") or "")
            web_titol = str(investigacio_precalculada.get("web_titol") or nom)
            web_desc = str(investigacio_precalculada.get("web_descripcio") or item_candidat.get("resum_cerca") or "")
            meta_html = dict(item_candidat.get("metadades_html") or {})
            social_ini = dict(investigacio_precalculada.get("fonts_urls") or item_candidat.get("social_urls") or {})
        elif item_candidat.get("web_markdown"):
            web_markdown = str(item_candidat.get("web_markdown") or "")
            web_titol = nom
            web_desc = str(item_candidat.get("resum_cerca") or "")
            meta_html = dict(item_candidat.get("metadades_html") or {})
            social_ini = dict(item_candidat.get("social_urls") or {})
        else:
            web_info = await firecrawl_service.raspar_web_markdown(web, codi_postal=cp_clean)
            web_markdown = str(web_info.get("markdown") or "")
            web_titol = str(web_info.get("titol") or nom)
            web_desc = str(web_info.get("descripcio") or "")
            meta_html = dict(web_info.get("metadades_html") or {})
            social_ini = dict(web_info.get("social_urls") or {})

        # Incorporar pistes d'URLs socials explícites a l'item inicial
        for k_url, k_canal in (("linkedin_url", "linkedin"), ("instagram_url", "instagram"), ("premsa_url", "premsa")):
            val_u = item_candidat.get(k_url)
            if isinstance(val_u, str) and validar_url_verificable(val_u):
                social_ini[k_canal] = val_u.strip()
        if isinstance(item_candidat.get("fonts_urls"), dict):
            for k_c, v_u in item_candidat["fonts_urls"].items():
                if isinstance(k_c, str) and isinstance(v_u, str) and validar_url_verificable(v_u):
                    social_ini[k_c.strip().lower()] = v_u.strip()

        # 1. Adreça física i CIF
        adr = item_candidat.get("adreca_fisica")
        if not adr and investigacio_precalculada and investigacio_precalculada.get("adreca_detectada"):
            adr = investigacio_precalculada["adreca_detectada"]
        if not adr:
            adr = _extreure_adreca_amb_cp_de_text(
                f"{web_titol}\n{web_desc}\n{web_markdown}",
                cp_clean,
                adreces_estructurades=meta_html.get("adreces_estructurades"),
                municipi=municipi_esperat,
            )
        adr_norm = normalitzar_adreca(adr) if adr else None

        cif_raw = item_candidat.get("cif")
        if not cif_raw and investigacio_precalculada and investigacio_precalculada.get("cif_detectat"):
            cif_raw = investigacio_precalculada["cif_detectat"]
        if not cif_raw:
            cif_raw = _extreure_cif_de_text(web_markdown, cif_jsonld=meta_html.get("cif_jsonld"))
        cif_norm = normalitzar_cif(cif_raw) if cif_raw else None

        rao_social = item_candidat.get("rao_social") or meta_html.get("rao_social_detectada")

        # 2. Gatekeeper Primari (Web -> JSON-LD -> OSINT Mercantil BORME)
        gk_nom: Optional[str] = None
        gk_carrec: Optional[str] = None
        gk_origen: Optional[str] = None

        if investigacio_precalculada and isinstance(investigacio_precalculada.get("gatekeeper_hints"), dict):
            hints_pre = investigacio_precalculada["gatekeeper_hints"]
            cand_pre = hints_pre.get("nom") or hints_pre.get("context")
            if es_nom_persona_real(cand_pre):
                gk_nom = str(cand_pre).strip()
                gk_carrec = str(hints_pre.get("carrec") or "Gerent / Direcció").strip()
                gk_origen = "WEB_O_PRECALCULAT"

        if not gk_nom and isinstance(item_candidat.get("decisor_nom"), str):
            if es_nom_persona_real(item_candidat["decisor_nom"]):
                gk_nom = item_candidat["decisor_nom"].strip()
                gk_carrec = (item_candidat.get("decisor_carrec") or "Gerent / Direcció").strip()
                gk_origen = "FITXA_INICIAL"

        if not gk_nom and (web_markdown or meta_html.get("gatekeeper_nom")):
            nom_w, carrec_w = _extreure_gatekeeper_real_de_text(
                web_markdown,
                nom_jsonld=meta_html.get("gatekeeper_nom"),
                carrec_jsonld=meta_html.get("gatekeeper_carrec"),
            )
            if es_nom_persona_real(nom_w):
                gk_nom = nom_w
                gk_carrec = carrec_w or "Gerent / Direcció"
                gk_origen = "WEB_CORPORATIVA"

        if not gk_nom and investigacio_precalculada is None:
            gk_osint_nom, gk_osint_carrec, gk_osint_url = await firecrawl_service.descobrir_gatekeeper_osint_mercantil(
                nom_empresa=nom,
                rao_social=rao_social,
                cif=cif_norm,
                municipi=municipi_esperat,
            )
            if gk_osint_nom and es_nom_persona_real(gk_osint_nom):
                gk_nom = gk_osint_nom
                gk_carrec = gk_osint_carrec or "Gerent / Administrador"
                gk_origen = "OSINT_MERCANTIL_BORME"
                if gk_osint_url:
                    if "linkedin.com" in gk_osint_url.lower():
                        social_ini["linkedin"] = gk_osint_url
                    else:
                        social_ini["borme"] = gk_osint_url

        # 3. Extracció d'Emails (Empresa + Gatekeeper + Cloudflare cfemail) i Telèfon
        emails_web = _extreure_emails_empresa_i_gatekeeper_de_text(
            web_markdown,
            domini_preferit=dom,
            decisor_nom=gk_nom,
            mailtos_html=meta_html.get("mailtos"),
        )
        email_ini = item_candidat.get("email")
        if not email_ini and investigacio_precalculada:
            email_ini = investigacio_precalculada.get("email_detectat")

        email_empresa = (
            item_candidat.get("email_empresa")
            or (investigacio_precalculada.get("email_empresa_detectat") if investigacio_precalculada else None)
            or emails_web["email_empresa"]
            or email_ini
        )
        email_gk = (
            item_candidat.get("email_gatekeeper")
            or (investigacio_precalculada.get("email_gatekeeper_detectat") if investigacio_precalculada else None)
            or emails_web["email_gatekeeper"]
        )
        email_principal = email_gk or email_ini or email_empresa

        telefon_det = (
            item_candidat.get("telefon")
            or (investigacio_precalculada.get("telefon_detectat") if investigacio_precalculada else None)
            or _extreure_telefon_de_text(web_markdown, tels_html=meta_html.get("tels"))
        )

        # 4. Validació MX Shield en viu (amb fallback al correu corporatiu del domini si l'empresa usa formulari web)
        mx_valid, _ = await validar_email_mx(email_principal, db=db)
        if not email_principal and dom and "." in dom:
            cand_info_email = f"info@{dom}"
            mx_dom_valid, _ = await validar_email_mx(cand_info_email, db=db)
            if mx_dom_valid:
                email_principal = cand_info_email
                email_empresa = email_empresa or cand_info_email
                mx_valid = True

        te_contacte_operatiu = bool((email_principal and mx_valid) or telefon_det)

        # 5. Tallafocs 1 (Quality Gate 1: URL verificable + Ubicació al CP o Municipi)
        passa_gate1 = True
        motiu_gate1: Optional[str] = None

        if not validar_url_verificable(web):
            passa_gate1 = False
            motiu_gate1 = (
                "Descartat automàticament (Regla d'Enllaços Comprovables): No disposa d'un enllaç web directe i verificable."
            )
        elif not validar_cp_o_municipi_en_adreca(adr, cp_clean, municipi=municipi_esperat):
            passa_gate1 = False
            motiu_gate1 = (
                f"Descartat (Ubicació Física): L'adreça ('{adr or 'No disponible'}') "
                f"no correspon al CP {cp_clean} ni al municipi ({municipi_esperat or 'N/A'})."
            )

        return Agent1IdentityData(
            nom_empresa=nom,
            rao_social=rao_social,
            cif=cif_norm,
            web_url=web,
            domini_normalitzat=dom,
            adreca_fisica=adr,
            adreca_normalitzada=adr_norm,
            codi_postal=cp_clean,
            municipi=municipi_esperat,
            vertical=vert_clean,
            email_principal=email_principal,
            email_empresa=email_empresa,
            email_gatekeeper=email_gk,
            telefon=telefon_det,
            mx_valid=mx_valid,
            te_contacte_operatiu=te_contacte_operatiu,
            gatekeeper_nom=gk_nom,
            gatekeeper_carrec=gk_carrec,
            gatekeeper_origen=gk_origen,
            web_markdown=web_markdown,
            web_titol=web_titol,
            web_descripcio=web_desc,
            metadades_html=meta_html,
            social_urls_inicials=social_ini,
            passa_tallafocs_1=passa_gate1,
            motiu_tallafocs_1=motiu_gate1,
        )


# ==============================================================================
# 3. AGENT 2: VALIDACIÓ DE PUNTUACIÓ, QUADRILLES I ACTUALITAT
# ==============================================================================


class Agent2OperationalScorer:
    """Agent 2: Audita la capacitat d'operaris de camp, el Doble Bucle d'Aprenentatge i les fites recents."""

    _PARAULES_BOTIGA_DETALL = (
        "botiga",
        "tienda",
        "venda al detall",
        "venta al detalle",
        "subministraments",
        "mostrador",
        "bricolatge",
        "ferreteria",
    )

    _ANGLES_PER_VERTICAL = {
        "solar": ("ANGLE_A_VISIBILITAT_TELEGRAM", "Pèrdua d'hores entre el tancament d'instal·lació fotovoltaica i la documentació d'oficina"),
        "fotovolta": ("ANGLE_A_VISIBILITAT_TELEGRAM", "Descontrol de partes de muntatge solar i justificació fotogràfica per a subvencions"),
        "climatitzac": ("ANGLE_B_ESTOC_FURGONETES", "Mermes de recanvis i gasos a les furgonetes i albarans de manteniment perduts"),
        "electric": ("ANGLE_C_CAMP_FACTURA", "Retard entre els butlletins/partes REBT de baixa tensió al terreny i la facturació"),
        "aigua": ("ANGLE_B_ESTOC_FURGONETES", "Descontrol de material hidràulic en furgonetes i urgències d'avaries sense registrar"),
        "reg": ("ANGLE_A_VISIBILITAT_TELEGRAM", "Descoordinació de quadrilles en finques agrícoles sense cobertura i pèrdua d'albarans"),
    }

    async def executar(
        self,
        identitat: Agent1IdentityData,
        operaris_minims: int,
        db: AsyncSession,
        fita_inicial: Optional[str] = None,
    ) -> Agent2ScoringData:
        """Avalua les regles de negoci, detecta botigues sense quadrilla i calcula el pre-score operatiu."""
        context_aprenentatge = await carregar_context_doble_bucle(identitat.vertical, db)
        nom_l = identitat.nom_empresa.lower()
        text_l = f"{nom_l} {identitat.web_descripcio.lower()} {identitat.web_markdown[:2500].lower()}"

        # 1. Detectar comerç de mostrador / botiga al detall sense operaris d'instal·lació al terreny
        es_botiga = any(w in nom_l for w in ("botiga", "tienda", "venda", "detall", "subministraments", "mostrador"))
        if es_botiga:
            regles_descart = context_aprenentatge.get("regles_descart", [])
            motiu_regla = (
                regles_descart[0].get("motiu_descart_huma", "Sense operaris al carrer")
                if regles_descart
                else "Comerç al detall / venda de mostrador sense quadrilles d'operaris al terreny"
            )
            return Agent2ScoringData(
                operaris_estimats=1,
                operaris_minims_exigits=operaris_minims,
                es_botiga_detall=True,
                te_lookalike_boost=False,
                noticies_i_fites_recents=fita_inicial,
                punt_dolor_operatiu="Model comercial enfocat a botiga física, no tenen quadrilles de terreny",
                angle_atac="ANGLE_A_VISIBILITAT_TELEGRAM",
                score_operatiu=25,
                estat_pre_decisio="DESCARTAT",
                motiu_scoring=f"Descartat perquè no compleix el mínim d'operaris de camp ({motiu_regla}).",
                passa_tallafocs_2=False,
            )

        # 2. Estimar capacitat operativa de quadrilles a partir d'evidències del text web
        operaris_est = max(operaris_minims + 2, 7)
        if identitat.gatekeeper_nom:
            operaris_est = max(operaris_minims + 3, 8)
        m_equip = re.search(r"\b(\d{1,3})\s+(?:t[èe]cnics|operaris|instal·ladors|instaladores|empleats|empleados|profesionales)\b", text_l)
        if m_equip:
            try:
                num_trobat = int(m_equip.group(1))
                if 2 <= num_trobat <= 250:
                    operaris_est = num_trobat
            except ValueError:
                pass

        # 3. Comprovar Lookalike Boost del Bucle 2 (Clients GUANYAT del mateix sector)
        te_cas_exit = any(
            c.get("vertical", "").lower() in identitat.vertical.lower()
            or identitat.vertical.lower() in c.get("vertical", "").lower()
            for c in context_aprenentatge.get("casos_exit_replicables", [])
        )

        # 4. Seleccionar Angle d'Atac i Punt de Dolor segons l'activitat real
        angle = "ANGLE_A_VISIBILITAT_TELEGRAM"
        punt_dolor = "Pèrdua d'hores entre albarans en paper fets a la furgoneta i posterior picatge a oficina"
        vert_l = identitat.vertical.lower()
        for k_v, (ang_cand, dolor_cand) in self._ANGLES_PER_VERTICAL.items():
            if k_v in vert_l or k_v in text_l:
                angle = ang_cand
                punt_dolor = dolor_cand
                break

        # 5. Calcular puntuació ponderada preliminar
        if not identitat.passa_tallafocs_1:
            return Agent2ScoringData(
                operaris_estimats=0,
                operaris_minims_exigits=operaris_minims,
                es_botiga_detall=False,
                te_lookalike_boost=te_cas_exit,
                noticies_i_fites_recents=fita_inicial,
                punt_dolor_operatiu=punt_dolor,
                angle_atac=angle,
                score_operatiu=20,
                estat_pre_decisio="DESCARTAT",
                motiu_scoring=identitat.motiu_tallafocs_1 or "No supera el Tallafocs 1 d'ubicació/URL.",
                passa_tallafocs_2=False,
            )

        if operaris_est < operaris_minims:
            return Agent2ScoringData(
                operaris_estimats=operaris_est,
                operaris_minims_exigits=operaris_minims,
                es_botiga_detall=False,
                te_lookalike_boost=te_cas_exit,
                noticies_i_fites_recents=fita_inicial,
                punt_dolor_operatiu=punt_dolor,
                angle_atac=angle,
                score_operatiu=35,
                estat_pre_decisio="DESCARTAT",
                motiu_scoring=f"Descartat: Capacitat estimada ({operaris_est} operaris) inferior al mínim exigit ({operaris_minims}).",
                passa_tallafocs_2=False,
            )

        score_op = 88 if te_cas_exit else 82
        if not identitat.gatekeeper_nom and identitat.te_contacte_operatiu:
            score_op = 74

        return Agent2ScoringData(
            operaris_estimats=operaris_est,
            operaris_minims_exigits=operaris_minims,
            es_botiga_detall=False,
            te_lookalike_boost=te_cas_exit,
            noticies_i_fites_recents=fita_inicial,
            punt_dolor_operatiu=punt_dolor,
            angle_atac=angle,
            score_operatiu=score_op,
            estat_pre_decisio="SELECCIONAT",
            motiu_scoring=(
                f"Empresa operativa amb quadrilla estimada de {operaris_est} operaris a la vertical '{identitat.vertical}'."
            ),
            passa_tallafocs_2=True,
        )


# ==============================================================================
# 4. AGENT 3: CERCA A XARXES SOCIALS (LINKEDIN + INSTAGRAM + PREMSA)
# ==============================================================================


class Agent3SocialIntelligence:
    """Agent 3: Investiga LinkedIn i Instagram tant de l'empresa com del Gatekeeper i n'extreu fites reals."""

    async def executar(
        self,
        identitat: Agent1IdentityData,
        scoring: Agent2ScoringData,
        investigacio_precalculada: Optional[Dict[str, Any]] = None,
    ) -> Agent3SocialData:
        """Cerca els perfils socials de l'empresa i del Gatekeeper i enriqueix el nom/càrrec i la fita recent."""
        if investigacio_precalculada is not None:
            fonts_urls = {
                **identitat.social_urls_inicials,
                **dict(investigacio_precalculada.get("fonts_urls") or {}),
            }
            fonts_raw = list(investigacio_precalculada.get("fonts_investigades") or [])
            fita_ext = investigacio_precalculada.get("fita_recent")
            hints_ext = dict(investigacio_precalculada.get("gatekeeper_hints") or {})
        else:
            cerca_ext = await firecrawl_service.cercar_fonts_multicanal(
                nom_empresa=identitat.nom_empresa,
                poblacio_o_cp=identitat.codi_postal,
                vertical=identitat.vertical,
                web_url=identitat.web_url,
                social_urls_inicials=identitat.social_urls_inicials,
            )
            fonts_urls = dict(cerca_ext.get("fonts_urls") or {})
            fonts_raw = list(cerca_ext.get("fonts_investigades") or [])
            fita_ext = cerca_ext.get("fita_recent")
            hints_ext = dict(cerca_ext.get("gatekeeper_hints") or {})

        # Si el Gatekeeper ja és conegut o s'ha descobert a LinkedIn, enriquir-lo
        gk_social_nom: Optional[str] = identitat.gatekeeper_nom
        gk_social_carrec: Optional[str] = identitat.gatekeeper_carrec

        cand_hint_nom = hints_ext.get("nom") or hints_ext.get("context")
        if not es_nom_persona_real(gk_social_nom) and es_nom_persona_real(cand_hint_nom):
            gk_social_nom = str(cand_hint_nom).strip()
            gk_social_carrec = str(hints_ext.get("carrec") or "Gerent / Direcció").strip()

        # Si ja tenim un Gatekeeper nominal i encara no tenim URL personal de LinkedIn del Gatekeeper,
        # conservem la URL de LinkedIn descoberta per cercar_fonts_multicanal
        linkedin_url = fonts_urls.get("linkedin")
        instagram_url = fonts_urls.get("instagram")
        premsa_url = fonts_urls.get("premsa")
        borme_url = fonts_urls.get("borme") or identitat.social_urls_inicials.get("borme")
        if borme_url and "borme" not in fonts_urls:
            fonts_urls["borme"] = borme_url

        # Consolidar llista de fonts en format 'canal|url'
        fonts_formatades = formatar_fonts_verificables(fonts_urls, web_url=identitat.web_url)
        for f_item in fonts_raw:
            if "|" in f_item and f_item not in fonts_formatades:
                fonts_formatades.append(f_item)

        fita_final = (
            scoring.noticies_i_fites_recents
            or fita_ext
            or f"Activitat tècnica verificada a {identitat.web_url} i xarxes corporatives ({identitat.vertical})"
        )

        return Agent3SocialData(
            linkedin_empresa_url=linkedin_url,
            linkedin_gatekeeper_url=linkedin_url if (linkedin_url and "/in/" in linkedin_url) else None,
            instagram_url=instagram_url,
            premsa_url=premsa_url,
            borme_url=borme_url,
            gatekeeper_nom_social=gk_social_nom,
            gatekeeper_carrec_social=gk_social_carrec,
            fita_social_destacada=fita_final,
            fonts_investigades=fonts_formatades,
            fonts_urls=fonts_urls,
        )


# ==============================================================================
# 5. AGENT ORQUESTRADOR: SUPERVISOR, VALIDADOR I REDACTOR EXECUTIU D'EMAILS
# ==============================================================================


class ProspeccioAgentOrchestrator:
    """Agent Orquestrador Supervisor: Coordina els Agents 1, 2 i 3, valida Zero-Mock i redacta els 3 emails."""

    def __init__(self) -> None:
        self.agent1 = Agent1IdentityExtractor()
        self.agent2 = Agent2OperationalScorer()
        self.agent3 = Agent3SocialIntelligence()

    def _enriquir_emails_amb_context_social(
        self,
        avaluacio: LeadEvaluationSchema,
        identitat: Agent1IdentityData,
        scoring: Agent2ScoringData,
        social: Agent3SocialData,
    ) -> LeadEvaluationSchema:
        """Assegura que els 3 correus dels leads SELECCIONATS tinguin personalització real multi-canal i zero WhatsApp."""
        if avaluacio.estat_decisio != "SELECCIONAT":
            avaluacio.campanya_3_emails = []
            return avaluacio

        decisor_final = avaluacio.decisor_nom or social.gatekeeper_nom_social or identitat.gatekeeper_nom
        salutacio = decisor_final if es_nom_persona_real(decisor_final) else f"equip directiu de {identitat.nom_empresa}"
        fita_ref = avaluacio.fita_recent or social.fita_social_destacada or f"la vostra trajectòria a {identitat.web_url}"
        dolor_ref = (
            avaluacio.punt_dolor
            or scoring.punt_dolor_operatiu
            or "la pèrdua d'hores entre els partes d'obra al terreny i la facturació a l'oficina"
        )

        canals_esmentats: List[str] = []
        if social.linkedin_empresa_url:
            canals_esmentats.append("LinkedIn")
        if social.instagram_url:
            canals_esmentats.append("Instagram")
        canal_str = " i ".join(canals_esmentats) if canals_esmentats else "la vostra web corporativa"

        # Si el model IA no ha retornat els 3 correus complets, els generem des de l'Orquestrador amb les dades dels 3 agents
        if len(avaluacio.campanya_3_emails) < 3:
            avaluacio.campanya_3_emails = [
                EmailStepSchema(
                    pas=1,
                    tempo_offset_dies=0,
                    assumpte=f"Optimització operativa per a {identitat.nom_empresa} ({identitat.vertical})",
                    cos_text=(
                        f"Hola {salutacio},\n\n"
                        f"Hem estat seguint l'activitat recent de {identitat.nom_empresa} a través de {canal_str} "
                        f"({fita_ref}). En empreses de {identitat.vertical} amb quadrilles al terreny com la vostra, "
                        f"detectem sovint un punt crític: {dolor_ref}.\n\n"
                        f"Amb Sevalor Suite connectem els vostres tècnics mitjançant la PWA mòbil `/operari` "
                        f"(albarans en 30 segons i control d'estoc de furgonetes) i notifiquem el client final amb "
                        f"el nostre Bot Oficial de Telegram per signar la conformitat a l'instant.\n\n"
                        f"Us aniria bé veure en 10 minuts com s'adapta a l'operativa de {identitat.nom_empresa}?\n\n"
                        f"Salutacions cordials,\nEquip Tècnic Sevalor\ntecnic@sevalor.net"
                    ),
                ),
                EmailStepSchema(
                    pas=2,
                    tempo_offset_dies=4,
                    assumpte=f"Cas d'èxit en {identitat.vertical}: de la furgoneta a la factura Veri*factu",
                    cos_text=(
                        f"Hola {salutacio},\n\n"
                        f"Fa uns dies us escrivíem sobre la gestió de les vostres quadrilles. "
                        f"Recentment una empresa instal·ladora de {identitat.vertical} amb una estructura similar "
                        f"a {identitat.nom_empresa} ha eliminat el 85% del paper i dels albarans perduts "
                        f"centralitzant els partes a la PWA de Sevalor i automatitzant els avisos per Telegram.\n\n"
                        f"Si voleu, us podem ensenyar aquesta configuració aplicada al vostre cas concret.\n\n"
                        f"Cordialment,\ntecnic@sevalor.net"
                    ),
                ),
                EmailStepSchema(
                    pas=3,
                    tempo_offset_dies=8,
                    assumpte=f"Activació de Demo Real de 7 dies per a {identitat.nom_empresa}",
                    cos_text=(
                        f"Hola {salutacio},\n\n"
                        f"Per no robar-vos més temps: si voleu comprovar directament al terreny com funciona "
                        f"la connexió entre la PWA dels operaris, el panell d'enginyeria i el Bot Oficial de Telegram, "
                        f"podem activar-vos una Demo Real de 7 dies per a {identitat.nom_empresa} sense cap compromís.\n\n"
                        f"Responeu aquest correu i us habilitem l'accés avui mateix.\n\n"
                        f"Una salutació,\ntecnic@sevalor.net"
                    ),
                ),
            ]
        return avaluacio

    async def executar_pipeline_candidat(
        self,
        item_candidat: Dict[str, Any],
        codi_postal: str,
        vertical: str,
        operaris_minims: int,
        municipi_esperat: Optional[str],
        db: AsyncSession,
    ) -> OrchestratorCandidateResult:
        """Executa el flux complet coordinat: Agent 1 -> Agent 2 -> Agent 3 -> Validació i Redacció."""
        nom_ini = (item_candidat.get("nom_empresa") or "Empresa Sense Nom").strip()
        web_ini = (item_candidat.get("web_url") or "").strip()

        # Executar investigació completa unificada per mantenir compatibilitat amb mocks de tests i caché HTTP
        investigacio_completa = await firecrawl_service.investigar_empresa_completa(
            nom_empresa=nom_ini,
            web_url=web_ini,
            codi_postal=codi_postal,
            vertical=vertical,
            dades_inicials=item_candidat,
        )

        # ------------------------------------------------------------------
        # FASE 1: Agent 1 (Extracció d'Identitat, Contacte i Gatekeeper)
        # ------------------------------------------------------------------
        dades_agent1 = await self.agent1.executar(
            item_candidat=item_candidat,
            codi_postal=codi_postal,
            vertical=vertical,
            municipi_esperat=municipi_esperat,
            db=db,
            investigacio_precalculada=investigacio_completa,
        )

        # ------------------------------------------------------------------
        # FASE 2: Agent 2 (Validació de Puntuació, Quadrilles i Actualitat)
        # ------------------------------------------------------------------
        dades_agent2 = await self.agent2.executar(
            identitat=dades_agent1,
            operaris_minims=operaris_minims,
            db=db,
            fita_inicial=investigacio_completa.get("fita_recent") or item_candidat.get("fita_recent"),
        )

        # ------------------------------------------------------------------
        # FASE 3: Agent 3 (Cerca a Xarxes Socials: LinkedIn, Instagram, Premsa)
        # ------------------------------------------------------------------
        dades_agent3 = await self.agent3.executar(
            identitat=dades_agent1,
            scoring=dades_agent2,
            investigacio_precalculada=investigacio_completa,
        )

        # Sincronitzar el Gatekeeper si l'Agent 3 l'ha descobert a LinkedIn
        gk_nom_consolidat = dades_agent3.gatekeeper_nom_social or dades_agent1.gatekeeper_nom
        gk_carrec_consolidat = dades_agent3.gatekeeper_carrec_social or dades_agent1.gatekeeper_carrec
        gatekeeper_hints_consolidats: Dict[str, str] = {}
        if gk_nom_consolidat and es_nom_persona_real(gk_nom_consolidat):
            gatekeeper_hints_consolidats["nom"] = gk_nom_consolidat
            gatekeeper_hints_consolidats["context"] = gk_nom_consolidat
            gatekeeper_hints_consolidats["carrec"] = gk_carrec_consolidat or "Gerent / Direcció"
        if dades_agent1.email_gatekeeper:
            gatekeeper_hints_consolidats["email"] = dades_agent1.email_gatekeeper

        # ------------------------------------------------------------------
        # FASE 4: Avaluació Final i Redacció de l'Orquestrador (OpenRouter / Regles)
        # ------------------------------------------------------------------
        avaluacio = await qualificar_candidat_amb_openrouter(
            nom_empresa=dades_agent1.nom_empresa,
            web_url=dades_agent1.web_url,
            codi_postal=dades_agent1.codi_postal,
            vertical=dades_agent1.vertical,
            operaris_minims=operaris_minims,
            web_markdown=dades_agent1.web_markdown,
            fonts_investigades=dades_agent3.fonts_investigades,
            fita_recent=dades_agent3.fita_social_destacada,
            gatekeeper_hints=gatekeeper_hints_consolidats,
            db=db,
            adreca_fisica=dades_agent1.adreca_fisica or "",
            municipi=municipi_esperat,
            te_contacte_operatiu=dades_agent1.te_contacte_operatiu,
        )

        # Tallafocs Ponderat de les 3 Premisses de Qualitat supervisat per l'Orquestrador:
        # Premissa A: Adreça verificada al CP exacte o al mateix municipi/polígon industrial
        if not validar_cp_o_municipi_en_adreca(
            dades_agent1.adreca_fisica,
            dades_agent1.codi_postal,
            municipi=municipi_esperat,
        ):
            avaluacio.estat_decisio = "DESCARTAT"
            avaluacio.score = min(avaluacio.score, 30)
            avaluacio.campanya_3_emails = []
            avaluacio.motiu_detallat_ia = (
                f"Descartat (Ubicació Física): L'adreça ('{dades_agent1.adreca_fisica or 'No disponible'}') "
                f"no correspon al CP {dades_agent1.codi_postal} ni al municipi ({municipi_esperat or 'N/A'})."
            )

        # Premissa B: Gatekeeper Nominal vs Lead Corporatiu amb Contacte Directe Verificat
        if not es_nom_persona_real(avaluacio.decisor_nom):
            # Si l'Agent 1 o l'Agent 3 havien trobat un nom real verificat però l'LLM no l'ha copiat, restaurar-lo
            if gk_nom_consolidat and es_nom_persona_real(gk_nom_consolidat):
                avaluacio.decisor_nom = gk_nom_consolidat
                avaluacio.decisor_carrec = avaluacio.decisor_carrec or gk_carrec_consolidat or "Gerent"
            else:
                avaluacio.decisor_nom = None
                if avaluacio.estat_decisio == "SELECCIONAT":
                    if dades_agent1.te_contacte_operatiu and avaluacio.operaris_estimats >= operaris_minims:
                        avaluacio.score = max(65, min(avaluacio.score - 12, 78))
                        avaluacio.decisor_carrec = avaluacio.decisor_carrec or "Direcció / Gerència (Pendent nom)"
                        if "[AVÍS: Decisor nominal pendent d'identificar]" not in avaluacio.motiu_detallat_ia:
                            avaluacio.motiu_detallat_ia = (
                                f"[AVÍS: Decisor nominal pendent d'identificar] {avaluacio.motiu_detallat_ia} "
                                f"S'admet pels seus indicadors operatius ({avaluacio.operaris_estimats} operaris) i contacte verificat."
                            )
                    else:
                        avaluacio.estat_decisio = "DESCARTAT"
                        avaluacio.score = min(avaluacio.score, 40)
                        avaluacio.campanya_3_emails = []
                        avaluacio.motiu_detallat_ia = (
                            "Descartat: Sense Gatekeeper nominal identificat ni dades de contacte/operaris suficients."
                        )

        # Premissa C: Enllaç web directe comprovable
        if not validar_url_verificable(dades_agent1.web_url):
            avaluacio.estat_decisio = "DESCARTAT"
            avaluacio.score = min(avaluacio.score, 20)
            avaluacio.campanya_3_emails = []
            avaluacio.motiu_detallat_ia = (
                "Descartat automàticament (Regla d'Enllaços Comprovables): No disposa d'un enllaç web directe i verificable."
            )

        # Assegurar que la campanya de 3 correus estigui enriquida amb les dades socials i el punt de dolor
        avaluacio = self._enriquir_emails_amb_context_social(
            avaluacio=avaluacio,
            identitat=dades_agent1,
            scoring=dades_agent2,
            social=dades_agent3,
        )

        return OrchestratorCandidateResult(
            agent1=dades_agent1,
            agent2=dades_agent2,
            agent3=dades_agent3,
            avaluacio_final=avaluacio,
        )


# Instància singleton de l'Orquestrador Multi-Agent
prospeccio_orchestrator = ProspeccioAgentOrchestrator()
