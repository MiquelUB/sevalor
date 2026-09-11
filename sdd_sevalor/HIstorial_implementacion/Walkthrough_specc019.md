# Walkthrough d'Auditoria i Verificació — PWA: Accés i Seguretat Offline PIN (/operari/login — Spec 019)

Aquest document certifica la implementació i auditories criptogràfiques del mòdul **PWA Accés i Seguretat Offline PIN** d'acord amb la **Spec 019**.

---

## 🎯 Proves i Regles de Negoci Verificades
1. **Autenticació PIN de 4 Dígits (`RF-01` a `RF-05`)**:
   - Verificat el teclat tàctil industrial i la validació de credencials ràpida.
2. **Criptografia Offline AES-GCM 256 bits (`RF-11` a `RF-16`)**:
   - Verificat mitjançant `node pwa/test_crypto.mjs`:
     - Derivació PBKDF2 correcta des del PIN.
     - Xifratge i desxifratge transparent de la base de dades local IndexedDB.
     - Rebuig atòmic i protecció de dades davant d'un PIN incorrecte.
3. **Bloqueig de Seguretat al 4t Intent Fallit (`RF-17` a `RF-20`)**:
   - Comprovada la immobilització del login i el requeriment de restabliment per l'administrador.
4. **Revocació Atòmica de Sessions**:
   - Verificada la invalidació immediata de sessions a Redis davant de baixes d'operaris.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite Cripto Offline**: `node pwa/test_crypto.mjs` (Tots els vectors de prova superats).
- **Suite PWA QA**: `node pwa/test_pwa_audit.mjs` (Login i PIN 100% en verd).
