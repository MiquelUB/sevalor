
with open("app/api/v1/gestio/magatzem.py", "r") as f:
    content = f.read()

old_ocr = """    import random
    from datetime import date
    
    return {
        "proveidor": {
            "nif": "A12345678",
            "nom": "Jardineria Verda, S.A.",
            "adreca": "C/ de les Flors, 45, 08001 Barcelona",
            "telefon": "931234567",
            "email": "info@jardineriaverda.cat"
        },
        "numero_document": f"ALB-2026-{random.randint(100, 999)}",
        "tipus_document": "ALBARA",
        "data_document": "2026-08-01",
        "numero_albarans_vinculats": [],
        "linies": [
            {
                "referencia": "CAB-2MM-01",
                "nom": "Bobina Cable Flex",
                "quantitat": 100,
                "preu": 0.50,
                "descompte_percent": 0.0,
                "tipus": "MATERIAL"
            },
            {
                "referencia": "TLL-18V",
                "nom": "Tornavis",
                "quantitat": 1,
                "preu": 150.0,
                "descompte_percent": 10.0,
                "tipus": "EINA"
            }
        ]
    }"""

new_ocr = """    import random
    import json
    import fitz  # PyMuPDF
    from datetime import date
    from app.api.v1.gestio.copilot import cridar_lm_studio
    
    # 1. Extracció del contingut del PDF
    text_extret = ""
    try:
        contingut_pdf = await fitxer.read()
        doc = fitz.open(stream=contingut_pdf, filetype="pdf")
        for page in doc:
            text_extret += page.get_text()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error llegint el PDF: {str(e)}")
        
    if not text_extret.strip():
        raise HTTPException(status_code=400, detail="El PDF està buit o no conté text llegible.")

    # 2. Cridar a LM Studio (Copilot IA)
    prompt_sistema = (
        "Analitza aquest text extret d'un albarà o factura. "
        "Retorna EXCLUSIVAMENT un objecte JSON vàlid amb aquesta estructura exacta, sense markdown ni text addicional: "
        '{"proveidor": {"nif": "", "nom": "", "adreca": "", "telefon": "", "email": ""}, '
        '"numero_document": "", "tipus_document": "ALBARA" (o "FACTURA"), "data_document": "YYYY-MM-DD", '
        '"numero_albarans_vinculats": [], '
        '"linies": [{"referencia": "", "nom": "", "quantitat": 0, "preu": 0.0, "descompte_percent": 0.0, "tipus": "MATERIAL"}]}'
    )
    
    resposta_ia = await cridar_lm_studio(
        pregunta=f"Aquest és el text del document:\n\n{text_extret}",
        vertical="LOGISTICA",
        context_addicional=prompt_sistema
    )
    
    if not resposta_ia:
        # Fallback de desenvolupament (Testing / CI sense LM Studio)
        import os
        if os.getenv("TESTING") == "1":
            return {
                "proveidor": {
                    "nif": "A12345678",
                    "nom": "Jardineria Verda, S.A.",
                    "adreca": "C/ de les Flors, 45, 08001 Barcelona",
                    "telefon": "931234567",
                    "email": "info@jardineriaverda.cat"
                },
                "numero_document": f"ALB-2026-{random.randint(100, 999)}",
                "tipus_document": "ALBARA",
                "data_document": "2026-08-01",
                "numero_albarans_vinculats": [],
                "linies": [
                    {
                        "referencia": "CAB-2MM-01",
                        "nom": "Bobina Cable Flex",
                        "quantitat": 100,
                        "preu": 0.50,
                        "descompte_percent": 0.0,
                        "tipus": "MATERIAL"
                    }
                ]
            }
        raise HTTPException(status_code=503, detail="El servei Copilot IA no està disponible (LM Studio apagat).")

    try:
        # Netejar possibles marcadores Markdown
        net = resposta_ia.strip()
        if net.startswith("```json"):
            net = net[7:]
        if net.startswith("```"):
            net = net[3:]
        if net.endswith("```"):
            net = net[:-3]
            
        dades = json.loads(net.strip())
        return dades
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"La IA ha retornat un format invàlid: {str(e)}")"""

content = content.replace(old_ocr, new_ocr)

with open("app/api/v1/gestio/magatzem.py", "w") as f:
    f.write(content)
