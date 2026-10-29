"""
integracio_snippets.py  ->  NO és un mòdul importable.
Conté dos fragments per enganxar als teus fitxers existents:

  A) firecrawl_service.py   -> substitueix el mètode descobrir_empreses_codi_postal
  B) crm_prospeccio.py      -> adapta el bucle d'avaluació de candidats

Cada mètode del bloc A va dins de la classe del servei (per això van indentats).
"""

# ═════════════════════════════════════════════════════════════════════════════
# A) firecrawl_service.py
# ═════════════════════════════════════════════════════════════════════════════

# --- Imports a afegir a dalt de firecrawl_service.py -------------------------
# import asyncio, logging, re
# from collections import Counter
# import httpx
# from app.services.prospeccio_validacio import (
#     USER_AGENT, GEOCODE_MODE, Gatekeeper, adreca_valida_per_cp, coincideix_vertical,
#     cp_geocodificat, es_domini_espanyol, ids_fiscals_valids, ordenar_per_prioritat,
#     sembla_directori, telefons_es, trobar_gatekeeper,
# )
# from app.services.scraper_domini import adreca_jsonld, descarregar_pagines, osm_per_cp
#
# logger = logging.getLogger(__name__)
#
# + afegeix a _XARXES_I_DIRECTORIS_GENERICS_IGNORAR: wallapop.com, milanuncios.com,
#   paginasamarillas.es, habitissimo.es, adac.de ... (i adapta la comprovació de
#   dominis de _recollir_candidats si la teva llista és de subcadenes).

