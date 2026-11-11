import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import require_roles
from app.models.models import (
    Article,
    EstocMagatzem,
    Incidencia,
    Magatzem,
    TiquetCarburant,
    Usuari,
    Vehicle,
)
from app.services.flota_service import sincronitzar_vehicle_al_disc_empresa
from app.services.sovereign_storage import SovereignStorageGateway

JERARQUIA_CARNETS: dict[str, int] = {"AM": 1, "B": 2, "B+E": 3, "C": 4, "C+E": 5}


def validar_assignacio_vehicle_operari(vehicle: dict, operari: dict) -> bool:
    """Valida si un operari pot agafar un vehicle a l'inici de jornada PWA."""
    estat_flota = vehicle.get("estat_operatiu_flota") or {}
    apte_pwa = estat_flota.get("apte_assignacio_pwa", vehicle.get("apte_assignacio_pwa", True))
    estat_semafor = estat_flota.get("estat_semafor", vehicle.get("estat_semafor", "OPERATIU_OK"))
    if not apte_pwa:
        raise HTTPException(
            status_code=403,
            detail=f"Vehicle bloquejat operativament: {estat_semafor}",
        )

    req = vehicle.get("requisits_operari") or {}
    carnet_req = req.get("carnet_minim") or vehicle.get("carnet_necessari") or "B"
    nivell_req = JERARQUIA_CARNETS.get(carnet_req, 2)
    nivell_op = JERARQUIA_CARNETS.get(operari.get("carnet_conduir", "B"), 2)

    if nivell_op < nivell_req:
        raise HTTPException(
            status_code=403,
            detail=f"Permís insuficient: es requereix carnet {carnet_req}",
        )

    requereix_cap = req.get("requereix_cap", vehicle.get("requereix_cap", False))
    te_cap = operari.get("te_cap_vigent", operari.get("te_cap", False))
    if requereix_cap and not te_cap:
        raise HTTPException(
            status_code=403,
            detail="Es requereix certificat CAP en vigor per a vehicles >3.500 kg",
        )

    prl_op = set(operari.get("certificats_prl", []))
    if "OPERADOR_GRUA_CAMIO" in prl_op or "PRL_OPERADOR_GRUA" in prl_op:
        prl_op.add("OPERADOR_GRUA_CAMIO")
        prl_op.add("PRL_OPERADOR_GRUA")

    certificats_req = req.get("certificats_prl_requerits", vehicle.get("certificats_prl_requerits", []))
    for prl in certificats_req:
        if prl not in prl_op:
            raise HTTPException(
                status_code=403,
                detail=f"Falta formació PRL obligatòria: {prl}",
            )

    return True


router = APIRouter(
    prefix="/operari/vehicles",
    tags=["Operari PWA Vehicles"],
    dependencies=[
        Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"]))
    ],
)


class VehicleResponse(BaseModel):
    id: uuid.UUID
    matricula: str
    marca: str
    model: str
    marca_model: str
    tipus: str = "FURGONETA"
    estat: str
    odometre_acumulat: int | None = None
    apte_assignacio_pwa: bool = True


@router.get("", response_model=List[VehicleResponse])
async def llistar_vehicles_pwa(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(require_roles(["OPERARI", "CAPATAZ", "CAP_DE_COLLA", "BOSS", "SUPERADMIN"])),
):
    empresa_id = request.state.empresa_id
    emp_uuid = uuid.UUID(empresa_id)

    # Identificar vehicle assignat a l'operari autenticat
    user_id_raw = getattr(request.state, "user_id", None) or claims.get("sub")
    user_uuid = None
    vehicle_assignat_id = None
    if user_id_raw:
        try:
            user_uuid = uuid.UUID(str(user_id_raw))
            user_res = await db.execute(
                select(Usuari).where(Usuari.id == user_uuid, Usuari.empresa_id == emp_uuid)
            )
            usuari_actiu = user_res.scalars().first()
            if usuari_actiu:
                vehicle_assignat_id = usuari_actiu.vehicle_assignat_id
        except (ValueError, TypeError):
            pass

    res = await db.execute(select(Vehicle).where(Vehicle.empresa_id == emp_uuid))
    vehicles = list(res.scalars().all())

    # Ordenar prioritzant el vehicle habitual de l'operari a l'índex 0
    if user_uuid or vehicle_assignat_id:
        vehicles.sort(
            key=lambda v: 0
            if (vehicle_assignat_id and v.id == vehicle_assignat_id)
            or (user_uuid and v.conductor_habitual_id == user_uuid)
            else 1
        )

    return [
        VehicleResponse(
            id=v.id,
            matricula=v.matricula,
            marca=v.marca,
            model=v.model,
            marca_model=f"{v.marca} {v.model}".strip(),
            tipus=getattr(v, "tipus", "FURGONETA") or "FURGONETA",
            estat=v.estat,
            odometre_acumulat=v.odometre_acumulat,
            apte_assignacio_pwa=bool(getattr(v, "apte_assignacio_pwa", True)),
        )
        for v in vehicles
    ]


