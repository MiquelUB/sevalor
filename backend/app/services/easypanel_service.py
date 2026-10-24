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
            if not dns_res.get("resolt", False):
                logger.warning(
                    f"[EasyPanel] Pre-validació DNS fallida per a '{domini_clean}'. "
                    "Evitant crida a EasyPanel per protegir quota Let's Encrypt."
                )
                return {
                    "ok": False,
                    "status": "PENDENT_DNS",
                    "detail": dns_res.get("detail", "DNS no resolt"),
                    "ips": dns_res.get("ips", []),
                }

        # 2. Comprovació de configuració EasyPanel
        token = settings.easypanel_token
        url_base = settings.EASYPANEL_URL or (
            f"http://{settings.PLATFORM_EDGE_IP}:3000" if settings.PLATFORM_EDGE_IP else "http://127.0.0.1:3000"
        )
        project = settings.easypanel_project or "sevalor"
        service = settings.easypanel_service
        # Normalitzar el servei frontend: a EasyPanel el servei Next.js és 'sevalor-pwa'
        if service in ("pwa", "frontend", None, ""):
            service = "sevalor-pwa"

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

        del_url = f"{url_base.rstrip('/')}/api/deleteDomain"
        list_url = f"{url_base.rstrip('/')}/api/listDomains"
        create_url = f"{url_base.rstrip('/')}/api/createDomain"
        update_url = f"{url_base.rstrip('/')}/api/updateDomain"
        target_domain_id = f"{project}-{service}-{domini_clean.replace('.', '-')}"

        rest_payload = {
            "id": target_domain_id,
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

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # PAS 1: Purgar qualsevol registre previ d'aquest domini a EasyPanel (Anti-Conflict)
                # D'aquesta manera s'eliminen associacions orfes amb serveis antics ('pwa') o IDs desalineats.
                try:
                    list_res = await client.get(
                        list_url,
                        headers=headers,
                        params={"projectName": project},
                    )
                    if list_res.status_code == 200:
                        raw_domains = list_res.json()
                        domain_list = raw_domains if isinstance(raw_domains, list) else raw_domains.get("data", [])
                        if isinstance(domain_list, list):
                            for item in domain_list:
                                item_host = str(item.get("host", "")).strip().rstrip("/").lower()
                                item_id = str(item.get("id", ""))
                                if item_host == domini_clean or item_id.endswith(domini_clean.replace(".", "-")):
                                    logger.info(
                                        f"[EasyPanel] Detectat domini previ '{item_host}' (ID: {item_id}). Purgant per refrescar router Traefik..."
                                    )
                                    await client.post(del_url, headers=headers, json={"id": item_id})
                except Exception as list_err:
                    logger.warning(f"[EasyPanel] No s'ha pogut llistar dominis existents per purgar: {list_err}")

                # Purgat preventiu d'IDs coneguts que hagin pogut quedar orfes
                proactive_ids = {
                    f"{project}-pwa-{domini_clean.replace('.', '-')}",
                    f"{project}-sevalor-pwa-{domini_clean.replace('.', '-')}",
                    target_domain_id,
                }
                for leg_id in proactive_ids:
                    try:
                        await client.post(del_url, headers=headers, json={"id": leg_id})
                    except Exception:
                        pass

                # PAS 2: Registrar el domini oficialment al servei Next.js PWA actiu
                res = await client.post(create_url, headers=headers, json=rest_payload)
                if res.status_code in (200, 201):
                    logger.info(f"[EasyPanel] Domini '{domini_clean}' registrat amb èxit a '{project}/{service}'.")
                    return {
                        "ok": True,
                        "status": "SSL_ACTIU",
                        "detail": f"Domini '{domini_clean}' registrat correctament a EasyPanel (servei '{service}') amb certificat SSL automàtic.",
                    }

                # PAS 3: Si EasyPanel al·lega que ja existeix, provar actualització directa amb updateDomain
                if res.status_code == 400 and "already used" in res.text.lower():
                    logger.info("[EasyPanel] Domini ja existent segons validador. Aplicant updateDomain...")
                    up_res = await client.post(update_url, headers=headers, json=rest_payload)
                    if up_res.status_code in (200, 201):
                        logger.info(f"[EasyPanel] Domini '{domini_clean}' actualitzat amb èxit via updateDomain.")
                        return {
                            "ok": True,
                            "status": "SSL_ACTIU",
                            "detail": f"Domini '{domini_clean}' actualitzat correctament a EasyPanel (servei '{service}') amb certificat SSL automàtic.",
                        }

                logger.warning(
                    f"[EasyPanel] Resposta {res.status_code} afegint domini '{domini_clean}': {res.text}"
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

        token = settings.easypanel_token
        url_base = settings.EASYPANEL_URL or (
            f"http://{settings.PLATFORM_EDGE_IP}:3000" if settings.PLATFORM_EDGE_IP else "http://127.0.0.1:3000"
        )
        project = settings.easypanel_project or "sevalor"
        service = settings.easypanel_service
        if service in ("pwa", "frontend", None, ""):
            service = "sevalor-pwa"

        if not token:
            return {"ok": False, "detail": "Token d'EasyPanel no configurat."}

        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": token,
            "Content-Type": "application/json",
        }

        del_url = f"{url_base.rstrip('/')}/api/deleteDomain"
        list_url = f"{url_base.rstrip('/')}/api/listDomains"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # 1. Buscar per host a la llista de dominis
                try:
                    list_res = await client.get(
                        list_url,
                        headers=headers,
                        params={"projectName": project},
                    )
                    if list_res.status_code == 200:
                        raw_domains = list_res.json()
                        domain_list = raw_domains if isinstance(raw_domains, list) else raw_domains.get("data", [])
                        if isinstance(domain_list, list):
                            for item in domain_list:
                                item_host = str(item.get("host", "")).strip().rstrip("/").lower()
                                item_id = str(item.get("id", ""))
                                if item_host == domini_clean or item_id.endswith(domini_clean.replace(".", "-")):
                                    await client.post(del_url, headers=headers, json={"id": item_id})
                except Exception as e:
                    logger.warning(f"[EasyPanel] Error llistant dominis per eliminar: {e}")

                # 2. Purgar per IDs coneguts
                proactive_ids = {
                    f"{project}-{service}-{domini_clean.replace('.', '-')}",
                    f"{project}-pwa-{domini_clean.replace('.', '-')}",
                    f"{project}-sevalor-pwa-{domini_clean.replace('.', '-')}",
                }
                for pid in proactive_ids:
                    try:
                        await client.post(del_url, headers=headers, json={"id": pid})
                    except Exception:
                        pass

                return {"ok": True, "status": "ELIMINAT"}
        except Exception as exc:
            logger.error(f"[EasyPanel] Error eliminant domini '{domini_clean}': {exc}")
            return {"ok": False, "detail": str(exc)}

