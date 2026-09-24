# INFORME EXECUTIU D'AUDITORIA: SEVALOR SUITE v4.0 (IMPLEMENTACIÓ I SEGURETAT)

**Data:** 09-Setembre-2026
**Àmbit:** Backend (FastAPI), Frontend (Next.js), Bot (Telegram) i Base de Dades (PostgreSQL)
**Objectiu:** Detectar contradiccions documentals, vulnerabilitats de seguretat, defectes estructurals i establir un pla d'esmena immediat.

---

## 1. VULNERACIONS CONSTITUCIONALS (CRÍTIC)

### 1.1 Falsificació de Tests Frontend (Violació "Zero Mock Data")
- **Troballa:** Els 12 fitxers de proves d'auditoria del Frontend (ex. `test_pwa_audit.mjs`, `test_bot_telegram_audit.mjs`) no proven el codi real de l'aplicació Next.js ni els serveis de bot reals. Només contenen funcions teòriques simulades hardcoded dins el mateix arxiu de test (Stubs) i en fan assertions (ex: es fa assert de funcions locals com `function validarWebhookSecret` al propi script). Aquests scripts no renderitzen components de React, ni comproven peticions de xarxa cap al backend.
- **Impacte:** CRÍTIC. Els 12 "passes" verds del frontend en realitat no verifiquen l'estabilitat del PWA en absolut. La documentació menteix en l'afirmació de "Testos QA Frontend Reals Passats".
- **Millora:** Eliminar immediatament tots els fitxers `test_*_audit.mjs` simulats. Substituir-los per una suite Playwright o Cypress per la interfície web i tests d'integració reals contra l'API.

### 1.2 Emmagatzematge d'Estat del Bot en Memòria (`_clients_vinculats`)
- **Troballa:** A `bot/main.py`, els tokens de deep-linking i les vinculacions de xat es guarden a les variables globals en diccionaris en memòria.
- **Impacte:** ALT. Si el microservei del bot es reinicia, o si hi ha més d'un Worker, l'estat es perd instantàniament i els usuaris no podran interaccionar amb ell, sent expulsats. Això xoca amb els requisits d'una plataforma multi-tenant escalable i amb dades persistents (Zero Mock Data).
- **Millora:** Eliminar els dict en memòria de Python i migrar l'estat de les vinculacions del bot de Telegram a Redis (ja que el servei redis ja està al contenidor docker) o directament a una taula de PostgreSQL `telegram_clients_vinculats`.

---

## 2. CONTRADICCIONS EN ARQUITECTURA I BD (ALT)

### 2.1 Desacoblament de valors DB CHECK vs Enum en Codi
- **Troballa:** A l'arxiu `db/migrations/001_core_multitenant.sql` els valors CHECK permesos per a `estat_pagament` són `('AL_DIA', 'DEUTOR', 'SUSPES')`. Tanmateix, a `api/v1/superadmin/tenants.py`, les API Pydantic fan referència als estats `TRIAL`, `ACTIU`, `SUSPES_PAGAMENT` o `BAIXA_OFFBOARDING` (amb un mapatge ambigu).
- **Impacte:** ALT. El fet de dependre d'un diccionari mapador per traduir els estats pot generar inconsistències importants a les dades o al retornar informació directament en crides GraphQL o serveis analítics com PostgREST.
- **Millora:** Normalitzar la base de dades eliminant el mapeig i actualitzar els ALTER CONSTRAINT del CHECK a PostgreSQL perquè coincideixin 1 a 1 amb les regles de negoci (afegint TRIAL, MANTENIMENT, BAIXA...).

### 2.2 Dependències Deprecades Crítiques (Code Smell)
- **Troballa:** Presència extensiva de `datetime.utcnow()` a tots els serveis (`bot/main.py`, `operari_auth.py`, `backup.py`, etc.).
- **Impacte:** MITJÀ. Risc de caiguda de microserveis per depreció en Python i possibles pèrdues de concordança a la BD sobre la data d'onboarding per Timezones.
- **Millora:** Substituir globalment per `datetime.now(timezone.utc)`.

---

## 3. AUDITORIA DE SEGURETAT VULNERABILITATS (CRÍTIC)

### 3.1 Hardcoded Secrets als Fitxers de Configuració i JWT
- **Troballa:** L'arxiu `.env` i `core/config.py` exposen credencials genèriques, incloent-hi el secret del JWT de forma explícita en el codi font (`SECRET_KEY=sevalor-dev-secret-key-32-chars-long-abc`). A més el middleware de Tenants comprova el JWT, si hi ha "SUPERADMIN", el sistema assigna automàticament bypass total a les RLS de Postgres a qualsevol usuari.
- **Impacte:** CRÍTIC. Amb l'exposició de la clau JWT, qualsevol persona pot signar un token amb el payload {"rol":"SUPERADMIN"}, bypassar els controls RLS (Row Level Security) del TenantMiddleware, i extreure informació financera completa o esborrar inquilins de producció.
- **Millora:** Eliminar el `.env` i injectar variables amb sistemes segurs (ex. Vault). Forçar una clau aleatòria generada via CLI en producció i rotació mandatoria a FastAPI de la Secret Key.

### 3.2 Vulnerabilitats de File Upload (Filtre Doble Extensió evadible)
- **Troballa:** A `bot/security.py`, la funció de seguretat `detectar_doble_extensio()` utilitza només Python String (`.split('.')`).
- **Impacte:** MITJÀ. És fàcilment evadible utilitzant "Null Byte Injection" en alguns sistemes i tampoc escaneja efectivament el contingut pel·ligrós en cas de payload modificat manualment (Magic bytes només es comproven parcialment). Un malware amb extensió `.jpg` falsa passaria.
- **Millora:** Reforçar les validacions amb la llibreria nativa `python-magic` real per comprovar completament els Magic Bytes i recomanació forta d'implementar escaneig antivirus.

---

## 4. PLA D'ACCIÓ I IMPLANTACIÓ AL CODI

**Prioritat P1 - Esmena Immediata (Abans de nou desenvolupament):**
- **Testos Frontend (Acció):** Executar `rm /media/akaun/Project_1/SEVALOR/pwa/test_*_audit.mjs`. Mantenir la cobertura neta instal·lant un directori real d'e2e tipus Cypress o Playwright per verificar els tests frontends reals, donat que actualment trenquen el principi de la constitució sobre "Zero Mock Data" al ser tot tests buits.
- **Codi Bot Persistent (Acció):** Actualitzar `bot/main.py` per substituir les variables `_clients_vinculats` i `_tokens_invitacio` per peticions asíncrones a un clúster Redis utilitzant la mateixa instància del docker-compose.
- **JWT (Acció):** Eliminar el default hardcoded a `core/config.py` substituint-ho per una excepció si falta al .env (`raise ValueError("JWT_SECRET_KEY missing")`).

**Prioritat P2 - Mantenibilitat (En 48 hores):**
- **Migració BD Estats (Acció):** Afegir `015_correcions_estats_db.sql` ampliant el camp CHECK per suportar 'TRIAL' i similars sense mapatges brossa en python.
- **Refactorització utcnow() (Acció):** Refactoritzar massivament la data mitjançant bash per canviar les expressions al codi al mètode `timezone.utc`.
