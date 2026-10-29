"""
test_prospeccio_validacio.py  ->  backend/tests/test_prospeccio_validacio.py
Cobreix els errors observats al test en viu amb el CP 25001 (Lleida).
Executa: pytest backend/tests/test_prospeccio_validacio.py -q
"""
from types import SimpleNamespace

import app.services.prospeccio_validacio as v
from app.services.prospeccio_validacio import (
    ContextValidat,
    adreca_valida_per_cp,
    aplicar_regles_dures,
    coincideix_vertical,
    email_sembla_del_nom,
    es_domini_espanyol,
    ids_fiscals_valids,
    sembla_directori,
    trobar_gatekeeper,
)


# ───────────── CP i adreça ─────────────
def test_cp_exacte_amb_carrer_i_numero_es_accepta():
    r = adreca_valida_per_cp("Carrer Major, 12 - 25001 Lleida", "25001")
    assert r and "Carrer Major" in r and "25001" in r


def test_l_adreca_no_arrossega_text_del_footer():
    r = adreca_valida_per_cp("Carrer Major, 12 - 25001 Lleida mail tel mailto:info@x.es", "25001")
    assert r == "Carrer Major, 12 - 25001 Lleida"


def test_altre_cp_del_mateix_municipi_es_rebutja():
    # Abans: "és de Lleida, per tant és compatible"
    assert adreca_valida_per_cp("Carrer Major, 12 - 25004 Lleida", "25001") is None
    assert adreca_valida_per_cp("Avinguda Catalunya 3, 25005 Lleida", "25001") is None


def test_cp_sense_carrer_es_rebutja():
    # Abans: l'adreça '25001 Lleida' sense via es donava per vàlida
    assert adreca_valida_per_cp("© 2024 Instal·lacions Puig SL · 25001 Lleida", "25001") is None


def test_cp_dins_d_un_altre_numero_no_compta():
    assert adreca_valida_per_cp("Carrer Major, 12 - 125001", "25001") is None


# ───────────── Espanya i directoris ─────────────
def test_domini_estranger_es_rebutja():
    # Abans: adac.de passava el filtre
    assert not es_domini_espanyol("https://www.adac.de/maps", "Tel +34 612 345 678")


def test_domini_espanyol_amb_telefon_valid():
    assert es_domini_espanyol("https://instalpuig.cat", "Truca'ns: +34 612 345 678")


def test_domini_sense_telefon_espanyol_es_rebutja():
    assert not es_domini_espanyol("https://instalpuig.cat", "Escriu-nos a info@instalpuig.cat")


def test_directori_amb_molts_cp():
    text = " ".join(f"250{i:02d}" for i in range(1, 8))
    assert sembla_directori(text)


def test_web_d_empresa_normal_no_es_directori():
    assert not sembla_directori("Carrer Major 12, 25001 Lleida. Tel +34 612 345 678")


# ───────────── Vertical ─────────────
def test_vertical_coincideix():
    assert coincideix_vertical("Instalaciones eléctricas y REBT en Lleida", "baixa tensió")


def test_vertical_no_coincideix_ferreteria():
    assert not coincideix_vertical("Ferretería y bricolaje para el hogar", "baixa tensió")


# ───────────── Gatekeeper ─────────────
def test_gatekeeper_de_l_aviso_legal():
    text = "Aviso legal. Titular: Joan Puig Serra, administrador único. NIF B12345678."
    gk = trobar_gatekeeper([("https://x.es/aviso-legal", text)])
    assert gk and gk.nom == "Joan Puig Serra"
    assert gk.carrec.startswith("administrador")
    assert gk.confianca == "mitjana"
    assert "Joan Puig Serra" in gk.cita


def test_gatekeeper_confianca_alta_amb_dues_pagines():
    gk = trobar_gatekeeper([
        ("https://x.es/equip", "Joan Puig Serra, Gerent"),
        ("https://x.es/", "Equip: Joan Puig Serra"),
    ])
    assert gk and gk.confianca == "alta"


def test_gatekeeper_rebutja_falsos_noms():
    assert trobar_gatekeeper([("u", "Política de Privacidad, Director")]) is None
    assert trobar_gatekeeper([("u", "Contacte: info@instalpuig.cat")]) is None


def test_email_personal_vs_generic():
    assert email_sembla_del_nom("jpuig@x.es", "Joan Puig Serra")
    assert email_sembla_del_nom("joan.puig@x.es", "Joan Puig Serra")
    assert not email_sembla_del_nom("info@x.es", "Joan Puig Serra")


def test_ids_fiscals_amb_digit_de_control():
    assert ids_fiscals_valids("NIF 12345678Z") == ["12345678Z"]
    assert ids_fiscals_valids("NIF 12345678A") == []


