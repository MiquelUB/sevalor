# Walkthrough — Magatzem Central & Inventari Continu (/gestio/magatzem — Spec 004)

Aquest document resumeix la implementació del mòdul de **Magatzem Central & Inventari Industrial** (`/gestio/magatzem`) d'acord amb la **Spec 004** de SEVALOR.

---

### D. Magatzem Central & Inventari Industrial (`/gestio/magatzem`)
*Basada en Stitch Screen `cec82abe4bcc4391a374e57d34f53f8b` i Spec 004.*
- **Inventari Multilocació**: Taula comparativa de l'estoc físic a la Nau Central vs Furgonetes Taller (Vehicle 7482-LDK).
- **Format Continu i Retalls**: Comptabilització de retalls aprofitables (m) per evitar talls innecessaris de barres de 6 metres.
- **Reserva Pesimista**: Càlcul atòmic de $\text{Disponible Net} = \text{Estoc Físic} - \text{Estoc Reservat en OTs}$.
- **Zero Mock Data**: Estat buit canònic: *"Magatzem central sense moviments d'estoc"*.

---

---

## 🧪 Validació i Proves d'Auditoria QA

```bash
node pwa/test_gestio_audit.mjs
```
- Verificació de taula d'alta densitat d'articles, estocs mínims, punts de comanda i valoració d'inventari continu.
