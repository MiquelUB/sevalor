import re

with open("backend/app/api/v1/gestio/copilot.py", "r") as f:
    content = f.read()

# 1. Update ConsultaXatIn
content = content.replace(
'''class ConsultaXatIn(BaseModel):
    pregunta: str''',
'''class ConsultaXatIn(BaseModel):
    pregunta: str
    imatge_b64: Optional[str] = None'''
)

# 2. Add parameter to endpoints
content = content.replace(
'''async def xat_copilot(
    dades: ConsultaXatIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims)
):''',
'''async def xat_copilot(
    dades: ConsultaXatIn,
    db: AsyncSession = Depends(get_db_with_tenant_context),
    claims: dict = Depends(get_current_user_claims)
):'''
)

# Wait, I need to pass imatge_b64 to the agent executor.
content = content.replace(
'''async def cridar_lm_studio_amb_tools(
    pregunta: str,
    vertical: str,
    db: AsyncSession,
    empresa_id: uuid.UUID
) -> Tuple[Optional[str], Optional[str], Optional[dict], Optional[dict]]:''',
'''async def cridar_lm_studio_amb_tools(
    pregunta: str,
    vertical: str,
    db: AsyncSession,
    empresa_id: uuid.UUID,
    imatge_b64: Optional[str] = None
) -> Tuple[Optional[str], Optional[str], Optional[dict], Optional[dict]]:'''
)

content = content.replace(
'''    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": pregunta}
    ]''',
'''    
    user_content = pregunta
    if imatge_b64:
        user_content = [
            {"type": "text", "text": pregunta or "Analitza aquesta imatge."},
            {"type": "image_url", "image_url": {"url": imatge_b64}}
        ]
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]'''
)

content = content.replace(
'''    resposta_ia, tool_name, tool_args, tool_result = await cridar_lm_studio_amb_tools(
        dades.pregunta, vertical, db, empresa_id
    )''',
'''    resposta_ia, tool_name, tool_args, tool_result = await cridar_lm_studio_amb_tools(
        dades.pregunta, vertical, db, empresa_id, dades.imatge_b64
    )'''
)

# If LM studio fails, fallback local shouldn't crash if it expects string, but local doesn't use imatge_b64 yet, so we don't pass it.
with open("backend/app/api/v1/gestio/copilot.py", "w") as f:
    f.write(content)

print("Patch applied to copilot.py for Multimodal")
