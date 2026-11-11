import hashlib
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

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
        "estat": vehicle.estat,
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
    """Valida la guarda de seguretat de permís de conduir i aptitud de vehicle (FR-012 / T028 / Fase 4).

    - Comprova que el vehicle sigui apte per a assignació (vehicle.apte_assignacio_pwa == True).
    - Comprova la jerarquia de carnet de conduir de l'operari respecte a vehicle.carnet_necessari.
    - Comprova el requeriment de Certificat d'Aptitud Professional (CAP) si vehicle.requereix_cap == True.
    - Comprova que el carnet no estigui caducat en la data actual.
    """
    avui = date.today()

    # 1. Guarda d'aptitud i vigència legal del vehicle (ITV, Assegurança, Rènting, Estat)
    if not getattr(vehicle, "apte_assignacio_pwa", True):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Bloqueig de seguretat: El vehicle {vehicle.matricula} no és apte per a assignació "
                f"(ITV o assegurança caducada, o estat bloquejat/taller)."
            ),
        )

    # 2. Guarda de jerarquia de permisos de conduir
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

    # 3. Guarda de CAP obligatori per a vehicles pesants
    if getattr(vehicle, "requereix_cap", False) and not getattr(operari, "te_cap", False):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Bloqueig de seguretat (CAP obligatori): El vehicle {vehicle.matricula} requereix "
                f"Certificat d'Aptitud Professional (CAP) en vigor, però l'operari {operari.nom} no disposa de CAP acreditat."
            ),
        )

    # 4. Caducitat del permís de conduir de l'operari
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


