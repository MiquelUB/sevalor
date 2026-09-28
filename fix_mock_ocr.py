path = "/media/akaun/Project_1/SEVALOR/backend/app/workers/tasks.py"
with open(path, "r") as f:
    text = f.read()

target = """    return {
        "estat": "COMPLETADO",
        "proveidor": {
            "nif": "PENDENT_VERIFICACIO",
            "nom": f"Document {nom_base}",
            "adreca": "",
            "telefon": "",
            "email": ""
        },
        "numero_document": f"DOC-{nom_base}",
        "tipus_document": "ALBARA"
    }"""

replacement = """    return {
        "estat": "COMPLETADO",
        "proveidor": {
            "nif": "PENDENT_VERIFICACIO",
            "nom": f"Document {nom_base}",
            "adreca": "",
            "telefon": "",
            "email": ""
        },
        "numero_document": f"DOC-{nom_base}",
        "tipus_document": "ALBARA",
        "data_document": "2024-01-01",
        "linies": [
            {
                "referencia": "ART-OCR-MAT-01",
                "nom": "Cable coure 1.5mm2",
                "quantitat": 100,
                "preu": 1.25,
                "descompte_percent": 0.0,
                "tipus": "MATERIAL"
            },
            {
                "referencia": "BOSCH-GSB-18",
                "nom": "Taladro Percutor Bosch 18V",
                "quantitat": 2,
                "preu": 180.50,
                "descompte_percent": 15.0,
                "tipus": "EINA"
            }
        ]
    }"""

if target in text:
    text = text.replace(target, replacement)
    print("Mock OCR replaced!")
else:
    print("Mock target not found")

with open(path, "w") as f:
    f.write(text)
