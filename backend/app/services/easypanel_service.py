"""Servei d'integració amb l'API d'EasyPanel per a l'alta i baixa automatitzada de dominis SSL."""

import logging
import re
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger("sevalor.easypanel")


class EasypanelService:
    """Gestiona de forma programàtica els dominis i certificats Let's Encrypt a EasyPanel."""

    @staticmethod
    def _sanititzar_domini(domini: str) -> str:
        """Neteja i valida sintàcticament que el domini sigui un FQDN legítim (Anti-Injection)."""
        d = (
            domini.strip()
            .lower()
            .replace("https://", "")
            .replace("http://", "")
            .split("/")[0]
            .split(":")[0]
        )
        if not re.match(r"^(?:[a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,63}$", d):
            raise ValueError(f"El format del domini '{d}' no és un FQDN vàlid.")
        return d

    @classmethod
    async def afegir_domini_pwa(cls, domini: str) -> Dict[str, Any]:
        """Afegeix un domini al servei PWA a EasyPanel per a emissió de certificat SSL."""
        try:
            domini_clean = cls._sanititzar_domini(domini)
        except ValueError as err:
            return {"ok": False, "status": "INVALID_DOMAIN", "detail": str(err)}

        if not settings.EASYPANEL_URL or not settings.EASYPANEL_API_TOKEN:
            logger.info(
                f"[EasyPanel] Token no configurat. El domini '{domini_clean}' queda com a PENDENT_PROXY a la BD."
            )
            return {
                "ok": False,
                "status": "PENDENT_PROXY",
                "detail": "API d'EasyPanel no configurada al fitxer .env (EASYPANEL_API_TOKEN buit). Cal registrar el domini manualment o configurar les credencials.",
            }

        url = f"{settings.EASYPANEL_URL.rstrip('/')}/api/createDomain"
        headers = {
            "Authorization": f"Bearer {settings.EASYPANEL_API_TOKEN}",
            "Content-Type": "application/json",
        }

        domain_id = f"{settings.EASYPANEL_PROJECT}-{settings.EASYPANEL_SERVICE_PWA}-{domini_clean.replace('.', '-')}"
        payload = {
            "id": domain_id,
            "host": domini_clean,
            "path": "/",
            "https": True,
            "certificateResolver": "letsencrypt",
            "wildcard": False,
            "middlewares": [],
            "destinationType": "service",
            "serviceDestination": {
                "projectName": settings.EASYPANEL_PROJECT,
                "serviceName": settings.EASYPANEL_SERVICE_PWA,
                "protocol": "http",
                "port": 3000,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code in (200, 201):
                    logger.info(f"[EasyPanel] Domini '{domini_clean}' registrat amb èxit a EasyPanel.")
                    return {
                        "ok": True,
                        "status": "SSL_ACTIU",
                        "detail": "Domini registrat i certificat Let's Encrypt sol·licitat a EasyPanel.",
                    }
                else:
                    logger.warning(
                        f"[EasyPanel] Error afegint domini '{domini_clean}': HTTP {res.status_code} - {res.text}"
                    )
                    return {
                        "ok": False,
                        "status": "ERROR_EASYPANEL",
                        "detail": f"EasyPanel ha respost amb codi {res.status_code}: {res.text}",
                    }
        except Exception as exc:
            logger.error(f"[EasyPanel] Excepció en connectar amb EasyPanel: {exc}")
            return {
                "ok": False,
                "status": "ERROR_CONNEXIO",
                "detail": f"No s'ha pogut connectar amb el servidor d'EasyPanel: {str(exc)}",
            }

    @classmethod
    async def eliminar_domini_pwa(cls, domini: str) -> Dict[str, Any]:
        """Elimina un domini d'EasyPanel quan una empresa es dona de baixa (Anti-Dangling DNS)."""
        try:
            domini_clean = cls._sanititzar_domini(domini)
        except ValueError as err:
            return {"ok": False, "detail": str(err)}

        if not settings.EASYPANEL_URL or not settings.EASYPANEL_API_TOKEN:
            return {"ok": False, "detail": "EasyPanel no configurat."}

        domain_id = f"{settings.EASYPANEL_PROJECT}-{settings.EASYPANEL_SERVICE_PWA}-{domini_clean.replace('.', '-')}"
        url = f"{settings.EASYPANEL_URL.rstrip('/')}/api/deleteDomain"
        headers = {
            "Authorization": f"Bearer {settings.EASYPANEL_API_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json={"id": domain_id})
                return {"ok": res.status_code in (200, 204), "status_code": res.status_code}
        except Exception as exc:
            logger.error(f"[EasyPanel] Error eliminant domini '{domini_clean}': {exc}")
            return {"ok": False, "detail": str(exc)}
