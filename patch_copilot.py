import re

with open("backend/app/api/v1/gestio/copilot.py", "r") as f:
    content = f.read()

# 1. Add tool to TOOLS_SCHEMA
new_tool = """    {
        "type": "function",
        "function": {
            "name": "replanificar_ot",
            "description": "Proposa re-planificar una Ordre de Treball (canvi de data o tècnic assignat). L'acció no s'executa immediatament, es demana confirmació a l'usuari.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codi_ot": {
                        "type": "string",
                        "description": "Codi de l'Ordre de Treball (ex: 'OT-2026-001')"
                    },
                    "nova_data": {
                        "type": "string",
                        "description": "Nova data de planificació en format YYYY-MM-DD"
                    }
                },
                "required": ["codi_ot", "nova_data"]
            }
        }
    },
"""

content = content.replace("TOOLS_SCHEMA = [", "TOOLS_SCHEMA = [\n" + new_tool)

# 2. Add execute_tool_replanificar_ot
new_executor = """
async def execute_tool_replanificar_ot(db: AsyncSession, empresa_id: uuid.UUID, codi_ot: str, nova_data: str) -> dict:
    from sqlalchemy import select
    from app.models.models import OrdreTreball
    q = select(OrdreTreball).where(OrdreTreball.empresa_id == empresa_id, OrdreTreball.codi == codi_ot)
    res = await db.execute(q)
    ot = res.scalar_one_or_none()
    if not ot:
        return {"trobat": False, "missatge": f"No s'ha trobat l'ordre de treball {codi_ot}."}
    
    # En lloc de canviar-ho directament, retornem una proposta
    return {
        "trobat": True,
        "requires_confirmation": True,
        "action": "confirm_replanificar_ot",
        "payload": {
            "ot_id": str(ot.id),
            "codi_ot": codi_ot,
            "nova_data": nova_data,
            "titol": ot.titol
        },
        "missatge": f"He preparat la proposta per moure l'ordre {codi_ot} ({ot.titol}) al dia {nova_data}. Necessito la teva confirmació per executar l'acció."
    }
"""

content = content.replace("# Funcions d'Execució d'Eines (Tools Execution Engine)", "# Funcions d'Execució d'Eines (Tools Execution Engine)\n" + new_executor)

# 3. Add to executar_eina
content = content.replace(
    'elif nom_eina == "get_rag_knowledge":',
    'elif nom_eina == "replanificar_ot":\n        return await execute_tool_replanificar_ot(db, empresa_id, args.get("codi_ot", ""), args.get("nova_data", ""))\n    elif nom_eina == "get_rag_knowledge":'
)

# 4. Add action endpoint ActionConfirmIn
new_endpoint = """
class ActionConfirmIn(BaseModel):
    action: str
    payload: dict

@router.post("/action/confirm")
async def confirmar_accio_copilot(
    dades: ActionConfirmIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims)
):
    empresa_id = uuid.UUID(claims["empresa_id"])
    if dades.action == "confirm_replanificar_ot":
        from app.models.models import OrdreTreball
        from sqlalchemy import update
        ot_id = uuid.UUID(dades.payload["ot_id"])
        nova_data_str = dades.payload["nova_data"]
        try:
            nova_data = date.fromisoformat(nova_data_str)
        except:
            raise HTTPException(400, "Format de data invàlid. Esperat YYYY-MM-DD.")
            
        stmt = update(OrdreTreball).where(
            OrdreTreball.id == ot_id, 
            OrdreTreball.empresa_id == empresa_id
        ).values(data_planificacio=nova_data)
        
        await db.execute(stmt)
        await db.commit()
        return {"success": True, "missatge": f"S'ha replanificat l'OT correctament al {nova_data_str}."}
    
    raise HTTPException(400, "Acció desconeguda o no suportada.")
"""

content = content + "\n" + new_endpoint

with open("backend/app/api/v1/gestio/copilot.py", "w") as f:
    f.write(content)

print("Patch applied to copilot.py")
