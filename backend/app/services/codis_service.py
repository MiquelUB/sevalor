"""Servei de generació automàtica i seqüencial de codis multi-tenant (Clients i Proveïdors)."""

import re
import uuid
from typing import Type

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Client, Proveidor


async def generar_seguent_codi(
    db: AsyncSession,
    model: Type[Client] | Type[Proveidor],
    empresa_id: uuid.UUID,
    prefix: str,
) -> str:
    """Genera el següent codi seqüencial (p. ex. CLI-0001, PRV-0001) aïllat per empresa_id.

    Utilitza un bloqueig transaccional PostgreSQL (`pg_advisory_xact_lock`) amb clau
    derivada de la taula i de `empresa_id` per evitar condicions de carrera en altes
    concurrents fins i tot quan la taula és buida (Dia-0).
    """
    prefix_norm = prefix.strip().upper()
    lock_ns = f"{model.__tablename__}_codi"

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:ns), hashtext(:emp))"),
        {"ns": lock_ns, "emp": str(empresa_id)},
    )

    rows = (
        await db.execute(
            select(model.codi).where(model.empresa_id == empresa_id)
        )
    ).scalars().all()

    pattern = re.compile(rf"^{re.escape(prefix_norm)}-(\d+)$")
    existents: set[str] = set()
    max_num = 0

    for raw_codi in rows:
        if not raw_codi:
            continue
        codi_norm = str(raw_codi).strip().upper()
        existents.add(codi_norm)
        match = pattern.match(codi_norm)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    seguent = max_num + 1
    while True:
        candidat = f"{prefix_norm}-{seguent:04d}"
        if candidat not in existents:
            return candidat
        seguent += 1
