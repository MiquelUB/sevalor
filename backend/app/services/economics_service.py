import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contractes import ContracteManteniment


async def calculate_mrr(db: AsyncSession, empresa_uuid: uuid.UUID) -> float:
    """
    Calculate Monthly Recurring Revenue (MRR) based on active contracts.
    Formula: SUM(import_anual) / 12 for all active contracts.
    """
    stmt = select(func.coalesce(func.sum(ContracteManteniment.import_anual), 0.0)).where(
        ContracteManteniment.empresa_id == empresa_uuid, ContracteManteniment.estat == "ACTIU"
    )
    total_anual = await db.scalar(stmt)
    if total_anual:
        return float(total_anual) / 12.0
    return 0.0
