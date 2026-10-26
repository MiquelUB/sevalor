"""Servei de validació MX Shield per a protecció del domini i deliverability.

Funcionalitats:
1. Validació estricta de sintaxi d'email segons RFC 5322.
2. Detecció i bloqueig de dominis d'un sol ús o temporals (disposable email providers).
3. Comprovació contra la llista negra persistent d'exclusió RGPD / LSSI (`saas_exclusio_rgpd`).
4. Resolució asíncrona de registres DNS MX mitjançant dnspython (`dns.asyncresolver`).
5. Protecció integral de la reputació de `tecnic@sevalor.net`.
"""

import logging
import re
from typing import List, Optional, Set, Tuple

import dns.asyncresolver
import dns.exception
import dns.resolver
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import SaasExclusioRgpd
from app.services.firecrawl_service import normalitzar_domini

logger = logging.getLogger("sevalor.crm.mx_shield")

# Patró de sintaxi RFC 5322 simplificat i segur contra ReDoS
PATRO_EMAIL_RFC5322 = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

# Llista negra de proveïdors de correu temporal / descartable (Anti-Spam / Anti-Bounce)
DOMINIS_DESCRIPTIBLES: Set[str] = {
    "mailinator.com",
    "yopmail.com",
    "guerrillamail.com",
    "guerrillamailblock.com",
    "10minutemail.com",
    "tempmail.com",
    "throwawaymail.com",
    "trashmail.com",
    "sharklasers.com",
    "dispostable.com",
    "getairmail.com",
    "maildrop.cc",
    "inboxkitten.com",
    "mohmal.com",
    "fakeinbox.com",
    "burnermail.io",
}


def validar_sintaxi_email(email: Optional[str]) -> bool:
    """Verifica si la cadena té un format d'adreça de correu vàlid segons RFC 5322."""
    if not email or len(email) > 254:
        return False
    return bool(PATRO_EMAIL_RFC5322.match(email.strip()))


def extreure_domini_email(email: str) -> str:
    """Extreu i normalitza el domini d'una adreça de correu."""
    if "@" not in email:
        return ""
    parts = email.strip().split("@")
    return normalitzar_domini(parts[-1])


def es_domini_temporal(domini: str) -> bool:
    """Determina si un domini pertany a un servei d'email d'un sol ús."""
    dom_norm = normalitzar_domini(domini)
    return dom_norm in DOMINIS_DESCRIPTIBLES


async def comprovar_exclusio_rgpd(
    email: str,
    db: AsyncSession,
) -> Tuple[bool, Optional[str]]:
    """Comprova si l'email o el seu domini figuren a la llista d'exclusió RGPD/LSSI."""
    domini = extreure_domini_email(email)
    condicions = [SaasExclusioRgpd.email == email.strip().lower()]
    if domini:
        condicions.append(SaasExclusioRgpd.domini == domini)

    stmt = select(SaasExclusioRgpd).where(or_(*condicions))
    res = await db.execute(stmt)
    registre = res.scalars().first()

    if registre:
        return True, f"Inscrit a la llista d'exclusió RGPD ({registre.motiu})"
    return False, None


async def verificar_registres_dns_mx(
    domini: str,
    timeout_segons: float = 3.5,
) -> Tuple[bool, str, List[str]]:
    """Consulta asíncronament els servidors de correu DNS MX per a un domini.

    Args:
        domini: Domini d'Internet a consultar (sense protocol ni www).
        timeout_segons: Temps màxim d'espera per a la consulta DNS.

    Returns:
        Tupla `(es_valid, motiu_o_estat, llista_servidors_mx)`
    """
    clean_domain = normalitzar_domini(domini)
    if not clean_domain:
        return False, "DOMINI_BUIT", []

    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = timeout_segons
    resolver.lifetime = timeout_segons

    try:
        respostes = await resolver.resolve(clean_domain, "MX")
        servidors = [str(r.exchange).rstrip(".").lower() for r in respostes]
        if servidors:
            return True, "MX_VALID", servidors
        return False, "SENSE_REGISTRES_MX", []

    except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return False, "DOMINI_INEXISTENT", []

    except dns.resolver.NoAnswer:
        # Si no té registres MX, segons RFC 5321 es pot utilitzar el registre A
        try:
            res_a = await resolver.resolve(clean_domain, "A")
            ips = [str(r) for r in res_a]
            if ips:
                return True, "MX_FALLBACK_REGISTRE_A", ips
        except Exception:
            pass
        return False, "SENSE_REGISTRES_MX", []

    except dns.exception.Timeout:
        logger.warning("Timeout DNS en consultar registres MX per al domini: %s", clean_domain)
        return False, "TIMEOUT_DNS", []

    except Exception as exc:
        logger.info("Error DNS en consultar domini %s: %s", clean_domain, exc)
        return False, f"ERROR_DNS_{type(exc).__name__}", []


async def validar_email_mx(
    email: Optional[str],
    db: Optional[AsyncSession] = None,
) -> Tuple[bool, str]:
    """Validació completa en 4 etapes per garantir la màxima autoritat de lliurament.

    Etapes:
    1. Validació de sintaxi RFC 5322.
    2. Comprovació de dominis temporals / d'un sol ús.
    3. Comprovació contra `saas_exclusio_rgpd` (si es passa la sessió de BD).
    4. Consulta DNS MX en viu.

    Args:
        email: Adreça de correu a validar.
        db: Sessió opcional per verificar exclusió RGPD a PostgreSQL.

    Returns:
        Tupla `(es_valid, codi_estat)`
        Exemples d'estat: 'MX_VALID', 'ERROR_SINTAXI', 'DOMINI_TEMPORAL',
                          'BLOQUEJAT_RGPD', 'DOMINI_INEXISTENT', 'SENSE_REGISTRES_MX'.
    """
    if not email:
        return False, "EMAIL_BUIT"

    clean_email = email.strip().lower()

    # 1. Sintaxi
    if not validar_sintaxi_email(clean_email):
        return False, "ERROR_SINTAXI"

    domini = extreure_domini_email(clean_email)
    if not domini:
        return False, "DOMINI_INVALID"

    # 2. Dominis d'un sol ús
    if es_domini_temporal(domini):
        return False, "DOMINI_TEMPORAL"

    # 3. Comprovació RGPD a la base de dades
    if db is not None:
        es_exclos, motiu = await comprovar_exclusio_rgpd(clean_email, db)
        if es_exclos:
            return False, "BLOQUEJAT_RGPD"

    # 4. Resolució DNS MX
    mx_ok, estat_dns, _ = await verificar_registres_dns_mx(domini)
    if not mx_ok:
        return False, estat_dns

    return True, "MX_VALID"
