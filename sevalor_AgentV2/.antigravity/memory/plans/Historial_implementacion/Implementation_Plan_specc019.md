# Pla d'Implementació — PWA: Accés, Seguretat Offline i Login PIN (/operari/login — Spec 019)

Aquest pla formalitza la implementació del sistema d'**Autenticació Tàctil per PIN de 4 Dígits, Enrolament per SMS OTP i Xifratge Offline AES-GCM** d'acord amb la **Spec 019**, la Constitució v4.0 de SEVALOR i la sobirania de dades.

---

## 🎯 Objectius del Mòdul
1. **Teclat Numèric Tàctil de Gran Format (`RF-01` a `RF-05`)**:
   - Botons de grans dimensions (>50px) optimitzats per a treballadors amb guants o pantalla humida.
   - Introducció de PIN de 4 dígits sense teclat virtual estàndard del sistema per a màxima rapidesa.
2. **Enrolament Inicial del Terminal per SMS OTP (`RF-06` a `RF-10`)**:
   - Verificació del número de telèfon corporatiu del treballador mitjançant codi SMS d'un sol ús.
   - Enllaç criptogràfic del dispositiu a l'arrendatari de l'empresa.
3. **Desbloqueig d'IndexedDB Xifrat amb Clau Derivada PBKDF2 (`RF-11` a `RF-16`)**:
   - Protecció de la base de dades local en repòs mitjançant algoritme AES-GCM de 256 bits.
   - Clau de desxifrat derivada del PIN numèric mitjançant PBKDF2 (100.000 iteracions) validada contra un bloc sentinella.
   - Permet l'accés complet i segur en zones blanques sense cobertura mòbil.
4. **Bloqueig per Intents Fallits & Revocació de Sessions (`RF-17` a `RF-20`)**:
   - Bloqueig temporal del compte després de 4 intents consecutius de PIN incorrecte.
   - Revocació immediata de tokens JWT a Redis des del panell d'oficina en cas de pèrdua o robatori del terminal.
5. **Zero Mock Data & Mode Fosc (`RF-21` a `RF-24`)**:
   - Pantalla de login neta amb identificació de la marca camaleònica de l'arrendatari.

---

## 🛠️ Components Tècnics
- **Frontend PWA**: `pwa/src/app/operari/login/page.tsx`
- **Mòdul Criptogràfic**: Web Crypto API natiu (PBKDF2 + AES-GCM 256 bits).
- **Auditoria QA**: `pwa/test_crypto.mjs` i `test_pwa_audit.mjs`
