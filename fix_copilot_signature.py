path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py"
with open(path, "r") as f:
    text = f.read()

target = """async def cridar_lm_studio_amb_tools(
    pregunta: str,
    vertical: str,
    db: AsyncSession,
    empresa_id: uuid.UUID,
    imatge_b64: Optional[str] = None
):"""

replacement = """async def cridar_lm_studio_amb_tools(
    pregunta: str,
    vertical: str,
    db: AsyncSession,
    empresa_id: uuid.UUID,
    imatge_b64: Optional[str] = None,
    agent_prompt_system: Optional[str] = None
):"""
text = text.replace(target, replacement)
with open(path, "w") as f:
    f.write(text)
print("Copilot signature fixed.")
