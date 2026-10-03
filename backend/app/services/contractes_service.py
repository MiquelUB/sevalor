import uuid
from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contractes import ContracteManteniment, RevisionsContracte
from app.models.models import Client, OrdreTreball


async def generar_ordres_preventives_per_contracte(
    contracte: ContracteManteniment,
    db: AsyncSession
) -> list[uuid.UUID]:
    """Genera les ordres de treball i revisions previstes per a un contracte donat el seu estat."""
    if contracte.estat != "ACTIU":
        return []

    # Calcular pròximes dates segons la periodicitat
    data_actual = date.today()
    if contracte.data_fi and contracte.data_fi < data_actual:
        contracte.estat = "VENCUT"
        await db.commit()
        return []

    # Comprovem quina va ser l'última revisió generada
    stmt_ult = select(RevisionsContracte).where(RevisionsContracte.contracte_id == contracte.id).order_by(RevisionsContracte.data_prevista.desc())
    res_ult = await db.execute(stmt_ult)
    ultima_revisio = res_ult.scalars().first()

    data_base = ultima_revisio.data_prevista if ultima_revisio else contracte.data_inici

    intervals = {
        "MENSUAL": relativedelta(months=1),
        "TRIMESTRAL": relativedelta(months=3),
        "SEMESTRAL": relativedelta(months=6),
        "ANUAL": relativedelta(years=1)
    }

    interval = intervals.get(contracte.periodicitat, relativedelta(years=1))

    noves_ordres_ids = []

    # Generem les revisions fins a 1 any vista o fins la data_fi del contracte
    limit_date = data_actual + relativedelta(years=1)
    if contracte.data_fi and contracte.data_fi < limit_date:
        limit_date = contracte.data_fi

    data_seguent = data_base + interval
    # Si és la primera, i no hem arribat a la primera data planificada, no generem sobre data_inici si és futura, o si

    client_res = await db.execute(select(Client).where(Client.id == contracte.client_id))
    client = client_res.scalars().first()
    client_rao_social = client.rao_social if client else "Desconegut"

    while data_seguent <= limit_date:
        if data_seguent < data_actual:
            # Ja ha passat o estem a la data i no s'havia generat
            data_seguent_iter = data_seguent + interval
            if data_seguent_iter <= limit_date:
                data_seguent = data_seguent_iter
                continue # Ometem generació d'OTs antigues que es van obviar, o les generem igualment? Generarem només les actuals/imminents.

        # Generar Revisió
        revisio = RevisionsContracte(
            empresa_id=contracte.empresa_id,
            contracte_id=contracte.id,
            data_prevista=data_seguent,
            estat="GENERADA_OT"
        )
        db.add(revisio)
        await db.flush()

        # Generar Ordre Treball
        nova_ot = OrdreTreball(
            empresa_id=contracte.empresa_id,
            client_id=contracte.client_id,
            codi=f"PREV-{contracte.numero_contracte}-{data_seguent.strftime('%Y%m')}",
            titol=f"Manteniment Preventiu - {client_rao_social}",
            adreca=client.adreca_fiscal if client and client.adreca_fiscal else "Sense adreça",
            estat="PENDENT",
            descripcio="Generada automàticament per contracte de manteniment",
            data_planificacio=data_seguent
        )
        db.add(nova_ot)
        await db.flush()

        revisio.ordre_treball_id = nova_ot.id
        noves_ordres_ids.append(nova_ot.id)

        data_seguent = data_seguent + interval

    await db.commit()
    return noves_ordres_ids
