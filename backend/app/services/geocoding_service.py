"""Servei de geocodificació territorial per al backend de Sevalor.
Tradueix adreces postals de Catalunya a coordenades reals (WGS84).
"""

import re
import unicodedata
from typing import Optional, Tuple


def normalitzar_text(text: str) -> str:
    """Normalitza el text eliminant accents i passant a minúscules."""
    nfkd = unicodedata.normalize("NFKD", text)
    sense_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return sense_accents.lower().strip()


# Diccionari territorial de Catalunya i ciutats clau
DICCIONARI_CATALUNYA = [
    # Carrers i punts de Barcelona
    (["carrer industria", "carrer indistria", "c/ industria", "c. industria", "industria"], 41.4080, 2.1760),
    (["passeig de gracia", "pg de gracia", "gracia"], 41.3920, 2.1649),
    (["diagonal", "av diagonal"], 41.3970, 2.1550),
    (["carrer arago", "c/ arago", "arago"], 41.3895, 2.1648),
    (["sagrada familia"], 41.4036, 2.1743),
    (["barcelona", "bcn"], 41.3879, 2.1699),
    (["badalona"], 41.4500, 2.2474),
    (["hospitalet de llobregat", "hospitalet"], 41.3597, 2.1003),
    (["sant cugat"], 41.4720, 2.0850),
    (["sabadell"], 41.5463, 2.1086),
    (["terrassa"], 41.5632, 2.0089),
    (["mataro"], 41.5381, 2.4447),
    (["granollers"], 41.6080, 2.2880),
    (["cornella"], 41.3560, 2.0720),
    (["sant boi"], 41.3460, 2.0420),
    (["castelldefels"], 41.2800, 1.9770),
    (["el prat"], 41.3280, 2.0950),
    (["rubi"], 41.4920, 2.0320),

    # Lleida i Ponent
    (["balaguer"], 41.7912, 0.8055),
    (["alcarras"], 41.5644, 0.5244),
    (["mollerussa"], 41.6300, 0.8950),
    (["tarrega"], 41.6467, 1.1396),
    (["cervera"], 41.6710, 1.2720),
    (["almacelles"], 41.7320, 0.4380),
    (["alpicat"], 41.6670, 0.5560),
    (["les borges blanques", "borges blanques"], 41.5220, 0.8710),
    (["tremp"], 42.1670, 0.8950),
    (["la seu d'urgell", "seu d'urgell"], 42.3580, 1.4600),
    (["vielha"], 42.7030, 0.7950),
    (["lleida", "lerida", "segria"], 41.6176, 0.6200),

    # Girona
    (["girona", "gerona"], 41.9794, 2.8214),
    (["figueres"], 42.2660, 2.9610),
    (["olot"], 42.1810, 2.4890),
    (["blanes"], 41.6750, 2.7930),
    (["lloret de mar", "lloret"], 41.6990, 2.8450),
    (["palafrugell"], 41.9170, 3.1640),
    (["banyoles"], 42.1180, 2.7660),

    # Tarragona
    (["tarragona"], 41.1189, 1.2445),
    (["reus"], 41.1561, 1.1069),
    (["tortosa"], 40.8120, 0.5210),
    (["cambrils"], 41.0750, 1.0590),
    (["salou"], 41.0770, 1.1290),
    (["valls"], 41.2860, 1.2500),
    (["el vendrell", "vendrell"], 41.2210, 1.5350),
    (["amposta"], 40.7130, 0.5800),

    # Catalunya Central
    (["manresa"], 41.7285, 1.8267),
    (["vic"], 41.9304, 2.2545),
    (["igualada"], 41.5820, 1.6170),
    (["berga"], 42.1040, 1.8460),
]


def geocodificar_adreca(
    adreca: Optional[str], lat_def: Optional[float] = None, lng_def: Optional[float] = None
) -> Tuple[Optional[float], Optional[float]]:
    """Resol les coordenades lat/lng a partir d'una adreça postal o coordenades directes."""
    if lat_def is not None and lng_def is not None:
        return lat_def, lng_def

    if not adreca or not isinstance(adreca, str) or not adreca.strip():
        return None, None

    raw = adreca.strip()

    # 1. Detectar coordenades numèriques directes tipus "41.4080, 2.1760"
    match = re.search(r"([-+]?\d{1,2}\.\d+)[,\s]+([-+]?\d{1,3}\.\d+)", raw)
    if match:
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
            if 35.0 <= lat <= 45.0 and -10.0 <= lng <= 5.0:
                return lat, lng
        except ValueError:
            pass

    # 2. Cerca al diccionari territorial
    norm = normalitzar_text(raw)
    for patrons, lat, lng in DICCIONARI_CATALUNYA:
        for p in patrons:
            if p in norm:
                return lat, lng

    return None, None
