with open("sdd_sevalor/specs/004-gestio-magatzem.md", "r") as f:
    content = f.read()

# Busquem la línia on hi ha el RF-08 i li injectem el detall tècnic
old_rf = """    RF-08 (Unwanted behavior) — Recepció de stock sense justificació documental: QUADA totalment prohibida la recepció física de material o entrada de stock sense albarà o factura de proveïdor associada sota el SIF. QUAN el de Secretaria seleccioni "Entrada assistida per IA", EL SISTEMA processará el document PDF mitjançant el motor OCR de Copilot, identificant les línies, unitats, preu de cost de compra, desglossaments i els associarà asíncronament a l'estoc, validant albarans multi-pedido que pertanyin a comandes de compra diferents."""

new_rf = """    RF-08 (Unwanted behavior) — Recepció de stock sense justificació documental: QUADA totalment prohibida la recepció física de material o entrada de stock sense albarà o factura de proveïdor associada sota el SIF. QUAN el de Secretaria seleccioni "Entrada assistida per IA", EL SISTEMA processará el document PDF mitjançant el motor OCR de Copilot, identificant les línies, unitats, preu de cost de compra, desglossaments i els associarà asíncronament a l'estoc, validant albarans multi-pedido que pertanyin a comandes de compra diferents.
        - **Detall Tècnic d'Integració Asíncrona:** L'endpoint receptor (`POST /api/v1/gestio/magatzem/albara/ocr`) enxamparà la sol·licitud, encolarà la tasca a Celery i retornarà de forma immediata un HTTP 202 Accepted amb la càrrega útil `{"task_id": "<uuid>"}`. Mai blocarà el fil del servidor esperant la resposta de l'OCR de la IA."""

content = content.replace(old_rf, new_rf)

with open("sdd_sevalor/specs/004-gestio-magatzem.md", "w") as f:
    f.write(content)