# --- Mètodes de la classe (referència per enganxar dins de la classe del servei) -
# (Ja integrats a backend/app/services/firecrawl_service.py)
#
#     async def descobrir_empreses_codi_postal(
#         self, codi_postal: str, vertical: str, limit: int = 10, max_candidats: int = 60,
#     ):
#         """
#         Retorna (candidats_validats, embut). Cap candidat surt d'aquí sense:
#         CP exacte (carrer+número), domini/telèfon d'Espanya, no-directori i vertical.
#         """
#         cp = codi_postal.strip()
#         if not re.fullmatch(r"\d{5}", cp):
#             raise ValueError(f"Codi postal invàlid: {codi_postal!r}")
#         vertical = vertical.strip()
#         embut: Counter = Counter()
#
#         geo = await obtenir_municipi_de_codi_postal(cp)
#         municipi = geo.get("municipi") if geo else None
#
#         validats: list[dict] = []
#         async with httpx.AsyncClient(follow_redirects=True,
#                                      headers={"User-Agent": USER_AGENT}) as client:
#             brut = (await self._recollir_candidats(client, cp, municipi, vertical))[:max_candidats]
#             embut["trobats"] = len(brut)
#             sem = asyncio.Semaphore(4)
#
#             async def un(item):
#                 async with sem:
#                     return await self._validar_candidat(client, item, cp, vertical, embut)
#
#             for i in range(0, len(brut), 8):          # lots de 8: ens aturem quan n'hi ha prou
#                 if len(validats) >= limit:
#                     break
#                 lot = await asyncio.gather(*(un(it) for it in brut[i:i + 8]), return_exceptions=True)
#                 for r in lot:
#                     if isinstance(r, Exception):
#                         logger.warning("candidat fallit: %r", r)
#                         embut["error"] += 1
#                     elif r:
#                         validats.append(r)
#
#         logger.info("embut descoberta cp=%s vertical=%s %s", cp, vertical, dict(embut))
#         return validats[:limit], dict(embut)
#
#     async def _recollir_candidats(self, client, cp: str, municipi: str | None, vertical: str) -> list[dict]:
#         vistos: set[str] = set()
#         out: list[dict] = []
#
#         def afegir(it: dict):
#             d = normalitzar_domini(it.get("url", ""))
#             if d and d not in vistos and d not in _XARXES_I_DIRECTORIS_GENERICS_IGNORAR:
#                 vistos.add(d)
#                 out.append(it)
#
#         # 1) OSM/Overpass amb CP exacte (font estructurada)
#         try:
#             for it in await osm_per_cp(client, cp, vertical):
#                 afegir(it)
#         except Exception as e:
#             logger.warning("overpass ha fallat: %r", e)
#
#         # 2) Cerca web: CP entre cometes, SENSE 'OR' i SENSE cerques només per municipi
#         for terme in _expandir_termes_cerca_vertical(vertical)[:3]:
#             consultes = [f'{terme} "{cp}"']
#             if municipi:
#                 consultes.append(f"{terme} {cp} {municipi}")
#             for q in consultes:
#                 for it in await self._cercar_web_multimotor(q, limit=10):
#                     afegir(it)
#         return out
#
#     async def _pagines(self, client, url: str):
#         # fallback_js: connecta aquí el scrape de Firecrawl que ja tens (retorna markdown o None)
#         return await descarregar_pagines(client, url, max_pagines=6, fallback_js=None)
#
#     async def _validar_candidat(self, client, item: dict, cp: str, vertical: str, embut: Counter):
#         url = item["url"]
#         pagines = await self._pagines(client, url)
#         if not pagines:
#             embut["descarrega_ko"] += 1
#             return None
#         text = "\n".join(p.text for p in pagines)
#
#         if sembla_directori(text):
#             embut["directori"] += 1
#             return None
#         if not es_domini_espanyol(url, text):
#             embut["no_espanya"] += 1
#             return None
#
#         adreca = adreca_valida_per_cp(text, cp) or adreca_jsonld(pagines, cp)
#         if not adreca:
#             embut["cp_no_coincideix"] += 1
#             return None
#
#         cp_geo = await cp_geocodificat(client, adreca)       # CP segons Nominatim (None = no ho sap)
#         cp_geo_coincideix = None if cp_geo is None else (cp_geo == cp)   # tri-estat: True / False / None
#         if cp_geo_coincideix is False:
#             embut["cp_geocode_difereix"] += 1
#             if GEOCODE_MODE == "descartar":
#                 return None
#         elif cp_geo_coincideix is None:
#             embut["cp_geocode_desconegut"] += 1             # no penalitza, però es compta
#
#         if not coincideix_vertical(text, vertical):
#             embut["vertical"] += 1
#             return None
#
#         ordre = ordenar_per_prioritat(pagines)
#         gk: Gatekeeper | None = trobar_gatekeeper([(p.url, p.text) for p in ordre])
#         emails = _extreure_emails_empresa_i_gatekeeper_de_text(
#             text, domini_preferit=normalitzar_domini(url))
#         ids = ids_fiscals_valids(text)
#         tels = sorted(telefons_es(text))
#
#         if gk is None:
#             embut["sense_gatekeeper"] += 1                  # per decidir PERMET_SENSE_GATEKEEPER amb dades
#             if not tels:
#                 embut["sense_gatekeeper_sense_telefon"] += 1
#
#         embut["validats"] += 1
#         return {
#             "nom_empresa": _deduir_nom_empresa_de_titol_i_domini(item.get("title", ""), url),
#             "web_url": url,
#             "adreca_fisica": adreca,
#             "cp_verificat": True,
#             "cp_geocode_retornat": cp_geo,                  # CP segons Nominatim (None si no ho sap)
#             "cp_geocode_coincideix": cp_geo_coincideix,     # True / False / None
#             "cif": ids[0] if ids else None,
#             "email": emails.get("email_principal"),
#             "telefon": tels[0] if tels else None,
#             "telefon_valid": bool(tels),
#             "gatekeeper": gk,                       # Gatekeeper | None (amb font i cita)
#             "pagines": pagines,                     # per construir_context() i per auditar
#             "pagines_urls": [p.url for p in pagines],
#         }


