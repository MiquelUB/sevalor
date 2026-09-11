"""Seguretat avançada i middlewares pel Bot de Telegram (Spec 023)."""
import os
import re
import filetype
import logging
from typing import Tuple, Optional
from redis.asyncio import Redis

logger = logging.getLogger("bot.security")

EXTENSIONS_PERMESES = {
    # Imatges
    "jpg", "jpeg", "png", "heic", "webp",
    # Documents bàsics
    "pdf", "csv"
}

def detectar_doble_extensio(nom_fitxer: str) -> Tuple[bool, str]:
    """Analitza el nom del fitxer per blocar ofuscacions de doble extensió (ex: document.pdf.exe)."""
    nom_net = nom_fitxer.strip().lower()
    
    # Comprovar si té múltiples punts i si l'última extensió és sospitosa o amagada
    parts = nom_net.split('.')
    if len(parts) <= 1:
        return False, "Només una extensió o cap."
        
    extensio_final = parts[-1]
    
    if extensio_final not in EXTENSIONS_PERMESES:
        return True, f"Extensió .{extensio_final} no permesa per seguretat."
        
    if len(parts) > 2:
        # Tenim coses tipus foto.jpg.zip
        return True, "Doble extensió detectada. Risc d'ofuscació de malware."
        
    # Validació de caràcters permesos al nom de fitxer
    if re.search(r'[<>:"/\\|?*\x00-\x1F]', nom_net):
        return True, "El nom del fitxer conté caràcters no permesos."
        
    return False, "OK"


def validar_magic_bytes(contingut_bytes: bytes) -> Tuple[bool, str]:
    """Utilitza la llibreria filetype per comprovar la signatura binària (Magic Bytes) real."""
    if not contingut_bytes:
        return False, "Arxiu buit."
        
    kind = filetype.guess(contingut_bytes)
    if kind is None:
        return False, "Format de fitxer desconegut a nivell binari."
        
    extensio_real = kind.extension.lower()
    if extensio_real not in EXTENSIONS_PERMESES:
        return False, f"Format binari .{extensio_real} no autoritzat pel sistema."
        
    return True, extensio_real


class RedisRateLimiter:
    """Control de concurrència i Rate Limiter suportat 100% per Redis (RF-07)."""
    def __init__(self, limit_per_minut: int = 10, redis_client: Optional[Redis] = None):
        self.redis = redis_client
        self.limit = limit_per_minut
        
    async def es_permes(self, user_id: int) -> bool:
        """Determina si un usuari pot enviar un altre missatge en la finestra de 1 minut."""
        key = f"rate_limit:telegram:{user_id}"
        
        # Algorisme simple de finestra rotatòria o limitador fix
        # Incrementar comptador
        current = await self.redis.incr(key)
        if current == 1:
            # Primera petició, assignem caducitat de 60 segons
            await self.redis.expire(key, 60)
            
        if current > self.limit:
            logger.warning(f"RATE LIMIT EXCEEDED for user {user_id}: {current}/{self.limit}")
            return False
            
        return True


# Alias per compatibilitat amb tests que importen RateLimiterTelegram
RateLimiterTelegram = RedisRateLimiter