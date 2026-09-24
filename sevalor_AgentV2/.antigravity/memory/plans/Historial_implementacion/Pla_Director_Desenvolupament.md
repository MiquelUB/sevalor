# Pla Director de Desenvolupament (Zero Mock & SDD)

Aquest document estableix el full de ruta arquitectònic real per reconstruir el backend i la PWA de **CampoPro (Sevalor Suite)**. L'estratègia es basa en la resolució de dependències (no pots crear una feina sense un client, no pots fitxar sense un operari), garantint que cada fase s'assenti sobre una base de dades PostgreSQL blindada per RLS (Row-Level Security).

## Regles d'Or (Controls d'Acceptació Obligatoris)
1. **Zero Mocks**: Cap dada serà hardcodejada ('AL_DIA', 'STARTER' inventats). Totes les proves inseriran dades reals mitjançant els propis models de BD o l'API.
2. **PostgreSQL RLS Strict**: Cada *endpoint* nou serà testejat amb dos *tenants* simultanis. Si el Tenant A pot veure dades del Tenant B, l'especificació es rebutja automàticament.
3. **100% Coverage Reial**: No s'avançarà de fase si el `pytest` retorna un sol *warning* o error d'integració.

---

## FASE 1: Nucli i Seguretat (Completada i Blindada ✅)
*S'ha demostrat que la base del sistema rebutja atacs i aïlla les empreses.*
- **Spec 021 (Superadmin & Tenants)**: Alta d'empreses, generació de subdominis i RLS. *(Superat)*
- **Spec 012 (Middleware Seguretat)**: Injecció del `empresa_id`, generació de claus, i tallafocs JWT. *(Superat)*
- **Spec 023 (Telegram Bot)**: FSM amb Redis, Rate Limiting i protecció de *Magic Bytes* (MIME). *(Superat)*

---

## FASE 2: Recursos Humans i Autenticació (En Procés ⏳)
*Sense personal no hi ha operativitat.*
- **Spec 008 (Gestió d'Operaris)**: Alta, bloquejos, rols i gestió de PINs via Hash Bcrypt. *(90% Superat, validat RLS avui)*
- **Spec 019 (Login d'Operari PWA)**: Intercanvi de NIF + PIN numèric per tokens JWT asíncrons. Prevenció d'atacs de força bruta. *(Immediatament Següent)*
- **Spec 011 (Configuració i Slots)**: Definició d'horaris laborals base, IVA per defecte, configuracions globals per empresa.

---

## FASE 3: Entitats Mestres (Base de Dades)
*Directori d'elements que formaran els pressupostos i ordres de treball.*
- **Spec 002 (Gestió de Clients)**: Fitxes de clients, dades de facturació, condicions de pagament.
- **Spec 003 (Proveïdors)**: Base de dades de subministraments.
- **Spec 006 (Flota de Vehicles)**: Matrícules, ITV, assignació a operaris.
- **Spec 004 (Magatzem i Estoc)**: Articles, codis QR/Barris, alertes d'estoc mínim (Depèn de Proveïdors).

---

## FASE 4: Operacions d'Oficina (Backoffice)
*El nucli de la gestió diària del "Boss" i els Enginyers.*
- **Spec 005 (Ordres de Treball i Mapa)**: Creació de feines, assignació de colles (Depèn de Clients i Operaris).
- **Spec 010 (Gestió de Plànols)**: Pujada de CAD/PDFs massius associats a les Feines (Depèn de Spec 005).

---

## FASE 5: Operacions de Camp (Lògica PWA Mobile)
*Els endpoints altament concurrents on els operaris reporten l'activitat.*
- **Spec 013 (Sincronització de Feines)**: Enviament de dades al mòbil, fitxatges i temps.
- **Spec 014 (Consum de Material)**: Descomptar estoc del magatzem des de l'obra.
- **Spec 015 & 016 (Vehicles i Incidències)**: Report de danys, consum de gasolina i avaries estructurals.
- **Spec 017 & 020 (Visor Plànols i Càmera)**: Consulta d'esquemes i pujada massiva de fotografies amb metadades i marca d'aigua temporal per evidències.
- **Spec 018 (Tiquets de Despeses)**: Càrrega de tiquets OCR per dietes o gasolina.

---

## FASE 6: Tancament, Finances i Intel·ligència
*Liquidació econòmica i processos en segon pla.*
- **Spec 007 (Comptabilitat i Facturació)**: Tancament de feines, emissió de factures, aplicació de retencions (Depèn de 005 i 014).
- **Spec 009 (Notificacions Push)**: Avisos als supervisors sobre canvis d'estat crítics.
- **Spec 024 (Processos Asíncrons / Workers)**: Exportació capdavantera a AEAT i automatització de Backups.
- **Spec 022 (Superadmin KPIs)**: Telemetria final global del sistema.

---

### Execució Immediata
El pas a seguir per respectar aquest pla de desenvolupament serà finalitzar **la Fase 2 (Spec 019: Login Operari)** creant exclusivament l'endpoint `/api/v1/operari_auth/login` i els tests pertinents simulant intents fallits per assegurar que els PINs xifrats avui responen perfectament abans de començar amb els Clients (Fase 3).
