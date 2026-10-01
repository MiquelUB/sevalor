# Sevalor Suite — Constitució del Projecte (v4.0)

> **Lema Fundacional:** *"Invisible per al treballador, omniscient per a l'enginyer."*

---

## 1. Context: Què és Sevalor Suite?

**Sevalor Suite** (plataforma multi-vertical: *CampoPro*, *ElectricPro*, *HydroPro*, *BuildingPro*, *ClimaPro*) és un sistema B2B integral dissenyat per a **empreses d'instal·lacions, manteniment i serveis tècnics amb quadrilles al terreny (5–50 treballadors)**.

Connecta en temps real **4 actors clau**:
1. **Operari en Camp (`/operari`)**: PWA mòbil ultraràpida, 100% offline-first, governada pel "Flux dels 30 segons" (fitxatge, fotos geolocalitzades, picking de material, quilometratge i reportatge per veu).
2. **Enginyer / Oficina Tècnica (`/gestio`)**: Dashboard web per planificar obres, versionar plànols tècnics, controlar estoc, auditar garanties, elaborar pressupostos i gestionar feines. L'emissió de factures legals i l'accés a comptabilitat queden reservats a Secretaria i Boss.
3. **Client Final (Canal Telegram Bot)**: Sense instal·lar aplicacions, rep notificacions d'arribada, aprova pressupostos amb 1 clic, signa conformitat digital i valida lliuraments.
4. **Superadmin (`/superadmin`)**: Centre de comandament per al propietari del SaaS: onboarding d'empreses, marca camaleònica, llicències, telemetria i sobirania de dades.

---

## 2. Principis Innegociables

### I. Tolerància Zero a Dades Fictícies (Zero Mock Data)
Queda terminantment prohibit introduir dades simulades, registres hardcodejats o mocks en cap part del codi o interfície. Tota la UI mostra estats buits reals (*"Sense dades disponibles"*). Cap funcionalitat es dona per completada si depèn de dades falses.

### II. Alta Màgica OCR (Zero Data Entry)
Tota entitat (vehicles, operaris, albarans, factures, contractes, clients, proveïdors) es dona d'alta mitjançant l'anàlisi OCR de fotografies o PDFs. L'assistent extreu dades estructurades i presenta un esborrany per a validació humana.

### III. Offline-First Criptogràfic (Web Crypto API)
La PWA garanteix persistència local a IndexedDB i sincronització amb Workbox. Tokens xifrats localment amb AES-GCM 256 bits derivats del PIN de l'operari. Prohibit guardar JWT en text pla.

### IV. Pressupost HITL (Human-in-the-Loop)
El cicle comercial complet és: **Pressupost Acceptat → Fulla de Treball → Incidències → Pre-factura → Factura Veri*factu**. Cap factura es genera sense validació humana prèvia del full de tasca. El formulari d'OT ofereix tres opcions: Generar Tasca, Generar Pressupost, o Pressupost Intel·ligent (Copilot).

### V. Copilot IA Local amb Aprenentatge Progressiu
El Copilot és IA local (LM Studio / Ollama) amb aïllament de domini per vertical. Aprèn progressivament de l'historial de l'empresa (preus, mermes, durades, marges). Mai pren decisions financeres autònomament.

### VI. Barrera Econòmica del Copilot (Doble Capa)
Les dades econòmiques (marges, EBITDA, nòmines, barema de preus) estan restringides exclusivament al rol Boss mitjançant:
- **Capa 1 (Soft)**: Classificador IA que filtra preguntes econòmiques per rol.
- **Capa 2 (Hard)**: RLS PostgreSQL amb policy `economics_boss_only` que retorna 0 rows si el rol no és Boss. Infranquejable.

### VII. Facturació Immutable i Legal (Veri*factu RD 1007/2023)
Tot PDF emès inclou codi QR tributari i encadenament immutable SHA-256. Conservació local segura i inalterable.

### VIII. Disseny Camaleònic (Chameleon UI Engine)
Cada empresa configura logotip i colors de marca (configurat per Superadmin en l'onboarding). El sistema injecta tokens CSS HSL transformant la PWA, Dashboard, PDFs i Telegram.

### IX. Arquitectura Asíncrona i Emmagatzematge Sobirà
- FastAPI asíncron (asyncpg). Cap endpoint bloqueja l'event loop.
- Tasques pesades delegades a Celery + Redis.
- Emmagatzematge exclusivament a Hetzner (UE). Zero dependència d'AWS S3.

### X. Governança SDD (Spec-Driven Development) i Tests Nets
Cap línia de codi es produeix sense seguir: **Constitució → Spec (EARS) → Clarificació → Pla d'Arquitectura (`plan.md`) → Tasques Atòmiques (`tasks.md`) → Validació Neta de Tests (100% en verd, zero falsos positius i RLS certificat)**. Si el codi contradiu l'especificació o la constitució, aquestes sempre prevalen.

---

## 3. Governança

- Aquesta Constitució preval sobre qualsevol altra pràctica.
- Les esmenes requereixen documentació, aprovació del Founder i pla de migració.
- Totes les PRs han de verificar el compliment d'aquests principis.

**Versió**: 4.0 | **Ratificada**: 2026-09-30 | **Última esmena**: 2026-09-30
