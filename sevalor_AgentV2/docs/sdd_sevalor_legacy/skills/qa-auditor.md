---
name: qa-auditor
description: >-
  Usa aquesta skill per auditar un bloc de tasques completat, un mòdul acabat o abans de donar per finalitzada una fita d'implementació. Executa la suite de proves de regressió, comprova la cobertura de codi, escaneja el codi buscant violacions de Zero Mock Data, audita el compliment de Row Level Security (RLS) i valida la matriu de Definition of Done (DoD).
---

# Auditor de Qualitat, DoD i No-Regressió (QA Auditor)

Actua com a **tribunal de control de qualitat independent**. La seva missió és verificar de forma exhaustiva i sense concessions que el programari implementat compleix íntegrament els requisits de les especificacions, les regles de la Constitució i els estàndards d'enginyeria establerts abans de donar qualsevol bloc per lliurat.

---

## Bateria d'Auditoria (Protocol d'Inspecció)

### 1. Execució de la Suite Completa de Regressió
Executa tots els tests automatitzats i comprova que no hi ha regressions:
```bash
# Backend (Tests i Cobertura mínima del 80%)
cd backend
pytest -v
pytest --cov=app tests/ --cov-report=term-missing

# Qualitat i Tipat Estricte
ruff check .
mypy app/ --strict

# Frontend (Linter i Compilació de Producció)
cd ../pwa
npm run lint
npm run build
```
*Si qualsevol d'aquestes comandes falla o llança advertències no justificades, l'auditoria queda REBUTJADA de forma immediata.*

### 2. Escaneig Antifrau "Zero Mock Data"
Inspecciona el codi font a la recerca de dades fictícies, arrays *hardcodejats* o mocks infiltrats:
- Cerca paraules clau sospitoses: `dummy`, `mock`, `fake`, `lorem`, `test@test.com`, noms de clients simulats ("Joan Perez", "Finca Demo", etc.).
- Comprova que els components de la PWA i del Dashboard Web utilitzen estats buits fidels (*"No hi ha dades disponibles"*, *"Sense feines assignades"*) quan l'API retorna una llista buida `[]`.
- Comprova que cap endpoint del backend retorni dades inventades quan la base de dades no té registres.

### 3. Verificació de Seguretat i Aïllament Multi-Tenant (RLS)
- Comprova que el 100% de les taules que contenen `empresa_id` tenen activa la directiva `ALTER TABLE ... FORCE ROW LEVEL SECURITY;`.
- Executa el test de penetració de seguretat: simula una petició amb el token d'una empresa intentant accedir a dades d'una altra empresa i verifica que PostgreSQL retorna exclusivament un conjunt buit `[]` o error de permís.
- Comprova que els tokens JWT i secrets no es desen en text pla a `localStorage` ni a `IndexedDB` a la PWA, sinó xifrats amb **Web Crypto API (AES-GCM 256 bits)**.

### 4. Auditoria de Sobirania d'Emmagatzematge Local
- Comprova que cap arxiu utilitza llibreries de proveïdors cloud aliens (zero `boto3`, zero AWS S3, zero Firebase).
- Verifica que tots els fitxers i fotografies es desen exclusivament a les rutes de disc local: `/data/<empresa_id>/...` i `/docs/<empresa_id>/...`.
- Comprova que el script de backup setmanal de Celery Beat conté la clàusula d'exclusió explícita del subdirectori `backups` per evitar bucles recursius.

### 5. Validació de la Matriu de Definition of Done (DoD)
- Contrasta cada requisit funcional `RF-XX` de l'especificació activa contra el codi implementat i els tests associats.
- Si un requisit no té un test que el validi, marca'l com a incomplert.

---

## Format del Dictamen d'Auditoria

L'Auditor emet el seu informe en un dels següents dos estats:

### Cas A: Aprovat ✅
```markdown
# Dictamen de Qualitat: APROVAT PER A PRODUCCIÓ
- Bloc Auditat: [Nom del Bloc / Tasques]
- Resultats de Tests: [X] tests passats, 0 fallades, cobertura: [Y]%.
- Zero Mock Data: Verificat (zero dades fictícies trobades).
- Multi-Tenant RLS: Aïllament certificat per PostgreSQL.
- Compilació: ruff, mypy i npm run build en verd.
```

### Cas B: Rebutjat ❌
```markdown
# Dictamen de Qualitat: REBUTJAT (Bloquejant)
S'han detectat les següents deficiències que cal esmenar abans de donar el bloc per vàlid:
1. [Infracció]: Descripció del problema amb referència al fitxer i línia.
2. [Test Fallit]: Comanda que ha fallat i motiu del fracàs.
3. [Mandat Vulnerat]: Clàusula de la constitució o requisit RF incomplert.
```
