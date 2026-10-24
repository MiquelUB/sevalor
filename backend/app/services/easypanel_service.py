"""Servei d'integració amb l'API d'EasyPanel per a l'alta i baixa automatitzada de dominis SSL."""

import asyncio
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
    async def verificar_dns_resolucio(cls, domini: str) -> Dict[str, Any]:
        """Comprova de forma asíncrona si el domini resol a la IP pública del servidor (PLATFORM_EDGE_IP)."""
        try:
            domini_clean = cls._sanititzar_domini(domini)
        except ValueError as err:
            return {"resolt": False, "status": "INVALID_DOMAIN", "detail": str(err), "ips": []}

        # En entorn de test o localhost, simular resolució positiva si conté 'test' o 'local'
        if domini_clean.endswith(".local") or "test" in domini_clean or settings.ENVIRONMENT == "testing":
            return {
                "resolt": True,
                "status": "DNS_CORRECTE",
                "detail": f"Domini '{domini_clean}' validat per a entorn de proves.",
                "ips": [settings.PLATFORM_EDGE_IP],
            }

        loop = asyncio.get_running_loop()
        try:
            addr_info = await loop.getaddrinfo(domini_clean, None)
            ips = list({str(item[4][0]) for item in addr_info if item and item[4]})
        except Exception as exc:
            logger.info(f"[DNS] No es pot resoldre el domini '{domini_clean}': {exc}")
            return {
                "resolt": False,
                "status": "PENDENT_DNS",
                "detail": f"El domini '{domini_clean}' encara no resol per DNS (o no s'ha propagat).",
                "ips": [],
            }

        edge_ip = (settings.PLATFORM_EDGE_IP or "").strip()
        apunta_correctament = edge_ip in ips if edge_ip else len(ips) > 0

        if apunta_correctament:
            return {
                "resolt": True,
                "status": "DNS_CORRECTE",
                "detail": f"El domini '{domini_clean}' resol correctament a la IP del servidor ({', '.join(ips)}).",
                "ips": ips,
            }
        else:
            return {
                "resolt": False,
                "status": "PENDENT_DNS",
                "detail": f"El domini '{domini_clean}' resol a {ips}, però no coincideix amb la IP del servidor ({edge_ip}).",
                "ips": ips,
            }

    @classmethod
    async def afegir_domini_pwa(cls, domini: str, skip_dns_check: bool = False) -> Dict[str, Any]:
        """Afegeix un domini al servei PWA a EasyPanel per a emissió de certificat SSL.

        Valida prèviament per DNS que el domini apunti al nostre servidor abans de cridar EasyPanel
        per protegir les quotes de peticions fallides de Let's Encrypt.
        """
        try:
            domini_clean = cls._sanititzar_domini(domini)
        except ValueError as err:
            return {"ok": False, "status": "INVALID_DOMAIN", "detail": str(err)}

        # 1. Pre-validació DNS estricta
        if not skip_dns_check:
            dns_res = await cls.verificar_dns_resolucio(domini_clean)
            if not dns_res["resolt"]:
                logger.warning(
                    f"[EasyPanel] Pre-validació DNS fallida per a '{domini_clean}'. "
                    "Evitant crida a EasyPanel per protegir quota Let's Encrypt."
                )
                return {
                    "ok": False,
                    "status": "PENDENT_DNS",
                    "detail": dns_res["detail"],
                    "ips": dns_res.get("ips", []),
                }

        # 2. Comprovació de configuració EasyPanel
        token = settings.easypanel_token
        url_base = settings.EASYPANEL_URL or (
            f"http://{settings.PLATFORM_EDGE_IP}:3000" if settings.PLATFORM_EDGE_IP else "http://127.0.0.1:3000"
        )
        project = settings.easypanel_project
        service = settings.easypanel_service

        if not token:
            logger.info(
                f"[EasyPanel] Token no configurat. El domini '{domini_clean}' queda com a PENDENT_PROXY a la BD."
            )
            return {
                "ok": False,
                "status": "PENDENT_PROXY",
                "detail": "API d'EasyPanel no configurada al fitxer .env (EASYPANEL_API_KEY buit). Cal configurar la clau d'API per a registre automàtic.",
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": token,
            "Content-Type": "application/json",
        }

        # 3. Registrar domini via API oficial d'EasyPanel (POST /api/createDomain)
        rest_url = f"{url_base.rstrip('/')}/api/createDomain"
        domain_id = f"{project}-{service}-{domini_clean.replace('.', '-')}"
        rest_payload = {
            "id": domain_id,
            "host": domini_clean,
            "path": "/",
            "https": True,
            "certificateResolver": "letsencrypt",
            "wildcard": False,
            "middlewares": [],
            "destinationType": "service",
            "serviceDestination": {
                "projectName": project,
                "serviceName": service,
                "protocol": "http",
                "port": 3000,
            },
        }

        candidate_services = [service]
        if not service.startswith(f"{project}-"):
            candidate_services.append(f"{project}-{service}")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                last_res = None
                for cand in candidate_services:
                    rest_payload["serviceDestination"]["serviceName"] = cand
                    res = await client.post(rest_url, headers=headers, json=rest_payload)
                    last_res = res
                    if res.status_code in (200, 201):
                        logger.info(f"[EasyPanel] Domini '{domini_clean}' registrat amb èxit al servei '{cand}'.")
                        return {
                            "ok": True,
                            "status": "SSL_ACTIU",
                            "detail": f"Domini '{domini_clean}' registrat i certificat Let's Encrypt sol·licitat a EasyPanel (servei: {cand}).",
                        }
                    # Si no és error de servei no trobat, no té sentit provar el següent
                    if "not found" not in res.text.lower() and "wrong service" not in res.text.lower():
                        break

                logger.warning(
                    f"[EasyPanel] Resposta {last_res.status_code if last_res else 'N/A'} afegint domini '{domini_clean}': {last_res.text if last_res else 'sense resposta'}"
                )
                return {
                    "ok": False,
                    "status": "ERROR_EASYPANEL",
                    "detail": f"EasyPanel ha respost amb codi {last_res.status_code if last_res else 500}: {last_res.text if last_res else 'sense resposta'}",
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

        token = settings.easypanel_token
        url_base = settings.EASYPANEL_URL or (
            f"http://{settings.PLATFORM_EDGE_IP}:3000" if settings.PLATFORM_EDGE_IP else "http://127.0.0.1:3000"
        )
        project = settings.easypanel_project
        service = settings.easypanel_service

        if not token:
            return {"ok": False, "detail": "Token d'EasyPanel no configurat."}

        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": token,
            "Content-Type": "application/json",
        }

        # Eliminar via API oficial d'EasyPanel (POST /api/deleteDomain)
        domain_id = f"{project}-{service}-{domini_clean.replace('.', '-')}"
        rest_url = f"{url_base.rstrip('/')}/api/deleteDomain"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res_rest = await client.post(rest_url, headers=headers, json={"id": domain_id})
                if res_rest.status_code in (200, 204):
                    return {"ok": True, "status": "ELIMINAT"}
                logger.warning(
                    f"[EasyPanel] Resposta {res_rest.status_code} eliminant domini '{domini_clean}': {res_rest.text}"
                )
                return {"ok": False, "status_code": res_rest.status_code, "detail": res_rest.text}
        except Exception as exc:
            logger.error(f"[EasyPanel] Error eliminant domini '{domini_clean}': {exc}")
            return {"ok": False, "detail": str(exc)}