class ItemEstocFurgonetaResponse(BaseModel):
    id: uuid.UUID
    nom: str
    referencia: str
    marca: str
    quantitat_actual: float
    quantitat_optima: float
    unitat: str


@router.get("/stock", response_model=List[ItemEstocFurgonetaResponse])
async def llistar_estoc_furgonetes(
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    """Retorna l'estoc físic d'articles ubicats als vehicles/furgoneta de la colla."""
    empresa_id = request.state.empresa_id
    if not empresa_id or empresa_id == "undefined":
        raise HTTPException(status_code=401, detail="Context d'empresa no trobat")

    stmt = (
        select(EstocMagatzem, Article)
        .join(Article, EstocMagatzem.article_id == Article.id)
        .join(Magatzem, EstocMagatzem.magatzem_id == Magatzem.id)
        .where(
            EstocMagatzem.empresa_id == uuid.UUID(empresa_id),
            Magatzem.tipus == "FURGONETA",
        )
    )
    res = await db.execute(stmt)
    items = []
    for estoc, art in res.all():
        items.append(
            ItemEstocFurgonetaResponse(
                id=estoc.id,
                nom=art.nom,
                referencia=art.referencia_inventari,
                marca=getattr(art, "familia", "") or "",
                quantitat_actual=float(estoc.quantitat_fisica or 0.0),
                quantitat_optima=float(getattr(art, "estoc_optim", 0.0) or 0.0),
                unitat=getattr(art, "unitat_mesura", "UNITAT") or "UNITAT",
            )
        )
    return items


class ReportDanyRequest(BaseModel):
    descripcio: str
    gravetat: str


@router.post("/{vehicle_id}/danys")
async def reportar_dany_vehicle(
    vehicle_id: uuid.UUID,
    payload: ReportDanyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id

    nova_incidencia = Incidencia(
        empresa_id=uuid.UUID(empresa_id),
        vehicle_id=vehicle_id,
        text_observacions=payload.descripcio,
        estat="VERMELL",
        ambit="VEHICLE",
    )
    db.add(nova_incidencia)
    await db.flush()
    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=empresa_id,
        categoria="incidencies_registres",
        item_id=str(nova_incidencia.id),
        dades={
            "id": str(nova_incidencia.id),
            "vehicle_id": str(vehicle_id),
            "ambit": "VEHICLE",
            "estat": "VERMELL",
            "gravetat": payload.gravetat,
            "text_observacions": payload.descripcio,
        },
    )
    await db.commit()

    return {"status": "OK", "incidencia_id": str(nova_incidencia.id)}


class CheckinVehicleRequest(BaseModel):
    odometre_inicial: int
    foto_odometre_id: str | None = None
    nivell_combustible: str | None = None


@router.post("/{vehicle_id}/checkin", status_code=status.HTTP_201_CREATED)
async def vehicle_checkin(
    vehicle_id: uuid.UUID,
    payload: CheckinVehicleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    emp_uuid = uuid.UUID(empresa_id)
    vehicle = (
        (
            await db.execute(
                select(Vehicle).where(
                    Vehicle.id == vehicle_id, Vehicle.empresa_id == emp_uuid
                )
            )
        )
        .scalars()
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404)

    if not getattr(vehicle, "apte_assignacio_pwa", True):
        raise HTTPException(
            status_code=422,
            detail=f"Bloqueig operatiu: El vehicle {vehicle.matricula} no és apte (ITV o assegurança caducada).",
        )

    vehicle.odometre_acumulat = payload.odometre_inicial
    await sincronitzar_vehicle_al_disc_empresa(
        db,
        emp_uuid,
        vehicle,
        {
            "ultim_checkin_odometre": payload.odometre_inicial,
            "nivell_combustible": payload.nivell_combustible,
        },
    )
    await db.commit()

    return {"estat": "CHECKIN_OK", "odometre": vehicle.odometre_acumulat}


class RepostatgeRequest(BaseModel):
    litres: float
    euros: float
    odometre: int


@router.post("/{vehicle_id}/repostatge", status_code=status.HTTP_201_CREATED)
async def vehicle_repostatge(
    vehicle_id: uuid.UUID,
    payload: RepostatgeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    emp_uuid = uuid.UUID(empresa_id)
    usuari_id = getattr(request.state, "user_id", None)  # Assuming user_id is in state
    if not usuari_id:
        # Fallback if state doesn't have it (for mock/tests)
        first_user = (
            (await db.execute(select(Usuari).where(Usuari.empresa_id == emp_uuid)))
            .scalars()
            .first()
        )
        usuari_id = first_user.id if first_user else uuid.uuid4()

    vehicle = (
        (
            await db.execute(
                select(Vehicle).where(
                    Vehicle.id == vehicle_id, Vehicle.empresa_id == emp_uuid
                )
            )
        )
        .scalars()
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404)

    tiquet = TiquetCarburant(
        empresa_id=emp_uuid,
        vehicle_id=vehicle_id,
        operari_id=uuid.UUID(str(usuari_id)),
        tiquet_foto_path="n/a",
        odometre_foto_path="n/a",
        litres=payload.litres,
        import_=payload.euros,
        odometre_valor=payload.odometre,
    )
    db.add(tiquet)
    await db.flush()

    await SovereignStorageGateway.desar_entitat_json(
        db=db,
        empresa_id=emp_uuid,
        categoria="tiquets_despesa",
        item_id=str(tiquet.id),
        dades={
            "id": str(tiquet.id),
            "operari_id": str(tiquet.operari_id),
            "vehicle_id": str(vehicle_id),
            "matricula": vehicle.matricula,
            "litres": float(payload.litres),
            "import_euros": float(payload.euros),
            "odometre_valor": int(payload.odometre),
        },
    )
    await sincronitzar_vehicle_al_disc_empresa(db, emp_uuid, vehicle)
    await db.commit()

    return {"estat": "REPOSTATGE_OK", "consum_litres": payload.litres, "tiquet_id": str(tiquet.id)}


class CheckoutVehicleRequest(BaseModel):
    odometre_final: int
    foto_odometre_id: str | None = None
    nivell_combustible: str | None = None


@router.post("/{vehicle_id}/checkout", status_code=status.HTTP_200_OK)
async def vehicle_checkout(
    vehicle_id: uuid.UUID,
    payload: CheckoutVehicleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_with_tenant_context),
):
    empresa_id = request.state.empresa_id
    emp_uuid = uuid.UUID(empresa_id)
    vehicle = (
        (
            await db.execute(
                select(Vehicle).where(
                    Vehicle.id == vehicle_id, Vehicle.empresa_id == emp_uuid
                )
            )
        )
        .scalars()
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404)

    km_recorreguts = payload.odometre_final - (vehicle.odometre_acumulat or 0)

    vehicle.odometre_acumulat = payload.odometre_final
    await sincronitzar_vehicle_al_disc_empresa(
        db,
        emp_uuid,
        vehicle,
        {
            "ultim_checkout_odometre": payload.odometre_final,
            "ultim_km_recorreguts": km_recorreguts,
        },
    )
    await db.commit()

    return {"estat": "CHECKOUT_OK", "km_recorreguts": km_recorreguts}
