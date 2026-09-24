# Auditoria PWA SEVALOR — Informe de Conformitat

**Projecte:** SEVALOR /pwa  
**Revisió basada en:** `/media/akaun/Project_1/SEVALOR/sdd_sevalor/constitution.md` i especificacions **001**, **013-021** i **020**.  
**Àmbit:** Codi font `pwa/src`, configuració, tests i artefactes de build.  
**Data:** setembre 2026  
**Auditor:** Subagent Frontend/PWA  

---

## 1. Resum executiu

La PWA presenta una **arquitectura visual i funcional parcial**, però té **bretxes crítiques de seguretat, conformitat PWA, integració real i qualitat de dades**. Els mòduls criptogràfic (`crypto.ts`), geovalla (`geo.ts`) i antifraude de càmera (`media.ts`) estan **implementats com a primitives aïllades**, però **no s’utilitzen** en els fluxos d’autenticació ni de persistència. L’aplicació conté **dades mock o hardcoded** a moltes pàgines, anant en contra del principi de *Zero Mock Data* de la Constitució. **No hi ha `manifest.json`, Service Worker/Workbox, `next.config.js`, ni cap artefacte PWA**. Els fetchers apunten tots a `http://127.0.0.1:8001`, sense cap mecanisme de tenant isolation per headers ni variables d’entorn.

El build (`npm run build`) tècnicament finalitza correctament, però genera output SSR de Next.js (`.next/`), no un bundle estàtic exportable com a PWA. `npm run lint` falla per falta de configuració ESLint.

---

## 2. Mètode i artefactes revisats

Revisats 26+ rutes App Router, `src/lib/*`, `package.json`, `tsconfig.json`, `tailwind.config.js`, `postcss.config.js`, `globals.css`, tests `test_crypto.mjs` i `test_pwa_logic.mjs`, i execució de `npm run build`, `npm run lint`, `npm test` i `node test_pwa_logic.mjs`.

| Categoria | Resultat global |
|-----------|-----------------|
| PWA / Service Worker | **Falta tot** |
| Seguretat offline (AES-GCM-256 + sentinel) | **Implementat però no integrat** |
| Zero Mock Data / hardcoded data | **Incompliment generalitzat** |
| Chameleon UI (HSL dinàmic per tenant) | **Parcial: tokens hardcoded i marca fixa** |
| Integració backend / tenant isolation | **Inexistent** |
| Qualitat de build / lint | **Build OK però no estàtic; lint no configurat** |
| Camera antifraude + geovalla | **Lògica correcta, poc o gens usada en fluxos reals** |

---

## 3. Matriu d’hallazgos per severitat

### 3.1 Crítica

| ID | Fitxer / Ubicació | Descripció | Impacte | Recomanació |
|----|-------------------|------------|---------|--------------|
| **C-01** | Tot el projecte: no existeix `public/manifest.json`, `src/app/sw.ts`, `public/sw.js`, `workbox-*`, `next.config.js` | La Constitució i les specs exigeixen PWA offline-first amb Workbox/Service Worker i manifest. El projecte no en té cap. | No és PWA; no hi ha instal·lació, offline-first ni background sync; fallaria qualsevol auditoria PWA/Lighthouse. | Afegir `next-pwa` o Workbox injection, crear `public/manifest.json` i el Service Worker amb cues de background sync. Configurar `next.config.js` amb `output: 'export'` i `distDir: 'dist'`. |
| **C-02** | `src/app/operari/login/page.tsx:70-97` | Login amb PIN via `fetch` a `127.0.0.1:8001`, NIF hardcoded `12345678Z` i fallback `PIN === "1234"` que sempre redirigeix a `/operari/feines`. | Accés universal amb PIN 1234; cap de seguretat real; viola Spec 019 RF-05/RF-06 i el mandat de zero tokens en text pla. | Implementar `verifySentinelBlock` amb `SENTINEL_PLAINTEXT`; xifrar JWT amb `encryptWithPin`; guardar solament ciphertext+salt+IV a IndexedDB; eliminar fallbacks hardcoded. |
| **C-03** | `src/lib/crypto.ts` implementat però **no importat** a cap pàgina de login/sessió; `src/lib/db.ts` no té taula per a token xifrat ni sentinel | Tot el model de seguretat offline-first AES-GCM-256 + PBKDF2 100k resta mort. | Tokens quedarien en text pla o directament sense persistir; autenticació operari és purament cosmètica. | Crear taula `auth_meta` a Dexie amb `sentinel_iv`, `sentinel_cipher`, `token_cipher`, `salt`; usar `createSentinelBlock`/`verifySentinelBlock` al login i a l’obertura de sessió. |

### 3.2 Alta

