# Pla d'Implementació — Workers de Fons, Motor de Facturació Veri*factu (ReportLab) i Processament Asíncron (Spec 024)

Aquest pla formalitza la implementació del sistema de **Workers de Fons, Motor de Facturació Veri*factu amb ReportLab i Processament Asíncron (Celery + Redis)** d'acord amb la **Spec 024**, la Constitució v4.0 de SEVALOR, la política innegociable de **Zero Mock Data** i la privacitat i sobirania Hetzner.

---

## 🎯 Objectius del Mòdul
1. **Arquitectura Modular de Cues Celery + Redis (`RF-01` a `RF-06`)**:
   - Cues especialitzades per prioritat:
     - `queue_documents`: Generació de PDFs pesats (ReportLab), càlcul d'hashing Veri*factu, compilat de caixetins i fitxes tècniques.
     - `queue_periodic`: Tasques cronometrades (Celery Beat), comprovacions d'expiració de sessions, purga de logs antics i renovació de certificats.
     - `queue_alerts`: Notificacions push d'alta prioritat, alertes SMS/Telegram per a incidents crítics o SOS 112.
   - Injecció obligatòria de context `empresa_id` en cada tasca per a respectar RLS a nivell de worker.
2. **Motor de Facturació Veri*factu amb ReportLab (`RF-07` a `RF-10`)**:
   - Generació determinista de factures PDF oficials amb codi QR tributari AEAT.
   - Algoritme de cadenes SHA-256 inalterables segons el RD 1007/2023 (`calcular_hash_verifactu`), incorporant empremta digital de la factura anterior.
3. **Outbox Pattern Asíncron per a l'AEAT (`RF-11` a `RF-15`)**:
   - Emmagatzematge a la carpeta outbox / taula d'esdeveniments en transacció atòmica junt amb la factura.
   - Despatx desacoblat cap als serveis web SOAP de l'Agència Tributària sense bloquejar el fil d'execució de l'usuari ni els terminals mòbils de camp.
4. **Política de Reintents Exponencials i Dead Letter Queue (`RF-19`, `RF-20`)**:
   - Reintents progressius (`2^intent * factor_segons`) davant de caigudes o manteniments dels servidors fiscals de l'AEAT.
   - Derivació a Dead Letter Queue (`dlq/`) després de superar el límit de reintents amb generació d'alerta d'auditoria.
5. **Còpia de Seguretat Dominical amb Exclusió de Bucle Recursiu (`RF-18`)**:
   - Script de backup setmanal automàtic executat per Celery Beat.
   - Clàusula de filtre rígid que **exclou incondicionalment** el directori de destí `/docs/<empresa_id>/backups/` i arxius `.zip`, blindant el disc Hetzner contra el col·lapse per auto-inclusió recursiva.
6. **Integració del Servei Whisper CPU-Only (`RF-16`, `RF-17`)**:
   - Delegació de transcripcions d'àudio de camp a tasques de fons amb priorització de CPU.

---

## 🛠️ Components i Canvis Tècnics
### 1. Nucli Celery (`backend/app/workers/celery_app.py` & `tasks.py`)
- Configuració de les 3 cues amb broker Redis (`redis://redis:6379/0`).
- Definició de tasques:
  - `generar_pdf_factura_task`
  - `despatx_outbox_aeat_task`
  - `executar_backup_setmanal_task`
  - `transcriure_audio_task`

### 2. Serveis de Negoci
- `backend/app/services/verifactu.py`: Càlcul de hash SHA-256, generació de payload QR i compilació de PDF ReportLab.
- `backend/app/services/outbox_aeat.py`: Processament per lots d'Outbox, reintents exponencials i derivació a DLQ.
- `backend/app/services/backup.py`: Generador de paquets ZIP sobirans amb exclusió de directoris recursius.
- `backend/app/services/whisper_service.py`: Enllaç asíncron amb el contenidor faster-whisper local INT8.

### 3. Suite de Proves QA
- Fitxer: `backend/tests/test_bloc5_workers.py` (proves unitàries de seguretat, ReportLab, backup, Outbox i Whisper).

---

## 🧪 Pla de Verificació
- Execució de `test_bloc5_workers.py` al contenidor Docker.
- Verificació que els backups no inclouen fitxers `.zip` previs.
- Verificació del retard exponencial d'Outbox i derivació a DLQ davant d'errors SOAP simulats.