# ═════════════════════════════════════════════════════════════════════════════
# B) crm_prospeccio.py  (bucle d'avaluació)
# ═════════════════════════════════════════════════════════════════════════════
#
# from app.services.prospeccio_validacio import (
#     ContextValidat, aplicar_regles_dures, bloc_gatekeeper, construir_context,
# )
#
#     candidats_raw, embut = await firecrawl_service.descobrir_empreses_codi_postal(
#         codi_postal=payload.codi_postal,
#         vertical=payload.vertical,
#         limit=payload.limit or 5,
#     )
#     # guarda `embut` al registre de l'execució (columna JSON) per veure on es perden leads
#
#     for item in candidats_raw:                      # ja validats: CP exacte, Espanya, vertical
#         async with db.begin_nested():
#             # 1) duplicats (barat): igual que ara
#             es_dup, vector_dup, motiu_dup = await verificar_duplicitat_multivector(...)
#             if es_dup:
#                 ...
#                 continue
#
#             # 2) investigació complementària (BORME, LinkedIn, Instagram): igual que ara
#             investigacio = await firecrawl_service.investigar_empresa_completa(...)
#             fonts = list(investigacio.get("fonts_investigades", []))
#             gk = item["gatekeeper"]
#             if gk:
#                 fonts.append(f"web|{gk.font_url}")  # traçabilitat del nom
#
#             # 3) MX shield: igual que ara
#             mx_valid, _ = await validar_email_mx(email_det, db=db)
#
#             # 4) LLM: ara rep context prioritzat i el gatekeeper ja verificat
#             avaluacio = await qualificar_candidat_amb_openrouter(
#                 nom_empresa=item["nom_empresa"],
#                 web_url=item["web_url"],
#                 codi_postal=cp_clean,
#                 vertical=vertical_clean,
#                 operaris_minims=payload.operaris_minims,
#                 web_markdown=construir_context(item["pagines"], max_chars=6000),
#                 fonts_investigades=fonts,
#                 fita_recent=investigacio.get("fita_recent"),
#                 gatekeeper_bloc=bloc_gatekeeper(gk),          # <- NOU (substitueix gatekeeper_hints)
#                 adreca_fisica=item["adreca_fisica"],
#                 municipi=municipi_esperat,
#                 te_contacte_operatiu=te_contacte_operatiu,
#                 db=db,
#             )
#
#             # 5) regles dures: el codi sempre té l'última paraula (substitueix l'antic pas 6)
#             aplicar_regles_dures(avaluacio, ContextValidat(
#                 ubicacio_ok=item["cp_verificat"],
#                 vertical_ok=True,                 # ja garantit a la descoberta
#                 gatekeeper=gk,
#                 fonts_entrada=set(fonts),
#                 fita_recent=investigacio.get("fita_recent"),
#                 telefon_valid=item["telefon_valid"],
#             ))
#
#             # 6) persistència (columnes noves, vegeu la secció C)
#             lead.cp_geocode_retornat = item["cp_geocode_retornat"]
#             lead.cp_geocode_coincideix = item["cp_geocode_coincideix"]    # True / False / None
#             lead.gatekeeper_font_url = gk.font_url if gk else None
#             lead.gatekeeper_cita = gk.cita if gk else None
#             lead.gatekeeper_confianca = gk.confianca if gk else None
#             # Interfície: mostra una etiqueta d'alerta quan cp_geocode_coincideix is False
#
# Esborra validar_cp_o_municipi_en_adreca (accepta el municipi) per evitar regressions.
# Afegeix 'SELECCIONAT_SENSE_GATEKEEPER' a l'enum / CHECK de estat_decisio (migració Alembic).


# ═════════════════════════════════════════════════════════════════════════════
# C) Migració Alembic (adapta TAULA_LEADS, el nom de l'enum i el model del lead)
# ═════════════════════════════════════════════════════════════════════════════
#
# def upgrade():
#     op.add_column("TAULA_LEADS", sa.Column("cp_geocode_retornat", sa.String(5), nullable=True))
#     op.add_column("TAULA_LEADS", sa.Column("cp_geocode_coincideix", sa.Boolean(), nullable=True))
#     op.add_column("TAULA_LEADS", sa.Column("gatekeeper_font_url", sa.Text(), nullable=True))
#     op.add_column("TAULA_LEADS", sa.Column("gatekeeper_cita", sa.Text(), nullable=True))
#     op.add_column("TAULA_LEADS", sa.Column("gatekeeper_confianca", sa.String(10), nullable=True))
#
#     # Nou valor d'estat_decisio. Depèn de com el tinguis definit:
#     #  - ENUM de PostgreSQL (fora de transacció, per això l'autocommit_block):
#     #      with op.get_context().autocommit_block():
#     #          op.execute("ALTER TYPE NOM_ENUM ADD VALUE IF NOT EXISTS 'SELECCIONAT_SENSE_GATEKEEPER'")
#     #  - VARCHAR amb CHECK: elimina i recrea la constraint incloent el valor nou.
#
# def downgrade():
#     for col in ("gatekeeper_confianca", "gatekeeper_cita", "gatekeeper_font_url",
#                 "cp_geocode_coincideix", "cp_geocode_retornat"):
#         op.drop_column("TAULA_LEADS", col)
#     # Els valors d'un ENUM de PostgreSQL no es poden eliminar fàcilment: deixa'l.