| ID | Fitxer / Ubicació | Descripció | Impacte | Recomanació |
|----|-------------------|------------|---------|--------------|
| **A-01** | `src/app/operari/feines/page.tsx:50-62`, `src/app/operari/material/page.tsx:42-73`, `src/app/operari/planols/page.tsx:26-43`, `src/app/operari/vehicles/page.tsx:101-150` | Cada mòdul operari inclou un botó/funció “Carregar … Demo” que injecta dades fictícies (OT-2026-0089, materials, vehicles, planols). | Incompliment flagrant del mandat *Zero Mock Data* de la Constitució i especificacions 013-017/015/018. | Suprimir funcions demo i carregar estats buits legítims; els botons han d’obrir llista real des del backend/IndexedDB. |
| **A-02** | `src/app/gestio/layout.tsx:58-71`, `src/app/gestio/mapa/page.tsx:55-67`, `src/app/gestio/mapa/page.tsx:327-363`, `src/app/gestio/copilot/page.tsx:44-124`, `src/app/gestio/configuracio/page.tsx:95-179`, `src/app/superadmin/telemetria/page.tsx:67-99` | Dades hardcoded als arrays de Spotlight, mapa, Copilot, usuaris, slots de jornada, microserveis i telemetria. | La interfície gestió presenta informació inventada com a real; distorsiona auditoria i proves; fomenta *data drift*. | Moure aquestes dades a fetchers reals o, si cal mostrar “exemples”, marcar-los explícitament com a placeholders governats per feature flag desactivat en producció. |
| **A-03** | Backend URL hardcoded a `http://127.0.0.1:8001/api/v1/...` en `operari/login`, `gestio/proveidors`, `gestio/flota`, `gestio/operaris`, `superadmin/telemetria` | Cap abstracció d’API, cap variable d’entorn, cap tenant header (`x-tenant-id`, `x-empresa-id`). | No desplegable en cap entorn real; impossible aïllar tenants (RLS); viola requisits de multi-tenant SaaS. | Crear `src/lib/api.ts` amb base URL `process.env.NEXT_PUBLIC_API_URL`, interceptor que llegeixi subdomini/empresa_id i afegeixi headers; usar Proxy durant dev. |
| **A-04** | `src/app/layout.tsx:15`, `src/app/globals.css:7-20`, `src/app/gestio/layout.tsx:243-245` | `themeColor` hardcoded `#15803d`, CSS tokens HSL amb valors fixos, sidebar amb “SEVALOR Enginyeria Civil SL / CIF B-67291043” hardcoded. | No es compleix el requisit Chameleon UI per tenant; la marca primària no és dinàmica. | Implementar API `/config/brand` que retorni HSL i logo; injectar CSS variables via `<style>`/root config; fer que `themeColor` variï segons tenant. |
| **A-05** | `src/app/gestio/mapa/page.tsx:84-86` | Fons de mapa amb imatges remotes d’Unsplash i vectors SVG hardcoded com a “dades GIS”. | Contingut extern no controlat, possible violació GDPR i manca de dades reals SIGPAC/cadastre/cartografia propietària. | Substituir per tiles/capa WMS pròpia o pública amb llicència compatible; els vectors han de venir del backend. |

### 3.3 Mitjana

| ID | Fitxer / Ubicació | Descripció | Impacte | Recomanació |
|----|-------------------|------------|---------|--------------|
| **M-01** | `src/app/gestio/configuracio/page.tsx` | Paleta IA hardcoded; prompt simulat amb `setTimeout`; tokens Telegram hardcoded. | Funcionalitat “ADN de Marca” és una simulació sense integració real d’IA ni emmagatzematge segur. | Implementar endpoint real d’anàlisi de marca; separar secrets a variables d’entorn backend. |
| **M-02** | `src/app/operari/login/page.tsx:196-202`, `src/app/operari/vehicles/page.tsx:179-180` | Alerta d'”SMS al supervisor” i càlcul d’odòmetre amb `+ 87` hardcoded. | Fluxos no reals; l’SMS no es pot enviar des del client; el càlcul d’odòmetre hauria de venir d’OCR real o backend. | Substituir alertes per forms/flows reals; integrar OCR/extracció del blob de la fotografia. |
| **M-03** | `src/lib/db.ts` | `SyncQueueItem.payload: any` i BLOB/STRING poc tipats (`Blob \| string`). | Trenca estrictesa TypeScript, pot generar inconsistències en sincronització offline. | Tipatge estricte de `payload` per acció (union discriminant) i forçar `Blob` + metadades. |
| **M-04** | `src/app/gestio/notificacions/page.tsx:327` | Token d’invitació generat amb `Math.random().toString(36)` i URL hardcoded al bot de Telegram. | Generació de token criptogràficament feble; URL externa no configurable. | Usar `crypto.getRandomValues` codificat base64url; que l’URL del bot vingui de configuració backend. |

### 3.4 Baixa

