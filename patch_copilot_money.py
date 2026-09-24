import re

with open("backend/app/api/v1/gestio/copilot.py", "r") as f:
    content = f.read()

# 1. Add tool to TOOLS_SCHEMA
new_tool = """    {
        "type": "function",
        "function": {
            "name": "get_unbilled_money",
            "description": "Calcula quants diners no han estat facturats comparant els treballs tancats i el material instal·lat amb les factures emeses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mes": {
                        "type": "integer",
                        "description": "Mes de l'any a analitzar (1-12), opcional. Si no es posa es fa global."
                    }
                }
            }
        }
    },
"""

content = content.replace("TOOLS_SCHEMA = [", "TOOLS_SCHEMA = [\n" + new_tool)

# 2. Add execution engine function
new_executor = """
async def execute_tool_get_unbilled_money(db: AsyncSession, empresa_id: uuid.UUID, mes: int = None) -> dict:
    from sqlalchemy import select, func, and_
    from app.models.models import OrdreTreball, FullaPicking, LiniaPicking, Article, FacturaLinia

    # Cost material instal·lat en OT's tancades / facturades vs no facturades
    # 1. Cost material de OTs "TANCADA"
    condicions_ot = [OrdreTreball.empresa_id == empresa_id, OrdreTreball.estat == 'TANCADA']
    if mes:
        # PostgreSQL extract
        condicions_ot.append(func.extract('month', OrdreTreball.data_planificacio) == mes)
        
    stmt_cost = (
        select(func.sum(LiniaPicking.quantitat_carregada_pick_in * Article.preu_venda))
        .join(FullaPicking, LiniaPicking.picking_id == FullaPicking.id)
        .join(OrdreTreball, FullaPicking.ordre_treball_id == OrdreTreball.id)
        .join(Article, LiniaPicking.article_id == Article.id)
        .where(and_(*condicions_ot))
    )
    res_cost = await db.execute(stmt_cost)
    cost_materials_esperat = res_cost.scalar() or 0.0

    # 2. Ingressos facturats per aquestes mateixes OTs
    stmt_fact = (
        select(func.sum(FacturaLinia.preu_venda_unitari * FacturaLinia.quantitat))
        .join(OrdreTreball, FacturaLinia.obra_id == OrdreTreball.id)
        .where(and_(*condicions_ot))
    )
    res_fact = await db.execute(stmt_fact)
    facturat_real = res_fact.scalar() or 0.0

    diferencia = float(cost_materials_esperat) - float(facturat_real)
    
    return {
        "trobat": True,
        "cost_materials_consumit_pvp": float(cost_materials_esperat),
        "facturat_real": float(facturat_real),
        "diner_no_facturat": diferencia,
        "missatge": f"L'anàlisi mostra que el material consumit a preu de venda val {cost_materials_esperat:.2f}€, però només s'ha facturat {facturat_real:.2f}€. Falten per facturar {diferencia:.2f}€."
    }
"""

content = content.replace("# Funcions d'Execució d'Eines (Tools Execution Engine)", "# Funcions d'Execució d'Eines (Tools Execution Engine)\n" + new_executor)

# 3. Add to executar_eina
content = content.replace(
    'elif nom_eina == "replanificar_ot":',
    'elif nom_eina == "get_unbilled_money":\n        return await execute_tool_get_unbilled_money(db, empresa_id, args.get("mes"))\n    elif nom_eina == "replanificar_ot":'
)

with open("backend/app/api/v1/gestio/copilot.py", "w") as f:
    f.write(content)

print("Patch applied to copilot.py for Unbilled Money Tool")
