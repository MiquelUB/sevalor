# Walkthrough d'Auditoria i Verificació — Workers de Fons, Motor Veri*factu i Processament Asíncron (Spec 024)

Aquest document certifica la implementació, proves de resiliència i auditories de conformitat del sistema de **Workers de Fons, Motor de Facturació Veri*factu (ReportLab) i Processament Asíncron (Celery + Redis)** d'acord amb la **Spec 024**.

---

## 🎯 Proves i Regles de Negoci Verificades

### 1. Inalterabilitat Veri*factu i Generació ReportLab (`RF-07` a `RF-10`)
- Verificat mitjançant `TestVerifactu.test_calcul_hash_determinista`:
  - El càlcul d'empremta SHA-256 sobre els camps obligatoris és 100% determinista i produeix una cadena hexadecimal de 64 caràcters exacta.
- Verificat mitjançant `TestVerifactu.test_encadenament_hash_canvia_resultat`:
  - La inclusió del hash de la factura anterior altera de manera unívoca el hash resultant, garantint la traçabilitat i no alteració de la sèrie comptable.
- Verificat mitjançant `TestVerifactu.test_generacio_pdf_factura_amb_qr`:
  - Generació del document PDF oficial mitjançant ReportLab amb el codi QR fiscal i els detalls de la transacció desats directament al disc local sobirà.

### 2. Còpia de Seguretat Dominical i Exclusió de Bucle Recursiu (`RF-18`)
- Verificat mitjançant `TestBackupTenant.test_backup_exclou_carpeta_backups_i_zips`:
  - L'empaquetador ZIP recorre tots els documents i factures de l'arrendatari.
  - La regla d'exclusió descarta activament qualsevol fitxer dins de `backups/` o amb extensió `.zip`, prevenint de forma demostrada la saturació exponencial de disc a Hetzner Falkenstein.

### 3. Outbox Pattern per a SOAP AEAT i Reintents Exponencials (`RF-11` a `RF-15`, `RF-19`, `RF-20`)
- Verificat mitjançant `TestOutboxAEAT.test_reintent_exponencial`:
  - La funció de càlcul de retard aplica estrictament la fórmula \(2^{\text{intent}} \times \text{factor}\) (2s, 4s, 8s, 16s, 32s).
- Verificat mitjançant `TestOutboxAEAT.test_despatx_outbox_correcte`:
  - Els fitxers situats a la bústia de sortida (`outbox/`) es processen i, un cop confirmats pel servei SOAP, es desplacen automàticament a `enviats/`.
- Verificat mitjançant `TestOutboxAEAT.test_despatx_outbox_rebuig_deriva_a_dlq`:
  - Quan el servidor respon amb error no recuperable o s'exhaureixen els reintents, el fitxer es transfereix a la cua de fallades (`dlq/`) per a la revisió humana de l'administració.

### 4. Transcripció d'Àudios de Camp faster-whisper CPU INT8 (`RF-16`, `RF-17`)
- Verificat mitjançant `TestWhisperAudio.test_transcripcio_amb_fitxer_temporal`:
  - Enllaç de petició asíncrona contra el contenidor local `faster-whisper-server:latest-cpu`, completant el processament en menys de 8 segons sense consum de targeta gràfica externa.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite Backend Unit & Integration Tests**:
  - Fitxer: `backend/tests/test_bloc5_workers.py`
  - 13/13 proves superades (100% OK).
- **Integració Global**:
  - Execució de tota la suite de backend (`run_tests.py`): 87/87 proves superades (100% OK).