| ID | Fitxer / Ubicació | Descripció | Impacte | Recomanació |
|----|-------------------|------------|---------|--------------|
| **B-01** | `package.json:9` `"lint": "next lint"` | No hi ha `.eslintrc` ni dependencies ESLint; `npm run lint` interromp el procés. | Qualitat de codi no automatitzable; risc d’errors silenciosos. | Afegir `eslint-config-next` i `.eslintrc.json` o desactivar script si no s’usa. |
| **B-02** | `src/lib/gestio-context.tsx`, `operari/layout.tsx`, `operari/login/page.tsx`, `superadmin/layout.tsx`, `superadmin/tenants/onboarding/page.tsx` | Lògica de tema duplicada en múltiples components i ús de `localStorage` per preferències. | Inconsistència visual i deute tècnic. | Centralitzar tema a `GestioProvider` i aplicar a tots els layouts; `localStorage` només per preferència de tema és acceptable però no per a tokens. |
| **B-03** | Noms de capes/classes (`bg-grid-pattern`, `animate-fade-in`) | Classes Tailwind personalitzades no definides a cap lloc visible. | Risc de classes sense efecte si no hi ha plugin/custom CSS. | Revisar i afegir definicions a `@layer components` o substituir per utilitats Tailwind. |

---

## 4. Estat de les proves executades

| Prova | Comanda | Resultat | Observació |
|-------|---------|----------|------------|
| Test criptogràfic | `npm test` | ✅ Passa | Verifica primitives PBKDF2 + AES-GCM-256 + sentinel; no garanteix integració. |
| Test lògica PWA | `node test_pwa_logic.mjs` | ✅ Passa | Verifica geovalla i atributs de càmera; no cobreix fluxos d’usuari. |
| Build Next.js | `npm run build` | ✅ Finalitza | Genera `.next/` SSR; **no** produeix export estàtic per PWA. |
| Lint | `npm run lint` | ❌ Falla | Falta configuració ESLint; el CLI demana setup interactiu. |

---

## 5. Verificació específica per specs

### Spec 001 (Dashboard / Gestió)
- **Respecta parcialment** la interfície de capes i rol ENGINYER (veto financer).
- **Falta**: dades reals, RTK real, tiles GIS propis, marca dinàmica, backend vinculat.

### Specs 013-017 / 019 / 020 / 015 / 018 (Operari)
- **UI existent** per feines, material, planols, vehicles, tiquets, incidències i login.
- **Falta**: integració real amb backend, zero mock data, login segur, Offline-First amb Workbox, geofence/gestió de Punto Cero, cua sync real.

### Spec 020 (Càmera antifraude)
- `CAMERA_LIVE_INPUT_PROPS` i `compressImageToWebP` implementats correctament.
- **Millorable**: afegir validació EXIF origen càmera i watermark de timestamp/GPS; assegurar WebP < 1 MB.

---

## 6. Riscos prioritaris

1. **Risc de seguretat crític:** accés sense autenticació real (PIN 1234) i tokens no xifrats.
2. **Risc PWA/Producte:** lliurament no és PWA; el client no podrà usar-lo offline ni instal·lar-lo.
3. **Risc qualitatiu:** dades mock hardcoded poden arribar a producció si no se’n fa una neteja estricta.
4. **Risc operatiu:** URLs backend hardcoded impedeixen desplegament multi-entorn i multi-tenant.

---

## 7. Recomanacions immediates en ordre de prioritat

1. **Crear `next.config.js`** amb `withPWA`, `output: 'export'`, `distDir: 'dist'` i el manifest generat.
2. **Integrar `crypto.ts` realment** al login: crear sentinel al primer desbloqueig, verificar a cada inici, i guardar JWT xifrat a IndexedDB.
3. **Eliminar totes les funcions `*Demo`** i substituir-les per fetchers que llegeixin del backend o d’IndexedDB.
4. **Centralitzar la API base URL** i tenant headers a `src/lib/api.ts` Configurar variables d’entorn.
5. **Implementar Workbox/Service Worker** amb background sync per les cues `sync_queue` i offline-first d’ordres/tiquets.
6. **Aplicar Chameleon UI real**: endpoint de marca tenant → CSS variables dinàmiques.
7. **Configurar ESLint** perquè `npm run lint` passi sense interacció.
8. **Establir una “producció data contract”**: cap array hardcoded pot aparèixer en builds de release.

---

## 8. Conclusió

La PWA té **elaborada UI i una base de primitives correctes** (crypto, geovalla, càmera), però no compleix els requisits constitucionals ni de specs en els aspectes **PWA, seguretat offline, Zero Mock Data i multi-tenant backend**. És necessària una **refactorització important** abans de considerar-la viable per a desplegament. El present informe és només auditiu i no modifica cap fitxer.

---
*Fi de l’informe.*
