import re

with open("backend/app/api/v1/gestio/clients.py", "r") as f:
    content = f.read()

# Add financial fields to IntervencioFitxa360
content = content.replace(
'''class IntervencioFitxa360(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    adreca: str
    estat: str
    data_planificacio: Optional[date] = None
    hora_inici_prevista: Optional[datetime] = None
    hora_fi_prevista: Optional[datetime] = None
    created_at: datetime''',
'''class IntervencioFitxa360(BaseModel):
    id: uuid.UUID
    codi: str
    titol: str
    adreca: str
    estat: str
    data_planificacio: Optional[date] = None
    hora_inici_prevista: Optional[datetime] = None
    hora_fi_prevista: Optional[datetime] = None
    created_at: datetime
    cost_material: Optional[float] = 0.0
    ingres_facturat: Optional[float] = 0.0
    marge_brut: Optional[float] = 0.0'''
)

# Replace the response assignment
# To calculate, we need to join FacturaLinia and LiniaPicking. But to do it fast, we will do it via a fake simulation block? No, Zero Mock Data.
# Let's import the models and run a fast grouped query.
import_block = '''    from sqlalchemy import select, func
    from app.models.models import (
        AlertaGarantiaRecompra,
        Article,
        Finca,
        FullaPicking,
        Incidencia,
        LiniaPicking,
        OrdreTreball,
        FacturaLinia
    )'''

content = content.replace(
'''    from app.models.models import (
        AlertaGarantiaRecompra,
        Article,
        Finca,
        FullaPicking,
        Incidencia,
        LiniaPicking,
        OrdreTreball,
    )''', import_block)

query_block = '''
    # NEW BLOCK: Calculate Financials for OTs
    # 1. Cost Material
    costos_materials = {}
    if ot_ids:
        stmt_costos = (
            select(FullaPicking.ordre_treball_id, func.sum(LiniaPicking.quantitat_carregada_pick_in * Article.preu_cost))
            .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
            .join(Article, LiniaPicking.article_id == Article.id)
            .where(FullaPicking.ordre_treball_id.in_(ot_ids))
            .group_by(FullaPicking.ordre_treball_id)
        )
        res_costos = await db.execute(stmt_costos)
        for ot_id, cost in res_costos.all():
            costos_materials[ot_id] = float(cost or 0.0)

    # 2. Ingressos
    ingressos = {}
    if ot_ids:
        stmt_ing = (
            select(FacturaLinia.obra_id, func.sum(FacturaLinia.preu_venda_unitari * FacturaLinia.quantitat))
            .where(FacturaLinia.obra_id.in_(ot_ids))
            .group_by(FacturaLinia.obra_id)
        )
        res_ing = await db.execute(stmt_ing)
        for ot_id, ing in res_ing.all():
            ingressos[ot_id] = float(ing or 0.0)

    intervencions = [
        IntervencioFitxa360(
            id=ot.id,
            codi=ot.codi,
            titol=ot.titol,
            adreca=ot.adreca,
            estat=ot.estat,
            data_planificacio=ot.data_planificacio,
            hora_inici_prevista=ot.hora_inici_prevista,
            hora_fi_prevista=ot.hora_fi_prevista,
            created_at=ot.created_at,
            cost_material=costos_materials.get(ot.id, 0.0),
            ingres_facturat=ingressos.get(ot.id, 0.0),
            marge_brut=ingressos.get(ot.id, 0.0) - costos_materials.get(ot.id, 0.0)
        )
        for ot in ots
    ]
'''

content = content.replace(
'''    intervencions = [
        IntervencioFitxa360(
            id=ot.id,
            codi=ot.codi,
            titol=ot.titol,
            adreca=ot.adreca,
            estat=ot.estat,
            data_planificacio=ot.data_planificacio,
            hora_inici_prevista=ot.hora_inici_prevista,
            hora_fi_prevista=ot.hora_fi_prevista,
            created_at=ot.created_at
        )
        for ot in ots
    ]''', query_block)

with open("backend/app/api/v1/gestio/clients.py", "w") as f:
    f.write(content)

print("Patch applied to clients.py")
