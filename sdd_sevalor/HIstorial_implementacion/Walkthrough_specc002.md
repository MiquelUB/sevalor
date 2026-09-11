# Walkthrough — Portal de Clients i Finques Rústiques (/gestio/clients — Spec 002)

Aquest document resumeix la implementació del mòdul de **Clients i Finques Rústiques** (`/gestio/clients`) d'acord amb la **Spec 002** de SEVALOR.

---

### C. Portal de Clients i Finques (`/gestio/clients`)
*Basada en Stitch Screen `4f8ba28a47ae413691f78f5458610c94` i Spec 002.*
- **Directori de Clients**: Codificació canònica `CLI-XXXX`, dades fiscals, NIF complet i canal Telegram de clients.
- **Dades Bancàries Segures**: Xifratge simètric AES-256 amb visualització emmascarada de l'IBAN (`ES82 •••• •••• •••• 4819`).
- **Inspecció de Finques**: Coordenades GPS en brut (WGS84) i claus de candats rústics.
- **Zero Mock Data**: Estat buit canònic: *"No hi ha clients registrats al directori"*.

---

---

## 🧪 Validació i Proves d'Auditoria QA

```bash
node pwa/test_gestio_audit.mjs
```
- Verificació del directori de clients, finques associades, codis correlatius `CLI-XXXX` i estat buit canònic.
