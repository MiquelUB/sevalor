import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import HistorialAssignacioVehicle, Usuari, Vehicle
from app.services.sovereign_storage import SovereignStorageGateway

# Jerarquia de permisos de conduir segons la DGT i normativa EARS (FR-012 / T028)
JERARQUIA_CARNETS: dict[str, set[str]] = {
    "AM": {"AM", "B", "B+E", "C", "C+E"},
    "B": {"B", "B+E", "C", "C+E"},
    "B+E": {"B+E", "C+E"},
    "C": {"C", "C+E"},
    "C+E": {"C+E"},
    "N/A": {"AM", "B", "B+E", "C", "C+E", "N/A"},
}


async def sincronitzar_vehicle_al_disc_empresa(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    vehicle: Vehicle,
    dades_extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Persisteix la fitxa actualitzada del vehicle al disc dur dedicat de l'empresa (08_flota_i_operaris/vehicles)."""
    payload: Dict[str, Any] = {
        "id": str(vehicle.id),
        "empresa_id": str(empresa_id),
        "matricula": vehicle.matricula,
        "marca": vehicle.marca,
        "model": vehicle.model,
        "tipus": getattr(vehicle, "tipus", "DIESEL"),
        "distintiu_ambiental": getattr(vehicle, "distintiu_ambiental", "C"),
        "estat": "OPERATIU" if vehicle.estat == "ASSIGNAT" else vehicle.estat,
        "odometre_acumulat": int(vehicle.odometre_acumulat or 0),
        "odometre_inici_contracte": int(getattr(vehicle, "odometre_inici_contracte", 0) or 0),
        "regim_adquisicio": getattr(vehicle, "regim_adquisicio", "PROPIETAT"),
        "renting_limit_km": getattr(vehicle, "renting_limit_km", None),
        "data_inici_contracte": (
            vehicle.data_inici_contracte.isoformat()
            if vehicle.data_inici_contracte is not None
            else None
        ),
        "data_fi_contracte": (
            vehicle.data_fi_contracte.isoformat()
            if vehicle.data_fi_contracte is not None
            else None
        ),
        "quota_mensual_eur": float(getattr(vehicle, "quota_mensual_eur", 0.0) or 0.0),
        "tarifa_diaria_eur": float(getattr(vehicle, "tarifa_diaria_eur", 0.0) or 0.0),
        "preu_km_exces_eur": float(getattr(vehicle, "preu_km_exces_eur", 0.0) or 0.0),
        "valor_residual_eur": (
            float(vehicle.valor_residual_eur)
            if vehicle.valor_residual_eur is not None
            else None
        ),
        "fianca_eur": (
            float(vehicle.fianca_eur)
            if vehicle.fianca_eur is not None
            else None
        ),
        "conductor_habitual_id": (
            str(vehicle.conductor_habitual_id) if vehicle.conductor_habitual_id else None
        ),
        "carnet_necessari": getattr(vehicle, "carnet_necessari", "B"),
        "estat_itv": getattr(vehicle, "estat_itv", None),
        "data_proxima_itv": (
            vehicle.data_proxima_itv.isoformat()
            if vehicle.data_proxima_itv is not None
            else None
        ),
        "companyia_asseguradora": getattr(vehicle, "companyia_asseguradora", None),
        "polissa_asseguranca": getattr(vehicle, "polissa_asseguranca", None),
        "data_caducitat_asseguranca": (
            vehicle.data_caducitat_asseguranca.isoformat()
            if vehicle.data_caducitat_asseguranca is not None
            else None
        ),
    }
    if dades_extra:
        payload.update(dades_extra)

    try:
        return await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="vehicles",
            item_id=str(vehicle.id),
            dades=payload,
        )
    except Exception:
        return None


