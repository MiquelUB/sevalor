import uuid
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import FacturaProveidor, RegistreJornadaLaboral, Usuari, FacturaCapcalera, FullaPicking, LiniaPicking, Article

async def update_dashboard(db: AsyncSession, empresa_uuid: uuid.UUID):
    # Despeses materials del mes: sum(FacturaProveidor.base_imposable) 
    stmt_mat = select(func.coalesce(func.sum(FacturaProveidor.base_imposable), 0)).where(
        FacturaProveidor.empresa_id == empresa_uuid,
        text("EXTRACT(MONTH FROM data_factura) = EXTRACT(MONTH FROM CURRENT_DATE)"),
        text("EXTRACT(YEAR FROM data_factura) = EXTRACT(YEAR FROM CURRENT_DATE)")
    )
    despeses_mat = await db.scalar(stmt_mat) or 0.0

    # Despeses salaris del mes: RegistreJornadaLaboral.hores_ordinaries * Usuari.cost_hora_eur
    stmt_sal = select(
        func.coalesce(func.sum(RegistreJornadaLaboral.hores_ordinaries * Usuari.cost_hora_eur), 0)
    ).join(Usuari, RegistreJornadaLaboral.usuari_id == Usuari.id).where(
        RegistreJornadaLaboral.empresa_id == empresa_uuid,
        text("EXTRACT(MONTH FROM data_jornada) = EXTRACT(MONTH FROM CURRENT_DATE)"),
        text("EXTRACT(YEAR FROM data_jornada) = EXTRACT(YEAR FROM CURRENT_DATE)")
    )
    despeses_sal = await db.scalar(stmt_sal) or 0.0
    return float(despeses_mat), float(despeses_sal)
