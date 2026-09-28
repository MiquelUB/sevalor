import re

# 1. Update Spec 006 (Flota)
path_flota = "sevalor_AgentV2/docs/sdd/specs/006-gestio-flota.md"
with open(path_flota, "r") as f:
    text_flota = f.read()

rf_target = "### Requisitos Funcionales"
rf_replacement = """### Requisitos Funcionales

#### RF-00: Alta Màgica de Vehicles via OCR (Zero Data Entry)
- **QUÉ**: El sistema debe permitir crear la ficha completa de un vehículo o remolque simplemente subiendo una fotografía o PDF de la Ficha Técnica, el Permiso de Circulación o la Póliza de Seguro.
- **PER QUÉ**: Para eliminar el error humano en la transcripción de bastidores, matrículas y características técnicas (MMA, plazas, propulsión), acelerando el proceso de onboarding del parque móvil siguiendo la filosofía estricta de Zero Data Entry.
- **CÓMO**: A través de un endpoint (`POST /api/v1/gestio/flota/ocr-draft`) que utiliza el LLM de visión para devolver un JSON pre-rellenado que la UI presentará en el formulario de alta. Los documentos originales quedarán automáticamente archivados en el volumen soberano del vehículo."""

if rf_target in text_flota:
    text_flota = text_flota.replace(rf_target, rf_replacement)

with open(path_flota, "w") as f:
    f.write(text_flota)
print("Spec 006 updated")

# 2. Update Spec 008 (Operaris)
path_operaris = "sevalor_AgentV2/docs/sdd/specs/008-gestio-operaris.md"
with open(path_operaris, "r") as f:
    text_operaris = f.read()

rf_target_op = "### Requisitos Funcionales"
rf_replacement_op = """### Requisitos Funcionales

#### RF-00: Alta Automática de Operarios vía OCR (DNI/NIE)
- **QUÉ**: El sistema debe permitir el alta rápida de un trabajador simplemente escaneando o subiendo una imagen de su DNI o NIE.
- **PER QUÉ**: Para agilizar las contrataciones y asegurar que el Nombre, Apellidos, Fecha de Nacimiento y el Documento de Identidad (que funciona como credencial principal de acceso a la PWA) sean 100% precisos sin teclear.
- **CÓMO**: Se añade un botón "Alta Màgica OCR" en RRHH que procesa el documento de identidad mediante el modelo de visión, estructurando el JSON del trabajador y vinculando el archivo original de forma segura bajo encriptación RGPD."""

if rf_target_op in text_operaris:
    text_operaris = text_operaris.replace(rf_target_op, rf_replacement_op)

with open(path_operaris, "w") as f:
    f.write(text_operaris)
print("Spec 008 updated")
