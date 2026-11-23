import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_with_tenant_context
from app.core.security import get_current_user_claims
from app.models.models import (
    CapaVectorial,
    Incidencia,
    OrdreTreball,
    RegistreJornadaLaboral,
    TiquetCarburant,
    TiquetDespesa,
    Vehicle,
)
from app.services.reconciliacio_ot_service import desar_signatura_client_ot
from app.services.sovereign_storage import SovereignStorageGateway

router = APIRouter(prefix="/sync", tags=["PWA Sync"])
logger = logging.getLogger(__name__)


class SyncAction(BaseModel):
    id: str = Field(..., description="ID únic de l'acció al client")
    accio: str = Field(..., description="Tipus d'acció (FITXAR_JORNADA, CREAR_TIQUET, etc.)")
    payload: Dict[str, Any] = Field(..., description="Càrrega útil de l'acció")
    timestamp: Optional[int] = Field(None, description="Timestamp de l'acció en client (ms)")


class BulkSyncRequest(BaseModel):
    accions: List[SyncAction] = Field(
        ..., description="Llista d'accions a sincronitzar seqüencialment"
    )


@router.post("/push")
async def bulk_sync_push(
    request: BulkSyncRequest,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """
    Rep una llista d'accions encuades (Offline-First) i les processa seqüencialment.
    Resol conflictes basant-se en el timestamp de l'acció vs DB (Spec 02 - T007).
    """
    processades = 0
    errors = []

    for accio in request.accions:
        try:
            if accio.accio == "FITXAR_JORNADA":
                logger.info(f"Processant FITXAR_JORNADA per {accio.id}")
                lat = float(accio.payload.get("latitud", 0.0))
                lng = float(accio.payload.get("longitud", 0.0))
                tipus_fitxatge = accio.payload.get("tipus", "INICI")
                j_id_str = accio.payload.get("jornada_id")

                if tipus_fitxatge == "FI" and j_id_str:
                    j_res = await db.execute(
                        select(RegistreJornadaLaboral).where(
                            RegistreJornadaLaboral.id == uuid.UUID(str(j_id_str)),
                            RegistreJornadaLaboral.empresa_id == uuid.UUID(claims["empresa_id"]),
                        )
                    )
                    jornada = j_res.scalars().first()
                    if jornada:
                        from datetime import datetime, timezone

                        jornada.hora_fi = datetime.now(timezone.utc)
                        jornada.geolocalitzacio_fi = f"{lat},{lng}"
                        jornada.estat = "COMPLERT"
                        await db.flush()
                        await SovereignStorageGateway.desar_entitat_json(
                            db=db,
                            empresa_id=claims["empresa_id"],
                            categoria="jornades",
                            item_id=str(jornada.id),
                            dades={
                                "id": str(jornada.id),
                                "usuari_id": str(jornada.usuari_id),
                                "estat": jornada.estat,
                                "geolocalitzacio_inici": jornada.geolocalitzacio_inici,
                                "geolocalitzacio_fi": jornada.geolocalitzacio_fi,
                            },
                        )
                else:
                    nova_jornada = RegistreJornadaLaboral(
                        empresa_id=uuid.UUID(claims["empresa_id"]),
                        usuari_id=uuid.UUID(claims["sub"]),
                        geolocalitzacio_inici=f"{lat},{lng}",
                        estat="EN_CURS",
                    )
                    db.add(nova_jornada)
                    await db.flush()
                    await SovereignStorageGateway.desar_entitat_json(
                        db=db,
                        empresa_id=claims["empresa_id"],
                        categoria="jornades",
                        item_id=str(nova_jornada.id),
                        dades={
                            "id": str(nova_jornada.id),
                            "usuari_id": str(nova_jornada.usuari_id),
                            "estat": nova_jornada.estat,
                            "geolocalitzacio_inici": nova_jornada.geolocalitzacio_inici,
                        },
                    )

            elif accio.accio == "CREAR_TIQUET":
                logger.info(f"Processant CREAR_TIQUET per {accio.id}")
                emp_uuid_tiquet = uuid.UUID(claims["empresa_id"])
                usuari_uuid_tiquet = uuid.UUID(claims["sub"])
                v_id = accio.payload.get("vehicle_id")
                if not v_id:
                    v_res = await db.execute(
                        select(Vehicle).where(Vehicle.empresa_id == emp_uuid_tiquet)
                    )
                    v_obj = v_res.scalars().first()
                    v_id = v_obj.id if v_obj else None

                ot_tiquet_raw = accio.payload.get("ordre_treball_id")
                if ot_tiquet_raw:
                    from datetime import date

                    ot_tiquet_uuid = uuid.UUID(str(ot_tiquet_raw))
                    ot_check = await db.execute(
                        select(OrdreTreball.id).where(
                            OrdreTreball.id == ot_tiquet_uuid,
                            OrdreTreball.empresa_id == emp_uuid_tiquet,
                        )
                    )
                    if not ot_check.scalar_one_or_none():
                        raise HTTPException(
                            status_code=404,
                            detail="Ordre de treball no trobada al tenant per al tiquet offline.",
                        )
                    cat_raw = str(accio.payload.get("categoria") or "ALTRES").strip().upper()
                    if cat_raw not in {"CARBURANT", "FERRETERIA", "PEATGES", "DIETES", "ALTRES"}:
                        cat_raw = "ALTRES"
                    nou_tiquet_despesa = TiquetDespesa(
                        id=uuid.uuid4(),
                        empresa_id=emp_uuid_tiquet,
                        categoria=cat_raw,
                        usuari_id=usuari_uuid_tiquet,
                        vehicle_id=uuid.UUID(str(v_id)) if v_id else None,
                        ordre_treball_id=ot_tiquet_uuid,
                        data_tiquet=date.today(),
                        import_total=accio.payload.get(
                            "import_euros", accio.payload.get("import_total")
                        ),
                        estat_aprovacio="PENDENT_PROCESSAMENT",
                        estat_fiscal="PENDENT_OCR",
                        requereix_aprovacio_boss=False,
                        custodia_paper_confirmada=False,
                        nom_fitxer_visible=accio.payload.get("nom_fitxer", "offline_sync.webp"),
                        foto_tiquet_path=accio.payload.get(
                            "tiquet_foto_path", accio.payload.get("nom_fitxer", "offline_sync.webp")
                        ),
                        foto_odometre_path=accio.payload.get("odometre_foto_path"),
                    )
                    db.add(nou_tiquet_despesa)
                    await db.flush()
                    await SovereignStorageGateway.desar_entitat_json(
                        db=db,
                        empresa_id=claims["empresa_id"],
                        categoria="tiquets_despesa",
                        item_id=str(nou_tiquet_despesa.id),
                        dades={
                            "id": str(nou_tiquet_despesa.id),
                            "usuari_id": str(usuari_uuid_tiquet),
                            "ordre_treball_id": str(ot_tiquet_uuid),
                            "categoria": cat_raw,
                            "nom_fitxer_visible": nou_tiquet_despesa.nom_fitxer_visible,
                        },
                    )
                elif v_id:
                    nou_tiquet = TiquetCarburant(
                        empresa_id=emp_uuid_tiquet,
                        operari_id=usuari_uuid_tiquet,
                        vehicle_id=uuid.UUID(str(v_id)),
                        tiquet_foto_path=accio.payload.get("tiquet_foto_path", "offline_sync.webp"),
                        odometre_foto_path=accio.payload.get("odometre_foto_path"),
                        litres=accio.payload.get("litres"),
                        import_=accio.payload.get("import_euros", accio.payload.get("import_total")),
                        odometre_valor=accio.payload.get("odometre_valor"),
                        estat_ocr="PENDENT_AUDITORIA",
                    )
                    db.add(nou_tiquet)
                    await db.flush()
                    await SovereignStorageGateway.desar_entitat_json(
                        db=db,
                        empresa_id=claims["empresa_id"],
                        categoria="tiquets_despesa",
                        item_id=str(nou_tiquet.id),
                        dades={
                            "id": str(nou_tiquet.id),
                            "operari_id": str(nou_tiquet.operari_id),
                            "vehicle_id": str(nou_tiquet.vehicle_id),
                            "import_euros": float(nou_tiquet.import_) if nou_tiquet.import_ is not None else None,
                            "estat_ocr": nou_tiquet.estat_ocr,
                        },
                    )

            elif accio.accio == "REPORTAR_INCIDENCIA":
                logger.info(f"Processant REPORTAR_INCIDENCIA per {accio.id}")
                ambit = accio.payload.get("ambit", "GENERAL")
                estat = accio.payload.get("estat", "VERMELL")
                text_obs = accio.payload.get(
                    "text_observacions", accio.payload.get("descripcio", "")
                )
                audio_path = accio.payload.get("audio_path")
                foto_path = accio.payload.get("foto_path")

                nova_incidencia = Incidencia(
                    empresa_id=uuid.UUID(claims["empresa_id"]),
                    operari_id=uuid.UUID(claims["sub"]),
                    ambit=ambit,
                    estat=estat,
                    text_observacions=text_obs,
                    audio_path=audio_path,
                    foto_path=foto_path,
                )
                db.add(nova_incidencia)
                await db.flush()
                await SovereignStorageGateway.desar_entitat_json(
                    db=db,
                    empresa_id=claims["empresa_id"],
                    categoria="incidencies_registres",
                    item_id=str(nova_incidencia.id),
                    dades={
                        "id": str(nova_incidencia.id),
                        "operari_id": str(nova_incidencia.operari_id),
                        "ambit": nova_incidencia.ambit,
                        "estat": nova_incidencia.estat,
                        "text_observacions": text_obs,
                        "audio_path": audio_path,
                        "foto_path": foto_path,
                    },
                )

            elif accio.accio in ("FINALITZAR_ORDRE", "TANCAR_ORDRE"):
                logger.info(f"Processant {accio.accio} per {accio.id}")
                # Exemple de validació de timestamp (CRDT/Conflict Resolution)
                ordre_id = accio.payload.get("ordre_id")
                if ordre_id:
                    emp_uuid_ot = uuid.UUID(claims["empresa_id"])
                    result = await db.execute(
                        select(OrdreTreball).where(
                            OrdreTreball.id == uuid.UUID(str(ordre_id)),
                            OrdreTreball.empresa_id == emp_uuid_ot,
                        )
                    )
                    ordre = result.scalars().first()

                    if ordre:
                        if accio.timestamp:
                            # Convertim el datetime a timestamp (ms)
                            db_ts = int(ordre.updated_at.timestamp() * 1000) if ordre.updated_at else 0
                            if accio.timestamp < db_ts:
                                logger.warning(
                                    f"Conflicte detectat per a ordre {ordre_id}. Client ts: {accio.timestamp}, DB ts: {db_ts}"
                                )
                                raise HTTPException(
                                    status_code=409,
                                    detail=f"Conflicte detectat a l'ordre {ordre_id}. DB és més recent.",
                                )
                        from datetime import datetime, timezone

                        now_utc = datetime.now(timezone.utc)
                        sig_b64 = accio.payload.get("signatura_base64")
                        if sig_b64:
                            sig_path = await desar_signatura_client_ot(
                                db=db,
                                empresa_id=emp_uuid_ot,
                                ordre_treball_id=ordre.id,
                                signatura_base64=str(sig_b64),
                                exigir_magic_bytes=True,
                            )
                            ordre.signatura_client_path = sig_path
                            ordre.data_signatura = now_utc

                        nom_rec = accio.payload.get("nom_receptor") or accio.payload.get("nom_signant")
                        if nom_rec is not None:
                            ordre.nom_receptor = str(nom_rec).strip()[:150] or None

                        dni_rec = accio.payload.get("dni_receptor") or accio.payload.get("dni_signant")
                        if dni_rec is not None:
                            ordre.dni_receptor = str(dni_rec).strip().upper()[:30] or None

                        obs_tanc = accio.payload.get("observacions") or accio.payload.get(
                            "observacions_tancament"
                        )
                        if obs_tanc is not None:
                            ordre.observacions_tancament = str(obs_tanc).strip()[:2000] or None

                        ordre.estat = "COMPLERT"
                        if ordre.data_finalitzacio_camp is None:
                            ordre.data_finalitzacio_camp = now_utc.date()
                        if (
                            (not ordre.hores_imputades_facturables or float(ordre.hores_imputades_facturables) <= 0)
                            and accio.payload.get("hores")
                        ):
                            ordre.hores_imputades_facturables = round(float(accio.payload["hores"]), 2)
                        await db.flush()
                        await SovereignStorageGateway.desar_entitat_json(
                            db=db,
                            empresa_id=claims["empresa_id"],
                            categoria="ots_historic",
                            item_id=str(ordre.id),
                            dades={
                                "id": str(ordre.id),
                                "codi": ordre.codi,
                                "titol": ordre.titol,
                                "estat": ordre.estat,
                                "hores": float(ordre.hores_imputades_facturables or 0.0),
                                "nom_receptor": ordre.nom_receptor,
                                "dni_receptor": ordre.dni_receptor,
                                "observacions": ordre.observacions_tancament,
                                "signatura_client_path": ordre.signatura_client_path,
                                "data_signatura": (
                                    ordre.data_signatura.isoformat()
                                    if ordre.data_signatura
                                    else None
                                ),
                                "signatura_present": bool(ordre.signatura_client_path),
                            },
                        )

            elif accio.accio == "POST_PLANOL_CAPA":
                logger.info(f"Processant POST_PLANOL_CAPA per {accio.id}")
                planol_id = accio.payload.get("planol_id")
                capa_data = accio.payload.get("capa", {})
                ot_capa_raw = accio.payload.get("ordre_treball_id") or capa_data.get(
                    "ordre_treball_id"
                )
                ot_capa_uuid: Optional[uuid.UUID] = None
                if ot_capa_raw:
                    try:
                        ot_capa_uuid = uuid.UUID(str(ot_capa_raw))
                    except ValueError:
                        ot_capa_uuid = None

                if planol_id:
                    geojson_capa = capa_data.get("geometries_geojson") or capa_data.get(
                        "dades_geojson"
                    )
                    if not isinstance(geojson_capa, dict):
                        pins = capa_data.get("pins", [])
                        features = [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [p.get("x", 0), p.get("y", 0)],
                                },
                                "properties": {"nom": p.get("etiqueta", "Anotació")},
                            }
                            for p in pins
                        ]
                        geojson_capa = {"type": "FeatureCollection", "features": features}
                    nova_capa = CapaVectorial(
                        empresa_id=uuid.UUID(claims["empresa_id"]),
                        planol_base_id=uuid.UUID(str(planol_id)),
                        ordre_treball_id=ot_capa_uuid,
                        nom=capa_data.get("nom", "Capa Operari"),
                        disciplina=capa_data.get("disciplina", "OBRA_CIVIL"),
                        es_immutable=bool(capa_data.get("es_tancada", False)),
                        color_hex=capa_data.get("color_hex", "#0284c7"),
                        gruix_linia=int(capa_data.get("gruix_linia") or 3),
                        opacitat_percent=100,
                        visible=True,
                        geometries_geojson=geojson_capa,
                        version_id=1,
                    )
                    db.add(nova_capa)

            elif accio.accio == "POST_PLANOL_PIN":
                logger.info(f"Processant POST_PLANOL_PIN per {accio.id}")
                planol_id = accio.payload.get("planol_id")
                capa_id = accio.payload.get("capa_id")
                pin = accio.payload.get("pin", {})
                if planol_id and capa_id and pin:
                    capa_uuid = None
                    try:
                        capa_uuid = uuid.UUID(str(capa_id))
                    except ValueError:
                        pass
                    if capa_uuid:
                        res = await db.execute(
                            select(CapaVectorial).where(
                                CapaVectorial.id == capa_uuid,
                                CapaVectorial.empresa_id == uuid.UUID(claims["empresa_id"]),
                            )
                        )
                        capa = res.scalars().first()
                        if capa and not capa.es_immutable:
                            features = list(capa.geometries_geojson.get("features", []))
                            features.append(
                                {
                                    "type": "Feature",
                                    "geometry": {
                                        "type": "Point",
                                        "coordinates": [pin.get("x", 0), pin.get("y", 0)],
                                    },
                                    "properties": {"nom": pin.get("etiqueta", "Anotació")},
                                }
                            )
                            capa.geometries_geojson = {
                                "type": "FeatureCollection",
                                "features": features,
                            }
                            capa.version_id += 1

            elif accio.accio == "USE_MATERIAL_FROM_VAN":
                logger.info(f"Processant USE_MATERIAL_FROM_VAN per {accio.id}")
                from app.services.picking_stock_service import registrar_consum_material_furgoneta

                ot_raw = accio.payload.get("ordre_treball_id") or accio.payload.get("ordre_camp_id")
                art_raw = accio.payload.get("article_id")
                qty_raw = accio.payload.get("quantitat")
                if not ot_raw or not art_raw or not qty_raw:
                    raise HTTPException(
                        status_code=422,
                        detail="USE_MATERIAL_FROM_VAN requereix ordre_treball_id, article_id i quantitat.",
                    )
                mag_raw = accio.payload.get("magatzem_id")
                await registrar_consum_material_furgoneta(
                    db=db,
                    empresa_id=uuid.UUID(claims["empresa_id"]),
                    ordre_treball_id=uuid.UUID(str(ot_raw)),
                    article_id=uuid.UUID(str(art_raw)),
                    quantitat=float(qty_raw),
                    quantitat_mermada=float(accio.payload.get("quantitat_mermada") or 0.0),
                    magatzem_id=uuid.UUID(str(mag_raw)) if mag_raw else None,
                    usuari_id=uuid.UUID(claims["sub"]) if claims.get("sub") else None,
                    notes=accio.payload.get("notes"),
                    auto_commit=False,
                )

            else:
                logger.warning(f"Acció desconeguda: {accio.accio}")

            processades += 1

        except HTTPException as e:
            if e.status_code == 409:
                errors.append({"id": accio.id, "error": e.detail, "status": 409})
            else:
                errors.append({"id": accio.id, "error": str(e), "status": e.status_code})
        except Exception as e:
            logger.error(f"Error processant acció {accio.id}: {str(e)}")
            errors.append({"id": accio.id, "error": str(e), "status": 500})

    await db.commit()

    # Si hi ha conflictes, responem 207 (Multi-Status) o un 200 amb detall
    return {"status": "ok", "processades": processades, "errors": errors}


