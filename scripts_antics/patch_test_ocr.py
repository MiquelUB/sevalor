with open("backend/tests/test_004_gestio_magatzem_ocr.py", "r") as f:
    content = f.read()

import re
# Remove the old pas1
content = re.sub(r'# Pas 1.*?assert data_ocr\["proveidor"\]\["nom"\] == "Jardineria Verda, S\.A\."',
                 '''# Pas 1: Pujar arxiu (Ara en Background - Spec 004 RF-08)
        file_content = b"Mock PDF/Image Data"
        files = {"fitxer": ("albara.pdf", file_content, "application/pdf")}
        res_ocr = await ac.post("/api/v1/gestio/magatzem/albara/ocr", files=files, headers=headers)
        assert res_ocr.status_code == 202
        data_ocr = res_ocr.json()
        assert "task_id" in data_ocr
        
        # Simulem que hem rebut les dades processades per la IA per continuar el flux
        mock_numero = "ALB-2026-123"''',
                 content, flags=re.DOTALL)

content = content.replace('data_ocr["proveidor"]', '{"nif": "A12345678", "nom": "Jardineria Verda, S.A.", "adreca": "C/ de les Flors, 45", "telefon": "931234567", "email": "info@jardineriaverda.cat"}')
content = content.replace('data_ocr["numero_document"]', 'mock_numero')

with open("backend/tests/test_004_gestio_magatzem_ocr.py", "w") as f:
    f.write(content)
