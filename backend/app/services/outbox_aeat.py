"""
Servei d'Outbox per a l'enviament telemàtic SOAP a la AEAT (Veri*factu).

Implementa l'Outbox Pattern (Spec 024 RF-07, RF-08):
- Desacoblament complet: la factura es consolida localment, i l'enviament
  SOAP a la AEAT es processa de forma asíncrona des de la cua PENDENT_REENVIAMENT.
- En cas de fallada o timeout, la factura roman a la cua per a reintents.
- Registre d'esdeveniments del SIF (Sistema d'Informació Fiscal).

La implementació real del client SOAP es realitzarà quan es disposi de les
credencials i endpoints de la AEAT (entorn pre-producció/producció).
Actualment es proporciona un stub que registra la intenció d'enviament.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("outbox_aeat")


def calcular_temps_reintent_exponencial(intents: int, base: float = 2.0) -> float:
    """Calcula el temps de reintent exponencial per a la Dead Letter Queue (RF-20)."""
    return base ** intents


class AEATSoapClient:
    """Client SOAP stub per a l'enviament de factures a la AEAT (a implementar amb credencials reals)."""
    def __init__(self, endpoint: str = "https://sede.aeat.gob.es/verifactu/soap"):
        self.endpoint = endpoint

    async def enviar_factura(self, factura_id: str, hash_sha256: str, ruta_pdf: str) -> dict:
        """Stub: registra la intenció d'enviament."""
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("AEAT SOAP Client stub: enviament simulat de factura %s", factura_id)
        return {
            "factura_id": factura_id,
            "estat": "ENVIAT_AEAT",
            "timestamp": timestamp,
            "nota": "Stub: implementar credencials AEAT per a enviament real",
        }

ESTAT_PENDENT = "PENDENT"
ESTAT_ENVIAT = "ENVIAT_AEAT"


async def registrar_enviament_outbox(
    factura_id: str,
    empresa_id: str,
    serie: str,
    numero: int,
    hash_sha256: str,
    ruta_pdf: str,
    db_session: object | None = None,
) -> dict:
    """
    Registra la intenció d'enviament al SIF (Outbox).

    La factura es marca com a PENDENT_REENVIAMENT en la base de dades.
    El worker de Celery (queue_critical) processarà l'enviament SOAP real.

    Args:
        factura_id: UUID de la factura.
        empresa_id: UUID de l'empresa tenant.
        serie: Sèrie de la factura.
        numero: Número de factura.
        hash_sha256: Hash SHA-256 de la factura.
        ruta_pdf: Ruta al PDF generat.
        db_session: Sessió de BD (opcional; si no es proveeix, es deixa registre en log).

    Returns:
        dict amb estat de registre.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(
        "OUTBOX: Factura %s/%s-%d registrada per enviament AEAT. "
        "Hash: %s | PDF: %s | Timestamp: %s",
        empresa_id, serie, numero, hash_sha256, ruta_pdf, timestamp,
    )

    if db_session is not None:
        from sqlalchemy import text
        await db_session.execute(
            text("""
                UPDATE factures_capcalera
                SET estat_enviament = :estat,
                    updated_at = NOW()
                WHERE id = CAST(:factura_id AS UUID)
            """),
            {"estat": ESTAT_PENDENT, "factura_id": factura_id},
        )
        await db_session.commit()

    return {
        "factura_id": factura_id,
        "estat": ESTAT_PENDENT,
        "timestamp": timestamp,
    }


async def processar_enviament_aeat(
    factura_id: str,
    empresa_id: str,
    serie: str,
    numero: int,
    hash_sha256: str,
    ruta_pdf: str,
) -> dict:
    """
    Processa l'enviament SOAP a la AEAT.

    >>> IMPLEMENTACIÓ PENDENT <<<
    Quan es disposi de les credencials i endpoints reals de la AEAT,
    aquí es realitzarà la crida SOAP amb les dades de la factura.

    Actualment: stub que simula un enviament correcte i registra la traça.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Simular enviament AEAT (a substituir per SOAP real)
    import asyncio
    await asyncio.sleep(0.01)  # Simular latència de xarxa

    logger.info(
        "AEAT SOAP: Factura %s (sèrie %s, num %d) enviada correctament. "
        "Hash: %s | Timestamp: %s",
        factura_id, serie, numero, hash_sha256, timestamp,
    )

    return {
        "factura_id": factura_id,
        "estat": "ENVIAT_AEAT",
        "timestamp": timestamp,
        "nota": "Stub d'enviament SOAP. Implementar client real amb credencials AEAT.",
    }


# Alias per compatibilitat amb tests existents
processar_outbox_local_tenant = registrar_enviament_outbox
