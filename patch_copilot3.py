import re

path = "/media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/copilot.py"
with open(path, "r") as f:
    text = f.read()

target1 = """    return {
        "trobat": True,
        "vehicle_id": str(v.id),"""
replace1 = """    
    from app.models.models import DocumentFlota
    stmt_docs = select(DocumentFlota).where(DocumentFlota.vehicle_id == v.id, DocumentFlota.empresa_id == empresa_id)
    res_docs = await db.execute(stmt_docs)
    docs = res_docs.scalars().all()
    docs_list = [{"tipus": d.tipus_document, "nom_arxiu": d.nom_arxiu, "data": d.data_document.isoformat() if d.data_document else None} for d in docs]
    
    return {
        "trobat": True,
        "vehicle_id": str(v.id),
        "documents": docs_list,"""
text = text.replace(target1, replace1)

target2 = """                    f"Consum: {tool_res.get('consum_l_100km') or 'N/A'} L/100km. "
                    f"Odòmetre: {tool_res['odometre_acumulat']} km."
                )"""
replace2 = """                    f"Consum: {tool_res.get('consum_l_100km') or 'N/A'} L/100km. "
                    f"Odòmetre: {tool_res['odometre_acumulat']} km. "
                    f"Pòlissa Assegurança: {tool_res.get('polissa_asseguranca', 'Desconeguda')}. "
                    f"Documents Registrats: {len(tool_res.get('documents', []))} arxius."
                )"""
text = text.replace(target2, replace2)

with open(path, "w") as f:
    f.write(text)
print("Copilot patched to include documents")