# ───────────── Regles dures post-IA ─────────────
def _av(**kw):
    base = dict(estat_decisio="SELECCIONAT", score=92, decisor_nom="Inventat Persona",
                decisor_carrec="Gerent",
                fonts_investigades=["web|https://a.es", "web|https://inventada.es"],
                fita_recent="Obra inventada", motiu_detallat_ia="ok", campanya_3_emails=[])
    base.update(kw)
    return SimpleNamespace(**base)


def _ctx(**kw):
    base = dict(ubicacio_ok=True, vertical_ok=True, gatekeeper=None,
                fonts_entrada={"web|https://a.es"}, fita_recent=None, telefon_valid=True)
    base.update(kw)
    return ContextValidat(**base)


def test_el_model_no_pot_inventar_gatekeeper_ni_fonts_ni_fita():
    av = aplicar_regles_dures(_av(), _ctx())
    assert av.decisor_nom is None and av.decisor_carrec is None
    assert av.fonts_investigades == ["web|https://a.es"]
    assert av.fita_recent is None
    assert av.estat_decisio == "SELECCIONAT_SENSE_GATEKEEPER" and av.score <= 79
    assert "[CODI]" in av.motiu_detallat_ia


def test_sense_gatekeeper_es_descarta_si_la_politica_ho_exigeix(monkeypatch):
    monkeypatch.setattr(v, "PERMET_SENSE_GATEKEEPER", False)
    av = aplicar_regles_dures(_av(), _ctx())
    assert av.estat_decisio == "DESCARTAT" and av.score <= 49


def test_sense_gatekeeper_ni_telefon_valid_es_descarta():
    av = aplicar_regles_dures(_av(), _ctx(telefon_valid=False))
    assert av.estat_decisio == "DESCARTAT" and av.score <= 49
    assert "telèfon" in av.motiu_detallat_ia


def test_amb_gatekeeper_no_cal_telefon_per_seleccionar():
    gk = trobar_gatekeeper([("https://x.es/equip", "Joan Puig Serra, Gerent")])
    av = aplicar_regles_dures(_av(), _ctx(gatekeeper=gk, telefon_valid=False))
    assert av.estat_decisio == "SELECCIONAT"


def test_ubicacio_no_verificada_descarta():
    av = aplicar_regles_dures(_av(), _ctx(ubicacio_ok=False))
    assert av.estat_decisio == "DESCARTAT" and av.score <= 25


def test_amb_gatekeeper_verificat_queda_seleccionat():
    gk = trobar_gatekeeper([("https://x.es/equip", "Joan Puig Serra, Gerent")])
    av = aplicar_regles_dures(_av(), _ctx(gatekeeper=gk, fita_recent="Obra real"))
    assert av.estat_decisio == "SELECCIONAT"
    assert av.decisor_nom == "Joan Puig Serra" and av.fita_recent == "Obra real"


# ───────────── Proves addicionals de Wallapop, .fr i llistes negres ─────────────
def test_domini_fr_i_altres_tld_estrangers_es_rebutgen():
    """Un domini .fr (França) o .de (Alemanya) mai és considerat espanyol encara que el text citi un CP espanyol."""
    assert not es_domini_espanyol("https://artisan-electricien.fr", "Carrer Major 12, 25001 Lleida tel: 973240011")
    assert not es_domini_espanyol("https://instal-service.fr/contact", "Av Catalunya 5, 25001 Lleida tel: 973240022")


def test_wallapop_i_milanuncios_no_arriben_a_candidats_a_validar():
    """Comprova que dominis de compravenda/anuncis (Wallapop, Milanuncios, Habitissimo)
    queden bloquejats a la llista negra del servei i mai arriben al procés de validació.
    """
    from app.services.firecrawl_service import _XARXES_I_DIRECTORIS_GENERICS_IGNORAR, normalitzar_domini

    urls_prohibides = [
        "https://es.wallapop.com/item/instalador-lleida-12345",
        "https://www.milanuncios.com/reformas/fontanero-lleida.htm",
        "https://maps.adac.de/poi/service-point",
        "https://www.habitissimo.es/instaladores-climatizacion",
    ]
    for u in urls_prohibides:
        dom = normalitzar_domini(u)
        assert any(x in dom for x in _XARXES_I_DIRECTORIS_GENERICS_IGNORAR), f"{u} hauria d'estar ignorada a la llista negra"


def test_directori_amb_patrons_de_marketplace_es_rebutja():
    """Si una pàgina conté patrons de marketplace/classificats o múltiples CPs, es detecta com a directori."""
    text_classificats = (
        "Anuncios de segunda mano en Lleida. Contacta con particulares y profesionales. "
        "CP 25001, CP 25002, CP 25003, CP 25004, CP 25005, CP 25006, CP 25007."
    )
    assert sembla_directori(text_classificats)