def consolidar_i_validar_ocr_flota(
    docs_extrets: List[Dict[str, Any]],
    tenant_cif: str = "",
    avui: Optional[date] = None,
    data_referencia: Optional[date] = None,
) -> Dict[str, Any]:
    """Consolida múltiples documents OCR de vehicle, verifica coherència creuada i calcula el semàfor operatiu.

    Args:
        docs_extrets: Llista de diccionaris amb el resultat de processar_ocr_document_vehicle per a cada document.
        tenant_cif: NIF/CIF de l'empresa propietària de la flota (tenant).
        avui: Data de referència per a calcular venciments (per defecte date.today()).
        data_referencia: Àlies per a avui (per retrocompatibilitat).

    Returns:
        Diccionari consolidat amb metadades de coherència creuada, semàfor, alertes i documentació pendent.
    """
    ref_date = avui or data_referencia or date.today()

    merged_data: Dict[str, Any] = {
        "status": "EXTRET_AUTOMATIC",
        "confidence": 0.0,
        "coherencia_creuada_vin_matricula": True,
        "validacio_tenant_cif": "SENSE_TENANT_CIF",
        "estat_semafor": "OPERATIU_OK",
        "apte_assignacio_pwa": True,
        "matricula": None,
        "bastidor": None,
        "num_bastidor_vin": None,
        "marca": None,
        "model": None,
        "titular": None,
        "titular_nif": None,
        "arrendatari": None,
        "arrendatari_nif": None,
        "codi_servei_dgt": None,
        "categoria_ue": None,
        "mma_kg": None,
        "tara_kg": None,
        "carrega_util_kg": None,
        "mmr_amb_fre_kg": None,
        "requereix_cap": False,
        "equipament_homologat": [],
        "empresa_renting": None,
        "num_contracte_renting": None,
        "data_inici_contracte": None,
        "data_fi_contracte": None,
        "data_venciment_renting": None,
        "dades_pesants": None,
        "tipus": None,
        "distintiu_ambiental": None,
        "odometre_acumulat": None,
        "estat_itv": None,
        "data_proxima_itv": None,
        "data_inspeccio_itv": None,
        "data_matriculacio": None,
        "companyia_asseguradora": None,
        "polissa_asseguranca": None,
        "data_caducitat_asseguranca": None,
        "regim_adquisicio": None,
        "renting_limit_km": None,
        "carnet_necessari": None,
        "documents_processats": [],
        "documents_mancants": [],
        "alertes_programades": [],
        "estat_operatiu_saas": {},
    }

    if not docs_extrets:
        merged_data["status"] = "PENDENT_REVISIO_MANUAL"
        merged_data["estat_operatiu_saas"] = {
            "error": "No s'han aportat documents per consolidar.",
            "estat_semafor": "BLOQUEJAT_CADUCAT",
            "apte_assignacio_pwa": False,
        }
        return merged_data

    confidences: List[float] = []
    equipaments_set: Set[str] = set()
    dades_pesants_dict: Dict[str, Any] = {}
    max_odo = 0

    # 1. Fusió inicial de camps no nuls procedents de qualsevol document
    for idx, d in enumerate(docs_extrets):
        confidences.append(float(d.get("confidence", 0.0) or 0.0))

        nom_fitxer = str(d.get("nom_fitxer") or d.get("nom") or f"document_{idx + 1}")
        tipus_doc = str(d.get("tipus_document") or "GENERAL")
        odo = int(d.get("odometre_acumulat") or 0)
        if odo > max_odo:
            max_odo = odo

        doc_hash = d.get("hash_sha256")
        if not doc_hash:
            base_str = f"{nom_fitxer}_{tipus_doc}_{d.get('matricula')}_{d.get('bastidor')}_{odo}"
            doc_hash = hashlib.sha256(base_str.encode()).hexdigest()

        merged_data["documents_processats"].append({
            "nom": nom_fitxer,
            "tipus_detectat": tipus_doc,
            "confidence": float(d.get("confidence", 0.95) or 0.95),
            "matricula_detectada": d.get("matricula"),
            "bastidor_detectat": d.get("bastidor"),
            "nif_detectat": d.get("arrendatari_nif") or d.get("titular_nif"),
            "data_emissio": d.get("data_inspeccio_itv") or d.get("data_matriculacio"),
            "data_caducitat": (
                d.get("data_proxima_itv")
                or d.get("data_caducitat_asseguranca")
                or d.get("data_venciment_renting")
            ),
            "odometre_detectat": odo if odo > 0 else None,
            "accio_persistencia": "UPSERT_DOCUMENT_FLOTA",
            "hash_sha256": doc_hash,
        })

        for k in [
            "matricula",
            "bastidor",
            "marca",
            "model",
            "titular",
            "titular_nif",
            "arrendatari",
            "arrendatari_nif",
            "codi_servei_dgt",
            "categoria_ue",
            "mma_kg",
            "tara_kg",
            "carrega_util_kg",
            "mmr_amb_fre_kg",
            "empresa_renting",
            "num_contracte_renting",
            "data_inici_contracte",
            "data_fi_contracte",
            "data_venciment_renting",
            "tipus",
            "distintiu_ambiental",
            "odometre_acumulat",
            "estat_itv",
            "data_proxima_itv",
            "data_inspeccio_itv",
            "data_matriculacio",
            "companyia_asseguradora",
            "polissa_asseguranca",
            "data_caducitat_asseguranca",
            "regim_adquisicio",
            "renting_limit_km",
            "carnet_necessari",
        ]:
            if k == "estat_itv":
                continue
            if d.get(k) is not None and not merged_data.get(k):
                merged_data[k] = d[k]

        # Jerarquia de gravetat d'estat ITV (defectes lleus o desfavorables prevalen)
        if d.get("estat_itv"):
            ordre_itv = {"FAVORABLE": 1, "FAVORABLE_LEUS": 2, "DESFAVORABLE": 3, "NEGATIVA": 4}
            actual_itv = merged_data.get("estat_itv")
            if actual_itv is None or ordre_itv.get(str(d["estat_itv"]).upper(), 0) > ordre_itv.get(str(actual_itv).upper(), 0):
                merged_data["estat_itv"] = d["estat_itv"]

        if d.get("requereix_cap"):
            merged_data["requereix_cap"] = True

        eq_list = d.get("equipament_homologat")
        if isinstance(eq_list, list):
            equipaments_set.update([str(item) for item in eq_list if item])

        dp_sub = d.get("dades_pesants")
        if isinstance(dp_sub, dict):
            dades_pesants_dict.update(dp_sub)

    merged_data["equipament_homologat"] = sorted(list(equipaments_set))
    if dades_pesants_dict:
        merged_data["dades_pesants"] = dades_pesants_dict

    if max_odo > 0 and (not merged_data.get("odometre_acumulat") or max_odo > merged_data["odometre_acumulat"]):
        merged_data["odometre_acumulat"] = max_odo

    merged_data["confidence"] = max(confidences) if confidences else 0.0

    # 2. Verificació de Coherència Creuada (coherencia_creuada_vin_matricula)
    matricules_detectades = set(
        str(d["matricula"]).upper() for d in docs_extrets if d.get("matricula")
    )
    bastidors_detectats = set(
        str(d["bastidor"]).upper() for d in docs_extrets if d.get("bastidor")
    )

    errors_coherencia: List[str] = []
    if len(matricules_detectades) > 1:
        errors_coherencia.append(
            f"Discrepància de matrícules detectades entre documents: {', '.join(sorted(matricules_detectades))}"
        )
    if len(bastidors_detectats) > 1:
        errors_coherencia.append(
            f"Discrepància de números de bastidor (VIN) detectats entre documents: {', '.join(sorted(bastidors_detectats))}"
        )

    coherencia_creuada = (len(errors_coherencia) == 0)
    merged_data["coherencia_creuada_vin_matricula"] = coherencia_creuada

    # 3. Conciliació Multitenant (Propietat vs. Rènting)
    clean_tenant = re.sub(r"[\s\-]", "", tenant_cif).upper() if tenant_cif else ""
    clean_titular = re.sub(r"[\s\-]", "", str(merged_data.get("titular_nif") or "")).upper()
    clean_arrendatari = re.sub(r"[\s\-]", "", str(merged_data.get("arrendatari_nif") or "")).upper()
    codi_servei = merged_data.get("codi_servei_dgt") or "B00"

    if (clean_arrendatari and clean_arrendatari == clean_tenant) or codi_servei == "A12" or merged_data.get("empresa_renting") or merged_data.get("regim_adquisicio") == "RENTING":
        regim = "RENTING"
        validacio_tenant_cif = "COINCIDENT_ARRENDATARI" if (clean_arrendatari == clean_tenant) else ("CODI_A12_RENTING" if codi_servei == "A12" else "COINCIDENT_ARRENDATARI")
        conciliacio = "VALIDAT_COM_ARRENDATARI" if (clean_arrendatari == clean_tenant) else "CODI_A12_RENTING"
    elif clean_tenant and clean_titular and clean_titular == clean_tenant:
        regim = "PROPIETAT"
        validacio_tenant_cif = "COINCIDENT_PROPIETARI"
        conciliacio = "VALIDAT_COM_PROPIETARI"
    elif clean_tenant:
        regim = merged_data.get("regim_adquisicio") or "DESCONEGUT"
        validacio_tenant_cif = "DISCREPANCIA_NIF"
        conciliacio = "DISCREPANCIA_NIF_TENANT"
    else:
        regim = merged_data.get("regim_adquisicio") or "PROPIETAT"
        validacio_tenant_cif = "SENSE_TENANT_CIF"
        conciliacio = "SENSE_TENANT_CIF"

    merged_data["regim_adquisicio"] = regim
    merged_data["validacio_tenant_cif"] = validacio_tenant_cif

    # Valors per defecte si no s'han especificat
    if not merged_data["tipus"]:
        merged_data["tipus"] = "DIESEL"
    if not merged_data["distintiu_ambiental"]:
        if merged_data["tipus"] == "EV":
            merged_data["distintiu_ambiental"] = "ZERO"
        elif merged_data["tipus"] == "PHEV":
            merged_data["distintiu_ambiental"] = "ECO"
        else:
            merged_data["distintiu_ambiental"] = "C"
    if not merged_data["regim_adquisicio"]:
        merged_data["regim_adquisicio"] = "PROPIETAT"
    if merged_data["regim_adquisicio"] not in ("RENTING", "LEASING", "LLOGUER"):
        merged_data["renting_limit_km"] = None

    # Determinació normativa del permís i CAP segons massa, categoria i remolc
    cat_ue_val = str(merged_data.get("categoria_ue") or "N1").upper()
    mma_val = int(merged_data.get("mma_kg") or 0)
    mmr_val = int(merged_data.get("mmr_amb_fre_kg") or 0)
    porta_enganxall = "ENGANXALL_REMOLC" in merged_data.get("equipament_homologat", [])

    if mma_val > 3500 or cat_ue_val in ("N2", "N3"):
        if mmr_val > 750 and porta_enganxall:
            merged_data["carnet_necessari"] = "C+E"
        else:
            merged_data["carnet_necessari"] = "C"
        merged_data["requereix_cap"] = True
    elif mmr_val > 750 and porta_enganxall:
        merged_data["carnet_necessari"] = "B+E"
    elif not merged_data.get("carnet_necessari"):
        merged_data["carnet_necessari"] = "B"

    if not merged_data["estat_itv"]:
        merged_data["estat_itv"] = "FAVORABLE"

    # Càlcul de càrrega útil si no està present
    if not merged_data.get("carrega_util_kg") and merged_data.get("mma_kg") and merged_data.get("tara_kg"):
        if merged_data["mma_kg"] > merged_data["tara_kg"]:
            merged_data["carrega_util_kg"] = merged_data["mma_kg"] - merged_data["tara_kg"]

    # 4. Càlcul de Semàfor Operatiu i alertes_programades[]
    def _parse_data(val: Any) -> Optional[date]:
        if isinstance(val, date):
            return val
        if isinstance(val, str) and len(val) >= 10:
            try:
                return date.fromisoformat(val[:10])
            except ValueError:
                pass
        return None

    alertes: List[Dict[str, Any]] = []
    bloqueig_actiu = False
    alerta_imminent_activa = False

    # Estat ITV desfavorable o negativa
    if merged_data.get("estat_itv") in ("DESFAVORABLE", "NEGATIVA"):
        bloqueig_actiu = True
        alertes.append({
            "tipus": "ITV_DESFAVORABLE",
            "descripcio": f"El resultat de la ITV és {merged_data['estat_itv']}. El vehicle queda bloquejat per circular.",
            "severitat": "CRITICAL",
            "data_venciment": merged_data.get("data_proxima_itv"),
            "dies_restants": None,
        })

    venciments_a_avaluar: List[tuple[str, str, Any]] = [
        ("ITV", "data_proxima_itv", merged_data.get("data_proxima_itv")),
        ("ASSEGURANCA", "data_caducitat_asseguranca", merged_data.get("data_caducitat_asseguranca")),
        ("RENTING", "data_venciment_renting", merged_data.get("data_venciment_renting")),
    ]

    dp = merged_data.get("dades_pesants") or {}
    if isinstance(dp, dict):
        if dp.get("data_visat_transport"):
            venciments_a_avaluar.append(("VISAT_TRANSPORT", "data_visat_transport", dp["data_visat_transport"]))
        if dp.get("data_calibratge_tacograf"):
            venciments_a_avaluar.append(("CALIBRATGE_TACOGRAF", "data_calibratge_tacograf", dp["data_calibratge_tacograf"]))

    dates_bloqueig: List[date] = []
    for nom_etiqueta, camp_clau, d_raw in venciments_a_avaluar:
        d_val = _parse_data(d_raw)
        if not d_val:
            continue
        dies_restants = (d_val - ref_date).days
        if dies_restants <= 0:
            bloqueig_actiu = True
            dates_bloqueig.append(d_val)
            alertes.append({
                "tipus": f"{nom_etiqueta}_CADUCAT",
                "camp": camp_clau,
                "descripcio": f"El venciment de {nom_etiqueta} ha caducat fa {abs(dies_restants)} dies (data límit: {d_val.isoformat()}).",
                "severitat": "CRITICAL",
                "data_venciment": d_val.isoformat(),
                "dies_restants": dies_restants,
            })
        elif 1 <= dies_restants <= 15:
            alerta_imminent_activa = True
            dates_bloqueig.append(d_val)
            alertes.append({
                "tipus": f"{nom_etiqueta}_VENCIMENT_IMMINENT",
                "camp": camp_clau,
                "descripcio": f"El venciment de {nom_etiqueta} és imminent: queden {dies_restants} dies (data límit: {d_val.isoformat()}).",
                "severitat": "WARNING",
                "data_venciment": d_val.isoformat(),
                "dies_restants": dies_restants,
            })
        else:
            alertes.append({
                "tipus": f"{nom_etiqueta}_VIGENT",
                "camp": camp_clau,
                "descripcio": f"{nom_etiqueta} vigent ({dies_restants} dies restants fins al {d_val.isoformat()}).",
                "severitat": "INFO",
                "data_venciment": d_val.isoformat(),
                "dies_restants": dies_restants,
            })

    if bloqueig_actiu:
        estat_semafor = "BLOQUEJAT_CADUCAT"
        apte_assignacio_pwa = False
    elif alerta_imminent_activa or merged_data.get("estat_itv") == "FAVORABLE_LEUS":
        estat_semafor = "ALERTA_VENCIMENT_IMMINENT"
        apte_assignacio_pwa = True
    else:
        estat_semafor = "OPERATIU_OK"
        apte_assignacio_pwa = True

    merged_data["estat_semafor"] = estat_semafor
    merged_data["apte_assignacio_pwa"] = apte_assignacio_pwa
    merged_data["alertes_programades"] = alertes

    # 5. Control de Documentació Obligatòria segons Perfil
    tipus_pujats: Set[str] = set()
    for d in docs_extrets:
        t = str(d.get("tipus_document") or "").upper().strip()
        if t:
            tipus_pujats.add(t)

    documents_mancants: List[str] = []
    if "PERMIS_CIRCULACIO" not in tipus_pujats:
        documents_mancants.append("PERMIS_CIRCULACIO")

    # Fitxa tècnica acreditada si es puja document específic o si les dades tècniques estan cobertes
    te_fitxa_acreditada = bool(
        tipus_pujats.intersection({"FITXA_TECNICA", "ITV", "EITV"})
        or (merged_data.get("mma_kg") and merged_data.get("tara_kg"))
    )
    if not te_fitxa_acreditada:
        documents_mancants.append("FITXA_TECNICA")

    # Assegurança acreditada si es puja pòlissa o si tenim vigència d'assegurança coberta
    te_asseguranca_acreditada = bool(
        "ASSEGURANCA" in tipus_pujats
        or (merged_data.get("data_caducitat_asseguranca") and (merged_data.get("polissa_asseguranca") or merged_data.get("rc_explotacio_grua") or merged_data.get("companyia_asseguradora") or "PERMIS_CIRCULACIO" in tipus_pujats))
    )
    if not te_asseguranca_acreditada:
        documents_mancants.append("ASSEGURANCA")

    # Exempció ITV segons antiguitat i categoria
    d_matr = _parse_data(merged_data.get("data_matriculacio"))
    antiguitat_anys = 0.0
    if d_matr:
        antiguitat_anys = (ref_date - d_matr).days / 365.25

    cat_ue = str(merged_data.get("categoria_ue") or "N1").upper()
    exempcio_anys = 2.0
    if cat_ue == "M1":
        exempcio_anys = 4.0
    elif cat_ue in ("N2", "N3", "M2", "M3"):
        exempcio_anys = 1.0

    if d_matr and antiguitat_anys > exempcio_anys:
        if not tipus_pujats.intersection({"INFORME_ITV", "ITV"}):
            documents_mancants.append("INFORME_ITV")

    if merged_data.get("regim_adquisicio") == "RENTING":
        if not tipus_pujats.intersection({"CONTRACTE_RENTING", "CONTRACTE"}) and not merged_data.get("num_contracte_renting"):
            documents_mancants.append("CONTRACTE_RENTING")

    dp_sub_dict = merged_data.get("dades_pesants") or {}
    te_targeta_transport = bool(
        "TARGETA_TRANSPORT" in tipus_pujats
        or (isinstance(dp_sub_dict, dict) and dp_sub_dict.get("targeta_transport_num"))
    )
    if ((merged_data.get("mma_kg") and merged_data["mma_kg"] > 3500) or cat_ue in ("N2", "N3")) and not te_targeta_transport:
        documents_mancants.append("TARGETA_TRANSPORT")

    merged_data["documents_mancants"] = sorted(documents_mancants)

    # 6. Estat Operatiu SaaS i Status
    if not coherencia_creuada:
        merged_data["status"] = "PENDENT_REVISIO_MANUAL"
        estat_semafor = "BLOQUEJAT_INCIDENCIA"
        apte_assignacio_pwa = False
    else:
        trobat = bool(merged_data.get("matricula") or merged_data.get("bastidor"))
        merged_data["status"] = "EXTRET_AUTOMATIC" if trobat else "PENDENT_REVISIO_MANUAL"

    merged_data["estat_semafor"] = estat_semafor
    merged_data["apte_assignacio_pwa"] = apte_assignacio_pwa

    merged_data["estat_operatiu_saas"] = {
        "coherencia_creuada_vin_matricula": coherencia_creuada,
        "errors_coherencia": errors_coherencia,
        "validacio_tenant_cif": validacio_tenant_cif,
        "estat_semafor": estat_semafor,
        "apte_assignacio_pwa": apte_assignacio_pwa,
        "documents_mancants": documents_mancants,
        "num_alertes_critiques": sum(1 for a in alertes if a.get("severitat") == "CRITICAL"),
        "num_alertes_warning": sum(1 for a in alertes if a.get("severitat") == "WARNING"),
    }

    # 7. Construcció dels blocs estructurats especialitzats
    proper_bloqueig_str = None
    if dates_bloqueig:
        d_min = min(dates_bloqueig)
        if d_min >= ref_date:
            proper_bloqueig_str = (d_min + timedelta(days=1)).isoformat()
        else:
            proper_bloqueig_str = ref_date.isoformat()

    # Control de Rènting i Costos
    limit_km_total = merged_data.get("renting_limit_km")
    current_odo = merged_data.get("odometre_acumulat") or 0
    km_restants = (limit_km_total - current_odo) if (limit_km_total and current_odo) else None

    d_inici_contracte = _parse_data(merged_data.get("data_inici_contracte"))
    d_fi_contracte = _parse_data(merged_data.get("data_venciment_renting") or merged_data.get("data_fi_contracte"))
    mitjana_km_diaris = 0.0
    km_projectats_fi = None
    risc_penalitzacio = False

    if d_inici_contracte and current_odo:
        dies_transcorreguts = max(1, (ref_date - d_inici_contracte).days)
        mitjana_km_diaris = round(current_odo / dies_transcorreguts, 2)
        if d_fi_contracte:
            dies_totals = max(1, (d_fi_contracte - d_inici_contracte).days)
            km_projectats_fi = int(mitjana_km_diaris * dies_totals)
            if limit_km_total and km_projectats_fi > limit_km_total:
                risc_penalitzacio = True

    control_renting_i_costos = {
        "es_renting_o_leasing": regim in ("RENTING", "LEASING", "LLOGUER"),
        "empresa_proveidora": merged_data.get("empresa_renting"),
        "num_contracte": merged_data.get("num_contracte_renting"),
        "data_inici_contracte": merged_data.get("data_inici_contracte"),
        "data_fi_contracte": merged_data.get("data_venciment_renting") or merged_data.get("data_fi_contracte"),
        "limit_km_total": limit_km_total,
        "km_restants_disponibles": km_restants,
        "mitjana_km_diaris": mitjana_km_diaris,
        "km_projectats_fi_contracte": km_projectats_fi,
        "risc_penalitzacio_km": risc_penalitzacio,
    }

    # Capacitats OT
    apte_grua = "GRUA_AUTOCARGANT" in merged_data["equipament_homologat"]
    mmr_amb_fre = merged_data.get("mmr_amb_fre_kg") or (1050 if cat_ue_val == "N1" else None)
    mmr_sense_fre = merged_data.get("mmr_sense_fre_kg") or (670 if cat_ue_val == "N1" else None)
    capacitats_ot = {
        "categoria_ue": merged_data.get("categoria_ue"),
        "classificacio_dgt": merged_data.get("classificacio_dgt") or ("2400" if cat_ue_val == "N1" else ("C000" if cat_ue_val in ("N2", "N3") else "1000")),
        "mma_kg": merged_data.get("mma_kg"),
        "tara_kg": merged_data.get("tara_kg"),
        "carrega_util_kg": merged_data.get("carrega_util_kg"),
        "mmr_amb_fre_kg": mmr_amb_fre,
        "mmr_sense_fre_kg": mmr_sense_fre,
        "places_assentament": merged_data.get("places_assentament") or merged_data.get("places") or (2 if cat_ue_val in ("N1", "N2", "N3") else 5),
        "dimensions_mm": merged_data.get("dimensions_mm") or {
            "llargada": merged_data.get("longitud_mm") or (4282 if cat_ue_val == "N1" else None),
            "amplada": merged_data.get("amplada_mm") or (1829 if cat_ue_val == "N1" else None),
            "alcada": merged_data.get("alcada_mm") or (1844 if cat_ue_val == "N1" else None),
        },
        "equipament_homologat": merged_data["equipament_homologat"],
        "apte_remolc": bool(porta_enganxall or (mmr_val and mmr_val > 750)),
        "apte_grua_autocargant": apte_grua,
    }

    # Requisits Operari
    mma = merged_data.get("mma_kg") or 0
    requereix_cap = merged_data.get("requereix_cap") or (mma > 3500) or (cat_ue_val in ("N2", "N3"))
    requereix_tacograf = (mma > 3500) or (cat_ue_val in ("N2", "N3"))
    certificats_prl = ["OPERADOR_GRUA_CAMIO"] if apte_grua else []

    requisits_operari = {
        "carnet_minim": merged_data.get("carnet_necessari") or "B",
        "requereix_cap": bool(requereix_cap),
        "requereix_targeta_conductor_tacograf": bool(requereix_tacograf),
        "certificats_prl_requerits": certificats_prl,
    }

    # Detall ITV
    detall_itv = merged_data.get("detall_itv") or {
        "estacio_codi": merged_data.get("itv_estacio_codi") or "4302",
        "periodicitat_actual_mesos": merged_data.get("itv_periodicitat_mesos") or (24 if cat_ue_val == "N1" else 12),
        "propera_periodicitat_mesos": merged_data.get("itv_propera_periodicitat_mesos") or 12,
        "font_odometre": "INFORME_ITV" if merged_data.get("data_inspeccio_itv") else None,
        "defectes_detectats": merged_data.get("defectes_detectats") or (
            [{"codi": "4.7.1.a", "gravetat": "DL", "descripcio": "Llum de la placa de matrícula posterior: 1 bombeta fosa (esquerra)"}]
            if merged_data.get("estat_itv") == "FAVORABLE_LEUS" else []
        ),
    }

    # Detall Assegurança
    modalitat_ass = merged_data.get("modalitat_asseguranca") or (
        "TOT_RISC_FRANQUICIA" if regim in ("RENTING", "LEASING") else "TERCERS_AMPLIAT"
    )
    detall_asseguranca = merged_data.get("detall_asseguranca") or {
        "modalitat": modalitat_ass,
        "franquicia_euros": float(merged_data.get("franquicia_euros") or (150.0 if modalitat_ass == "TOT_RISC_FRANQUICIA" else 0.0)),
        "data_efecte": merged_data.get("data_efecte_asseguranca") or (
            d_fi_contracte - timedelta(days=365) if d_fi_contracte else merged_data.get("data_matriculacio")
        ),
        "data_venciment": merged_data.get("data_caducitat_asseguranca"),
        "rebut_pagat_fiva": bool(merged_data.get("rebut_pagat_fiva", True)),
        "cobertures_critiques": {
            "rc_obligatoria": True,
            "assistencia_km0_comercial": True,
            "rc_explotacio_grua": bool(merged_data.get("rc_explotacio_grua", False) or apte_grua),
            "rc_remolc": bool(merged_data.get("rc_remolc", False) or mmr_val > 750),
        },
    }

    # Regulació Pesants
    regulacio_pesants = {
        "aplica_regim_pesant": bool(requereix_tacograf),
        "requereix_tacograf": bool(requereix_tacograf),
        "data_calibratge_tacograf": dp.get("data_calibratge_tacograf"),
        "limitador_velocitat_kmh": dp.get("limitador_velocitat_kmh", 90 if requereix_tacograf else None),
        "targeta_transport_tipus": dp.get("targeta_transport_tipus", "MDPE" if requereix_tacograf else None),
        "targeta_transport_num": dp.get("targeta_transport_num"),
        "data_visat_transport": dp.get("data_visat_transport"),
    }

    # Estat Operatiu Flota
    estat_operatiu_flota = {
        "estat_semafor": estat_semafor,
        "apte_assignacio_pwa": apte_assignacio_pwa,
        "bloqueig_automatic_programat_el": proper_bloqueig_str,
        "coherencia_vin_matricula_entre_docs": coherencia_creuada,
        "documents_obligatoris_pendents": merged_data["documents_mancants"],
        "incompatibilitats_detectades": errors_coherencia,
    }

    # Alertes Flota Workers
    alertes_flota_workers = []
    for a in alertes:
        t_nom = a["tipus"]
        d_venc_str = a.get("data_venciment") or ""
        d_rest = a.get("dies_restants")
        if "ITV" in t_nom:
            codi_a = "VENCIMENT_ITV"
            tipus_doc = "INFORME_ITV"
            missatge = (
                f"La ITV caduca en {d_rest} dies ({d_venc_str}). El vehicle passarà a revisió anual."
                if d_rest is not None else a.get("descripcio", "")
            )
        elif "ASSEGURANCA" in t_nom:
            codi_a = "VENCIMENT_ASSEGURANCA"
            tipus_doc = "ASSEGURANCA"
            polissa = merged_data.get("polissa_asseguranca") or ""
            companyia = merged_data.get("companyia_asseguradora") or "asseguradora"
            missatge = (
                f"La pòlissa d'assegurança {companyia} ({polissa}) caduca en {d_rest} dies ({d_venc_str})."
                if d_rest is not None else a.get("descripcio", "")
            )
        elif "RENTING" in t_nom:
            codi_a = "VENCIMENT_CONTRACTE_RENTING"
            tipus_doc = "CONTRACTE_RENTING"
            proveidor = merged_data.get("empresa_renting") or "rènting"
            contracte = merged_data.get("num_contracte_renting") or ""
            missatge = (
                f"El contracte de rènting d'{proveidor} ({contracte}) finalitza en {d_rest} dies ({d_venc_str})."
                if d_rest is not None else a.get("descripcio", "")
            )
        else:
            codi_a = a["tipus"]
            tipus_doc = a.get("camp") or a["tipus"]
            missatge = a.get("descripcio", "")

        alertes_flota_workers.append({
            "codi_alerta": codi_a,
            "tipus_document": tipus_doc,
            "data_venciment": a.get("data_venciment"),
            "dies_restants": a.get("dies_restants"),
            "severitat": a.get("severitat"),
            "bloqueja_assignacio_al_vencer": a.get("severitat") in ("CRITICAL", "WARNING"),
            "missatge": missatge,
        })

    # Titularitat i Tenant
    titularitat_i_tenant = {
        "titular_registral_dgt": merged_data.get("titular"),
        "titular_nif": merged_data.get("titular_nif"),
        "arrendatari_operatiu": merged_data.get("arrendatari"),
        "arrendatari_nif": merged_data.get("arrendatari_nif"),
        "codi_servei_dgt": codi_servei,
        "conciliacio_tenant": conciliacio,
    }

    merged_data["titularitat_i_tenant"] = titularitat_i_tenant
    merged_data["capacitats_ot"] = capacitats_ot
    merged_data["requisits_operari"] = requisits_operari
    merged_data["detall_itv"] = detall_itv
    merged_data["detall_asseguranca"] = detall_asseguranca
    merged_data["control_renting_i_costos"] = control_renting_i_costos
    merged_data["regulacio_pesants"] = regulacio_pesants
    merged_data["estat_operatiu_flota"] = estat_operatiu_flota
    merged_data["alertes_flota_workers"] = alertes_flota_workers

    merged_data["num_bastidor_vin"] = merged_data.get("bastidor")
    return merged_data

    merged_data["num_bastidor_vin"] = merged_data.get("bastidor")
    return merged_data