async def sincronitzar_operari_al_disc_empresa(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    operari: Usuari,
    dades_extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Persisteix la fitxa actualitzada de l'operari al disc dur dedicat de l'empresa (08_flota_i_operaris/vehicles)."""
    payload: Dict[str, Any] = {
        "id": str(operari.id),
        "empresa_id": str(empresa_id),
        "nif": operari.nif,
        "nom": operari.nom,
        "cognoms": operari.cognoms or "",
        "email": operari.email,
        "telefon": operari.telefon,
        "rol": operari.rol,
        "especialitat": getattr(operari, "especialitat", None),
        "estat": operari.estat,
        "estat_operatiu": getattr(operari, "estat_operatiu", "DISPONIBLE"),
        "cost_hora_eur": float(getattr(operari, "cost_hora_eur", 22.50) or 22.50),
        "carnet_conduir": getattr(operari, "carnet_conduir", "B") or "B",
        "carnet_caducitat": (
            operari.carnet_caducitat.isoformat()
            if operari.carnet_caducitat is not None
            else None
        ),
        "prl_certificat_vigencia": (
            operari.prl_certificat_vigencia.isoformat()
            if operari.prl_certificat_vigencia is not None
            else None
        ),
        "vehicle_assignat_id": (
            str(operari.vehicle_assignat_id) if operari.vehicle_assignat_id else None
        ),
    }
    if dades_extra:
        payload.update(dades_extra)

    try:
        return await SovereignStorageGateway.desar_entitat_json(
            db=db,
            empresa_id=empresa_id,
            categoria="vehicles",
            item_id=f"operari_{operari.id}",
            dades=payload,
        )
    except Exception:
        return None


def validar_permis_conduir(vehicle: Vehicle, operari: Usuari) -> None:
    """Valida la guarda de seguretat de permís de conduir (FR-012 / T028).

    - Comprova que l'operari tingui la categoria de carnet exigida pel vehicle o superior.
    - Comprova que el carnet no estigui caducat en la data actual.
    """
    avui = date.today()
    carnet_req = (vehicle.carnet_necessari or "B").upper().strip()
    carnet_op = (operari.carnet_conduir or "B").upper().strip()
    permisos_valids = JERARQUIA_CARNETS.get(carnet_req, {carnet_req})

    if carnet_op not in permisos_valids:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Bloqueig de seguretat (FR-012 / T028): El vehicle {vehicle.matricula} requereix "
                f"permís '{carnet_req}', però l'operari {operari.nom} només disposa de '{carnet_op}'."
            ),
        )

    if operari.carnet_caducitat and operari.carnet_caducitat < avui:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Bloqueig de seguretat (FR-012 / T028): El carnet de conduir de {operari.nom} "
                f"ha caducat el {operari.carnet_caducitat.isoformat()}."
            ),
        )


async def sincronitzar_assignacio_vehicle_operari(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    vehicle: Vehicle,
    nou_conductor_id: Optional[uuid.UUID],
    autor_id: Optional[uuid.UUID] = None,
    motiu: str = "Assignació de conductor habitual",
    odometre: Optional[int] = None,
) -> None:
    """Sincronitza bidireccionalment Vehicle.conductor_habitual_id i Usuari.vehicle_assignat_id

    garantint relació 1:1 estricta, tancament d'historials previs i guarda de carnet (FR-012 / T028).
    """
    ara = datetime.now(timezone.utc)
    odo_actual = odometre if odometre is not None else vehicle.odometre_acumulat

    # 1. Desvinculació (nou_conductor_id is None)
    if nou_conductor_id is None:
        operaris_afectats: list[Usuari] = []
        if vehicle.conductor_habitual_id:
            u_prev = (
                await db.execute(
                    select(Usuari).where(
                        Usuari.id == vehicle.conductor_habitual_id,
                        Usuari.empresa_id == empresa_id,
                    )
                )
            ).scalars().first()
            if u_prev:
                if u_prev.vehicle_assignat_id == vehicle.id:
                    u_prev.vehicle_assignat_id = None
                operaris_afectats.append(u_prev)

        # Desvincular qualsevol altre operari que apuntés a aquest vehicle
        usuaris_vinculats = (
            await db.execute(
                select(Usuari).where(
                    Usuari.vehicle_assignat_id == vehicle.id,
                    Usuari.empresa_id == empresa_id,
                )
            )
        ).scalars().all()
        for u_vinc in usuaris_vinculats:
            u_vinc.vehicle_assignat_id = None
            if u_vinc not in operaris_afectats:
                operaris_afectats.append(u_vinc)

        # Tancar registres d'historial oberts d'aquest vehicle
        hist_oberts = (
            await db.execute(
                select(HistorialAssignacioVehicle).where(
                    HistorialAssignacioVehicle.vehicle_id == vehicle.id,
                    HistorialAssignacioVehicle.empresa_id == empresa_id,
                    HistorialAssignacioVehicle.data_fi.is_(None),
                )
            )
        ).scalars().all()
        for h in hist_oberts:
            h.data_fi = ara
            h.odometre_fi = odo_actual

        vehicle.conductor_habitual_id = None
        if vehicle.estat == "ASSIGNAT":
            vehicle.estat = "OPERATIU"

        await sincronitzar_vehicle_al_disc_empresa(db, empresa_id, vehicle, {"conductor_nom": None})
        for op_af in operaris_afectats:
            await sincronitzar_operari_al_disc_empresa(
                db, empresa_id, op_af, {"vehicle_habitual": None}
            )
        return

    # 2. Assignació a un nou conductor: Cercar operari
    operari = (
        await db.execute(
            select(Usuari).where(
                Usuari.id == nou_conductor_id,
                Usuari.empresa_id == empresa_id,
            )
        )
    ).scalars().first()
    if not operari:
        raise HTTPException(status_code=404, detail="Operari no trobat")

    # 3. Guarda de Carnet i Caducitat (FR-012 / T028)
    validar_permis_conduir(vehicle, operari)

    # 4. Si ja està assignat exactament a aquest mateix operari, assegurar estat i no duplicar
    if vehicle.conductor_habitual_id == operari.id and operari.vehicle_assignat_id == vehicle.id:
        if vehicle.estat == "ASSIGNAT":
            vehicle.estat = "OPERATIU"
        c_nom = f"{operari.nom or ''} {operari.cognoms or ''}".strip() or None
        await sincronitzar_vehicle_al_disc_empresa(
            db, empresa_id, vehicle, {"conductor_nom": c_nom}
        )
        await sincronitzar_operari_al_disc_empresa(
            db,
            empresa_id,
            operari,
            {
                "vehicle_habitual": {
                    "id": str(vehicle.id),
                    "matricula": vehicle.matricula,
                    "model": f"{vehicle.marca} {vehicle.model}".strip(),
                }
            },
        )
        return

    # 5. Alliberar antic conductor del vehicle
    antic_cond = None
    if vehicle.conductor_habitual_id and vehicle.conductor_habitual_id != operari.id:
        antic_cond = (
            await db.execute(
                select(Usuari).where(
                    Usuari.id == vehicle.conductor_habitual_id,
                    Usuari.empresa_id == empresa_id,
                )
            )
        ).scalars().first()
        if antic_cond and antic_cond.vehicle_assignat_id == vehicle.id:
            antic_cond.vehicle_assignat_id = None

        hist_v_oberts = (
            await db.execute(
                select(HistorialAssignacioVehicle).where(
                    HistorialAssignacioVehicle.vehicle_id == vehicle.id,
                    HistorialAssignacioVehicle.empresa_id == empresa_id,
                    HistorialAssignacioVehicle.data_fi.is_(None),
                )
            )
        ).scalars().all()
        for h in hist_v_oberts:
            h.data_fi = ara
            h.odometre_fi = odo_actual

    # 6. Alliberar qualsevol antic vehicle de l'operari (per vehicle_assignat_id o conductor_habitual_id)
    condicions_veh_prev = [Vehicle.conductor_habitual_id == operari.id]
    if operari.vehicle_assignat_id:
        condicions_veh_prev.append(Vehicle.id == operari.vehicle_assignat_id)

    antics_vehicles = (
        await db.execute(
            select(Vehicle).where(
                Vehicle.empresa_id == empresa_id,
                Vehicle.id != vehicle.id,
                or_(*condicions_veh_prev),
            )
        )
    ).scalars().all()

    if antics_vehicles:
        for antic_veh in antics_vehicles:
            if antic_veh.conductor_habitual_id == operari.id:
                antic_veh.conductor_habitual_id = None
            if antic_veh.estat == "ASSIGNAT":
                antic_veh.estat = "OPERATIU"

        hist_u_oberts = (
            await db.execute(
                select(HistorialAssignacioVehicle).where(
                    HistorialAssignacioVehicle.conductor_id == operari.id,
                    HistorialAssignacioVehicle.empresa_id == empresa_id,
                    HistorialAssignacioVehicle.data_fi.is_(None),
                )
            )
        ).scalars().all()
        for h in hist_u_oberts:
            h.data_fi = ara
            h.odometre_fi = odo_actual

    # 7. Vincular atòmicament 1:1
    vehicle.conductor_habitual_id = operari.id
    operari.vehicle_assignat_id = vehicle.id
    if vehicle.estat == "ASSIGNAT":
        vehicle.estat = "OPERATIU"

    # 8. Registrar nou moviment a l'historial
    db.add(
        HistorialAssignacioVehicle(
            empresa_id=empresa_id,
            vehicle_id=vehicle.id,
            conductor_id=operari.id,
            data_inici=ara,
            odometre_inici=odo_actual,
            motiu=motiu,
            creat_per_id=autor_id,
        )
    )

    # 9. Persistir fitxes actualitzades al disc dur de l'empresa
    if antic_cond:
        await sincronitzar_operari_al_disc_empresa(
            db, empresa_id, antic_cond, {"vehicle_habitual": None}
        )
    for antic_veh in antics_vehicles:
        await sincronitzar_vehicle_al_disc_empresa(
            db, empresa_id, antic_veh, {"conductor_nom": None}
        )
    c_nom = f"{operari.nom or ''} {operari.cognoms or ''}".strip() or None
    await sincronitzar_vehicle_al_disc_empresa(db, empresa_id, vehicle, {"conductor_nom": c_nom})
    await sincronitzar_operari_al_disc_empresa(
        db,
        empresa_id,
        operari,
        {
            "vehicle_habitual": {
                "id": str(vehicle.id),
                "matricula": vehicle.matricula,
                "model": f"{vehicle.marca} {vehicle.model}".strip(),
            }
        },
    )


async def sincronitzar_assignacio_des_de_operari(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    operari: Usuari,
    nou_vehicle_id: Optional[uuid.UUID],
    autor_id: Optional[uuid.UUID] = None,
    motiu: str = "Assignació des de fitxa operari",
    odometre: Optional[int] = None,
) -> None:
    """Sincronitza l'assignació iniciada des del perfil de l'operari."""
    if nou_vehicle_id is None:
        condicions_desvincular = [Vehicle.conductor_habitual_id == operari.id]
        if operari.vehicle_assignat_id:
            condicions_desvincular.append(Vehicle.id == operari.vehicle_assignat_id)

        vehicles_antics = (
            await db.execute(
                select(Vehicle).where(
                    Vehicle.empresa_id == empresa_id,
                    or_(*condicions_desvincular),
                )
            )
        ).scalars().all()
        for v_antic in vehicles_antics:
            await sincronitzar_assignacio_vehicle_operari(
                db, empresa_id, v_antic, None, autor_id=autor_id, motiu=motiu, odometre=odometre
            )
        operari.vehicle_assignat_id = None
        await sincronitzar_operari_al_disc_empresa(
            db, empresa_id, operari, {"vehicle_habitual": None}
        )
        return

    # Obtenir vehicle i validar
    vehicle = (
        await db.execute(
            select(Vehicle).where(
                Vehicle.id == nou_vehicle_id,
                Vehicle.empresa_id == empresa_id,
            )
        )
    ).scalars().first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle no trobat")

    await sincronitzar_assignacio_vehicle_operari(
        db, empresa_id, vehicle, operari.id, autor_id=autor_id, motiu=motiu, odometre=odometre
    )