@router.get("/hud")
async def get_hud_stats(
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: Dict[str, Any] = Depends(get_current_user_claims),
):
    """
    Retorna les estadístiques diàries per al HUD de l'operari.
    (S'executa quan hi ha connectivitat).
    """
    import datetime

    from sqlalchemy import func

    avui = datetime.date.today()
    operari_id_uuid = uuid.UUID(claims["sub"])

    # Ordres de treball per avui assignades a l'operari
    query_ordres = (
        select(OrdreTreball.estat, func.count(OrdreTreball.id))
        .where(
            OrdreTreball.cap_de_colla_id == operari_id_uuid, OrdreTreball.data_planificacio == avui
        )
        .group_by(OrdreTreball.estat)
    )

    result_ordres = await db.execute(query_ordres)
    ordres = result_ordres.all()

    ordres_pendents = sum(count for estat, count in ordres if estat == "PENDENT")
    ordres_completades = sum(count for estat, count in ordres if estat == "COMPLETADA")

    # Incidències creades avui per l'operari
    query_inc = select(func.count(Incidencia.id)).where(
        Incidencia.operari_id == operari_id_uuid, func.date(Incidencia.created_at) == avui
    )

    result_inc = await db.execute(query_inc)
    incidencies_avui = result_inc.scalar() or 0

    return {
        "ordres_pendents": ordres_pendents,
        "ordres_completades": ordres_completades,
        "incidencies_avui": incidencies_avui,
        "data": avui.isoformat(),
    }
