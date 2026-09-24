---
name: task-planner
description: >-
  Usa aquesta skill quan calgui descompondre el Pla d'Arquitectura en tasques atòmiques d'implementació (tareas.md). Genera una llista seqüencial de tasques de menys de 30 minuts, ordenades per dependències i amb criteris d'acceptació binaris "Fet quan:".
---

# Planificador de Tasques Atòmiques (Task Planner)

Converteix el Pla d'Arquitectura i Disseny Físic en una **seqüència ordenada i executable de tasques d'implementació atòmiques**. Cada tasca és una unitat mínima de treball que pot ser codificada, provada i validada en menys de 30 minuts.

---

## Procés de Descomposició

1. **Anàlisi de Dependències Estructurals:**  
   Examina el model relacional i els components del pla per establir l'arbre de dependències lògiques (Fundació de Base de Dades ➔ Backend Core & Seguretat ➔ PWA Mòbil ➔ Web Gestió ➔ Workers i Microserveis).
2. **Segmentació en Blocs Cohesius:**  
   Organitza el pla de tasques en blocs temàtics clars:
   - **Bloc 1: Infraestructura i Base de Dades Inicial** (Contenidors, esquemes SQL, taules, RLS).
   - **Bloc 2: Backend Core, Seguretat Multi-Tenant i Autenticació** (Middlewares, JWT, Web Crypto, OTP).
   - **Bloc 3: Mòdul de Camp (PWA `/operari`)** (Components tàctils, càmera antifrau, geovalla, tiquets).
   - **Bloc 4: Central Web i Administració (`/gestio`)** (Spotlight, Three-Way Matching, bloqueig d'estoc, veto).
   - **Bloc 5: Microserveis, Integracions i Processament Asíncron** (Whisper INT8, bot Telegram, ReportLab Veri*factu, Outbox SOAP, backups).
3. **Redacció de Cada Tasca Atòmica:**  
   Per a cada tasca, documenta de forma obligatòria:
   - **Identificador i Títol:** `[ ] Tasca X.Y: Nom concís de l'acció tècnica`.
   - **Dependència:** Identificador exacte de la tasca prèvia que ha d'estar completada abans d'iniciar aquesta (o `Cap (Punt d'inici)`).
   - **RF Associats:** Llista de requisits funcionals de les especificacions que cobreix (ex: `Spec 011 (RF-21), Spec 019 (RF-24)`).
   - **Línia "Fet quan:":** Criteri d'acceptació binari i mesurable (què ha de retornar una comanda de terminal, un test de Pytest o una crida d'API per considerar-la satisfeta).

---

## Regles Inviolables

1. **Límit de 30 Minuts:** Cap tasca no pot tenir una durada estimada superior a 30 minuts. Si una tasca és massa gran, divideix-la en subtasques independents.
2. **Criteri "Fet quan:" 100% Objectiu:** Prohibit utilitzar descripcions vagues com *"fet quan funcioni bé"* o *"fet quan estigui implementat"*. El criteri ha de descriure una comprovació mecànica:
   - Un assert de test unitari o d'integració (`pytest test_x.py`).
   - Un codi de resposta HTTP específic (`POST retorna 201 Created amb UUID`).
   - Una restricció de base de dades efectiva (`trigger bloqueja UPDATE retornant error SQL`).
   - Un missatge d'estat buit exacte renderitzat a pantalla.
3. **Ordre Estricte Acíclic (DAG):** Les dependències han de formar un graf acíclic dirigit. Està prohibit establir dependències circulars o començar components visuals abans de tenir llest el suport de dades.
4. **Sense Codi a la Tasca:** La tasca indica **QUINA acció tècnica fer** i **COM comprovar-la**, no conté el codi de la solució.

---

## Format Estàndard d'una Tasca

```markdown
[ ] Tasca 1.3: Script SQL d'Activació de Row Level Security (RLS) Global
    Dependència: Tasca 1.2.
    RF associats: Spec 011 (RF-21), Spec 019 (RF-24), Spec 021 (RF-05).
    Fet quan: En executar el script SQL d'inicialització, la directiva ALTER TABLE ... FORCE ROW LEVEL SECURITY està activa a totes les taules creades i la política filtra estrictament per l'atribut app.current_empresa_id.
```
