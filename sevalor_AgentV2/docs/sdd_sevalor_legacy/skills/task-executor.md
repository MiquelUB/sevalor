---
name: task-executor
description: >-
  Usa aquesta skill per implementar i executar les tasques atòmiques de tareas-implementacio-campopro.md. Aplica desenvolupament guiat per proves (TDD estricte), escriu codi net i tipat, compleix els 7 mandats constitucionals (Zero Mock Data, RLS) i valida el criteri "Fet quan:" abans de marcar la tasca com a completada.
---

# Executor de Tasques i Desenvolupament TDD (Task Executor)

Executa de forma rigorosa i metòdica cadascuna de les tasques del document `tareas-implementacio-campopro.md`, aplicant la metodologia **Test-Driven Development (TDD)** i garantint que cap codi arribi a producció sense complir estrictament les especificacions i la constitució.

---

## Cicle Operatiu de Treball (Tasca a Tasca)

1. **Selecció de la Tasca Activa:**  
   Localitza la primera tasca pendent `[ ]` les dependències de la qual estiguin completament marcades com a `[x]`. Mai treballis en múltiples tasques simultàniament ni et saltis l'ordre seqüencial.
2. **Revisió de Context Obligatòria:**  
   Abans de tocar codi, llegeix:
   - La tasca activa i el seu criteri *"Fet quan:"*.
   - Els requisits funcionals (RFs) associats a l'especificació (`specs/NNN-*.md`).
   - La secció corresponent del Pla d'Arquitectura (`plan-v2.md`).
   - `constitution.md` (mandats innegociables).
3. **Fase Vermella (Test Primer - TDD):**  
   Crea o actualitza el test automatitzat (`pytest` per a backend/BD o test de component per a frontend) que comprovi la condició de la línia *"Fet quan:"*. Executa el test i confirma que falla pel motiu esperat.
4. **Fase Verda (Implementació Mínima i Neta):**  
   Escriu el codi de producció estrictament necessari per fer passar el test en verd:
   - Backend: Python 3.12+, tipat estàtic estricte (`mypy`), docstrings en format Google, asíncron (`asyncpg` / `SQLAlchemy 2.0`).
   - Frontend: Next.js 14, Tailwind CSS amb variables HSL (`--color-primary`), TypeScript estricte.
5. **Fase de Refactorització i Qualitat:**  
   Executa les eines de control de qualitat:
   ```bash
   # Backend
   ruff check .
   mypy app/ --strict
   # Frontend
   npm run lint
   npm run build
   ```
6. **Auditoria dels Mandats Constitucionals:**  
   Verifica que la teva implementació no vulneri cap mandat:
   - **Zero Mock Data:** Comprova que no has introduït llistes dummy, noms falsos ni dades de prova al codi de producció; només estats buits fidels.
   - **Row Level Security (RLS):** Assegura't que s'injecta `SET LOCAL app.current_empresa_id` en cada sessió de base de dades.
   - **Sobirania Local:** Els fitxers es guarden a `/data/<empresa_id>/...` o `/docs/<empresa_id>/...` (zero AWS S3).
7. **Validació del Criteri "Fet quan:":**  
   Executa la comprovació exacta indicada a la tasca. Si l'assert és binari i positiu, marca la casella de la tasca com a completada:  
   `[x] Tasca X.Y: ...` a `tareas-implementacio-campopro.md`.
8. **Seguiment de Regles de Desplegament:**  
   - Si hi ha instrucció explícita de no tocar Git (*"NO GIT ESTA PERMES"*), desa els canvis directament als fitxers físics sense executar cap comanda git.
   - En cas contrari, executa el commit atòmic indicant la tasca i el push corresponent.

---

## Regles Inviolables

1. **PROHIBIT Crear Codi sense Test Previ:** Cap funció, endpoint o component es dóna per bo si no compta amb la seva prova automatitzada.
2. **Tolerància Zero a Dades Fictícies (Zero Mock Data):** Està terminantment prohibit afegir arrays de prova o registres inventats per fer bonic a la UI. Si la BD està buida, la interfície mostra l'estat buit real.
3. **Àmbit Tancat:** No modifiquis fitxers que no tinguin relació directa amb la tasca activa. Evita el "ja que hi sóc" (*while at it*).
4. **Resolució d'Errors:** Si un test falla, llegeix la traça d'error abans de fer modificacions a cegues. Consulta `docs/errors/ERRORS.md` si existeix.
