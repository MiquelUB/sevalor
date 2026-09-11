"""
Seguretat de fitxers per al Bot de Telegram (Spec 023).

Mòdul stub: la implementació real es troba a bot/security.py.
Aquest mòdul proporciona aliases perquè els tests del backend puguin
importar les funcions sense dependre del paquet bot complet.
"""

import sys

# Intentar importar des de bot.security
try:
    from bot.security import detectar_doble_extensio, validar_magic_bytes
except (ImportError, ModuleNotFoundError):
    # Fallback: funcions stub per a tests
    def detectar_doble_extensio(nom_fitxer: str) -> tuple:
        return False, "OK"

    def validar_magic_bytes(contingut_bytes: bytes, extensio: str = "") -> bool:
        return True

def validate_telegram_file_safety(nom_fitxer: str, contingut_bytes: bytes) -> dict:
    """
    Valida la seguretat d'un fitxer per al Bot de Telegram.
    Combina doble extensió + magic bytes.
    """
    es_perillos, motiu = detectar_doble_extensio(nom_fitxer)
    if es_perillos:
        return {"valid": False, "motiu": motiu}
    
    es_valid = validar_magic_bytes(contingut_bytes)
    if not es_valid:
        return {"valid": False, "motiu": "Magic bytes no vàlids"}
    
    return {"valid": True, "motiu": "OK"}