# Walkthrough — Flota i Manteniment ITV (/gestio/flota — Spec 006)

Aquest document resumeix la implementació del mòdul de **Gestió de Flota i Parc Mòbil** (`/gestio/flota`) d'acord amb la **Spec 006**, la Constitució v4.0 de SEVALOR, suport complet per a **Mode Clar i Mode Fosc**, **Zero Mock Data** i verificació amb bateries de proves automatitzades.

---

### E. Flota i Manteniment ITV (`/gestio/flota` — Spec 006)
- **Taula de Flota d'Alta Densitat amb les 8 Columnes Essencials (RF-01)**:
  - Identificador / Matrícula.
  - Tipologia i Distintiu Ambiental DGT oficial (0, ECO, C, B, Sense Distintiu) inmutable.
  - Marca, Model i Versió.
  - Règim d'Adquisició (Propietat, Rènting/Leasing, Sustitució) amb barres de progrés i alertes deterministes al **90%**, **95%** i **100%** de límit contractual (RF-29).
  - Custodi / Conductor Habitual assignat.
  - Mètrica d'Ús Acumulada (km d'odòmetre o h d'horòmetre sota historial únic continu, o N/A en remolcs).
  - Estat Operatiu amb 7 estats canònics (Operatiu, Operatiu DL, En Ruta, En Taller, Incidència, Retirat ITV, Baixa).
  - Estat Legal, ITV i Consum.
- **Resolució d'ITV en 4 Veredictes (RF-18)**:
  - **Favorable Neta**: Vehicle recupera l'estat `OPERATIU` [Verd].
  - **Favorable amb Defectes Lleus (DL)**: Vehicle passa a `LEVE` [Verd Clar / Lima], es manté 100% operatiu per llei i els defectes es traslladen a manteniment preventiu.
  - **Desfavorable**: Vehicle passa a `DESFAVORABLE` [Vermell Fosc], queda immobilitzat, s'obre la finestra de 2 mesos de termini de subsanació (amb alerta crítica al dia 61 de proposta de baixa DGT) i es genera automàticament una Ordre de Treball (OT) interna a taller.
  - **Negativa**: Vehicle passa a `INACTIVAT` [Vermell Fosc], immobilització total amb avís obligatori de transport en grua al taller.
- **Anàlisi de Consum Real i Desglossament d'AdBlue (RF-16)**:
  - Càlcul $\text{L/100km} = \frac{\text{Litres}}{\Delta\text{Km}} \times 100$.
  - Desglossament independent d'AdBlue en dièsel (purament informatiu).
  - Alerta d'anomalia si el consum supera en més d'un 10% la mitjana consolidada (>30 dies).
  - **Botó de descarte manual tipificat** (Càrrega pesada/remolc, Climatologia adversa, Ruta de muntanya, Fuga mecànica revisada, Altres justificats).
- **Zero Mock Data (Dia 0)**: Estat buit canònic: *"No hi ha vehicles registrats a la flota"*, cercador deshabilitat i botó d'alta.

---



---

## 🧪 Validació i Proves d'Auditoria QA

S'ha executat amb èxit el protocol de verificació de Flota i ITV:
```bash
node pwa/test_flota_audit.mjs
```
- **8/8 comprovacions aprovades al 100%**:
  1. Identificadors de vehicle, matrícula, marca i model.
  2. Llindars de rènting 90%, 95% i 100% amb canvi dinàmic de severitat.
  3. Càlcul precís de consum mitjà (l/100km).
  4. Els 4 veredictes canònics d'ITV (FAVORABLE, FAVORABLE_AMB_DEFECTES_LLEUS, DESFAVORABLE, NEGATIVA).
  5. Bloqueig operatiu automàtic per a vehicles amb ITV caducada o negativa.
  6. Custòdia d'operari assignat i traçabilitat de quilometratge.
