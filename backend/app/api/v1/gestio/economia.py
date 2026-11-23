import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    Client,
    FacturaCapcalera,
    FacturaProveidor,
    OrdreTreball,
    RegistreJornadaLaboral,
    Usuari,
)
from app.services.magatzem_comptabilitat_service import calcular_cost_i_marge_analitic_ot

router = APIRouter(
    prefix="/gestio/economia",
    tags=["Gestió Economia"],
    dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))],
)


class RendibilitatObra(BaseModel):
    ordre_treball_id: uuid.UUID
    codi: str
    titol: str
    client_id: uuid.UUID
    client_nom: str
    hores_treballades: float
    cost_operari: float
    cost_materials: float
    import_facturat: float
    marge_brut: float


class DashboardFinancer(BaseModel):
    ingressos_mensuals: float
    despeses_materials: float
    despeses_salaris: float
    marge_brut: float
    factures_pendents: int


@router.get("/rendibilitat", response_model=List[RendibilitatObra])
async def llistar_rendibilitat(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    empresa_uuid = uuid.UUID(empresa_id)

    stmt = (
        select(OrdreTreball, Client)
        .join(Client, OrdreTreball.client_id == Client.id)
        .where(OrdreTreball.empresa_id == empresa_uuid)
    )
    result = await db.execute(stmt)
    rows = result.all()

    res = []
    for ordre, client in rows:
        analitic = await calcular_cost_i_marge_analitic_ot(
            db=db,
            empresa_id=empresa_uuid,
            ordre_treball_id=ordre.id,
        )
        desgl = analitic["desglossament_costos"]
        cost_materials = float(desgl["materials_picking_pmp_eur"]) + float(
            desgl["mermes_imputades_eur"]
        )
        cost_operari = float(desgl["ma_obra_real_eur"])
        hores_treballades = float(analitic.get("hores_treballades_reals", 0.0))
        facturat = float(analitic["ingressos_nets_eur"])
        marge = float(analitic["marge_brut_eur"])

        res.append(
            RendibilitatObra(
                ordre_treball_id=ordre.id,
                codi=ordre.codi,
                titol=ordre.titol,
                client_id=client.id,
                client_nom=client.rao_social,
                hores_treballades=hores_treballades,
                cost_operari=cost_operari,
                cost_materials=cost_materials,
                import_facturat=facturat,
                marge_brut=marge,
            )
        )

    return res


@router.get("/dashboard", response_model=DashboardFinancer)
async def obtenir_dashboard(
    request: Request, db: AsyncSession = Depends(get_db_with_tenant_context)
):
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401)

    empresa_uuid = uuid.UUID(empresa_id)

    # Ingressos mensuals
    stmt_ingressos = select(func.coalesce(func.sum(FacturaCapcalera.base_imposable), 0)).where(
        FacturaCapcalera.empresa_id == empresa_uuid,
        text("EXTRACT(MONTH FROM data_emissio) = EXTRACT(MONTH FROM CURRENT_DATE)"),
        text("EXTRACT(YEAR FROM data_emissio) = EXTRACT(YEAR FROM CURRENT_DATE)"),
    )
    ingressos = await db.scalar(stmt_ingressos) or 0.0

    # Factures pendents
    stmt_pendents = select(func.count(FacturaCapcalera.id)).where(
        FacturaCapcalera.empresa_id == empresa_uuid, FacturaCapcalera.estat_cobrament == "PENDENT"
    )
    pendents = await db.scalar(stmt_pendents) or 0

    # Despeses materials del mes: Factures Proveidor
    stmt_mat = select(func.coalesce(func.sum(FacturaProveidor.base_imposable), 0)).where(
        FacturaProveidor.empresa_id == empresa_uuid,
        text("EXTRACT(MONTH FROM data_factura) = EXTRACT(MONTH FROM CURRENT_DATE)"),
        text("EXTRACT(YEAR FROM data_factura) = EXTRACT(YEAR FROM CURRENT_DATE)"),
    )
    despeses_mat = await db.scalar(stmt_mat) or 0.0

    # Despeses salaris del mes: Hores ordinaries * cost hora
    stmt_sal = (
        select(
            func.coalesce(
                func.sum(RegistreJornadaLaboral.hores_ordinaries * Usuari.cost_hora_eur), 0
            )
        )
        .join(Usuari, RegistreJornadaLaboral.usuari_id == Usuari.id)
        .where(
            RegistreJornadaLaboral.empresa_id == empresa_uuid,
            text("EXTRACT(MONTH FROM data_jornada) = EXTRACT(MONTH FROM CURRENT_DATE)"),
            text("EXTRACT(YEAR FROM data_jornada) = EXTRACT(YEAR FROM CURRENT_DATE)"),
        )
    )
    despeses_sal = await db.scalar(stmt_sal) or 0.0

    marge_brut = float(ingressos) - float(despeses_mat) - float(despeses_sal)

    return DashboardFinancer(
        ingressos_mensuals=float(ingressos),
        despeses_materials=float(despeses_mat),
        despeses_salaris=float(despeses_sal),
        marge_brut=marge_brut,
        factures_pendents=int(pendents),
    )
