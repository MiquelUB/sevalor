import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    Article,
    Client,
    FacturaCapcalera,
    FacturaLinia,
    FacturaProveidor,
    FullaPicking,
    LiniaPicking,
    OrdreTreball,
    RegistreJornadaLaboral,
    Usuari,
)

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
        # Calcular facturat
        stmt_fact = select(func.coalesce(func.sum(FacturaLinia.subtotal), 0)).where(
            FacturaLinia.obra_id == ordre.id, FacturaLinia.empresa_id == empresa_uuid
        )
        facturat = await db.scalar(stmt_fact) or 0.0

        # Cost materials consumits en aquesta ordre
        stmt_mat = (
            select(
                func.coalesce(
                    func.sum(
                        (
                            LiniaPicking.quantitat_carregada_pick_in
                            - LiniaPicking.quantitat_retornada_pick_out
                            - LiniaPicking.quantitat_mermada
                        )
                        * Article.preu_cost
                    ),
                    0,
                )
            )
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(
                FullaPicking.ordre_treball_id == ordre.id, LiniaPicking.empresa_id == empresa_uuid
            )
        )
        cost_materials = await db.scalar(stmt_mat) or 0.0

        # PENDENT_AUDITORIA: Com que no hi ha taulell d'imputació directe d'hores a OrdreTreball,
        # només tenim RegistreJornadaLaboral general o AuditoriaPostObra.desviacio_hores.
        # Es manté a 0 segons requeriments de dades reals quan no hi ha vincle.
        hores_treballades = 0.0
        cost_operari = 0.0

        marge = float(facturat) - float(cost_materials) - float(cost_operari)

        res.append(
            RendibilitatObra(
                ordre_treball_id=ordre.id,
                codi=ordre.codi,
                titol=ordre.titol,
                client_id=client.id,
                client_nom=client.rao_social,
                hores_treballades=hores_treballades,
                cost_operari=cost_operari,
                cost_materials=float(cost_materials),
                import_facturat=float(facturat),
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
