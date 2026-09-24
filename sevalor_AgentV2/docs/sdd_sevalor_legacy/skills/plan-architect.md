---
name: plan-architect
description: >-
  Usa aquesta skill quan calgui dissenyar, redactar o actualitzar el Pla d'Arquitectura i Disseny Físic (plan.md o plan-v2.md) a partir de les especificacions funcionals aprovades. Defineix el model de dades relacional, les decisions d'enginyeria justificades, l'estratègia de QA i la matriu de traçabilitat.
---

# Arquitecte de Disseny i Sistemes (Plan Architect)

Converteix el conjunt d'especificacions funcionals aprovades (Specs NNN) en un **Pla d'Arquitectura i Disseny Físic** precís i auditable. El pla és el pont tècnic que garanteix que el sistema es pugui codificar sense improvisacions ni incoherències estructurals.

---

## Procés d'Elaboració

1. **Lectura Integral de les Especificacions:**  
   Llegeix les specs que formen part de la fase (`specs/001` a `specs/NNN`), la Constitució i el document `AGENTS.md` per extreure totes les entitats, relacions, requisits no funcionals i restriccions de seguretat.
2. **Modelatge de Dades Relacional Lògic (Sense SQL de producció):**  
   Dissenya l'esquema relacional d'entitats agrupades per dominis de negoci:
   - Identifica totes les taules necessàries amb clau primària UUID v4.
   - Inclou de forma **mandatòria** la clau forana `empresa_id` a totes les taules d'inquilí per a l'aïllament `FORCE ROW LEVEL SECURITY`.
   - Especifica tipus de dades estructurats (ex. PostGIS `GEOMETRY(Point, 4326)` per a finques, camps xifrats simètricament amb AES-256-GCM per a IBANs o nòmines).
3. **Decisions Justificades d'Enginyeria (Trade-offs):**  
   Per a cada decisió arquitectònica rellevant (ex. cues Celery, emmagatzematge de documents, patrons d'enviament a la AEAT), documenta estrictament la tríada:
   - **Decisió d'Arquitectura:** La solució escollida.
   - **Justificació i Criteri de QA:** El motiu tècnic de robustesa, compliment normatiu o rendiment.
   - **Alternativa Descartada:** L'opció rebutjada i per què és inviable o perillosa.
4. **Estratègia de Proves i Control de Qualitat (QA):**  
   Defineix els casos de prova automatitzats crítics que validen els límits de seguretat abans del desplegament (tests d'aïllament RLS, inmutabilitat de registres SIF, no-recursivitat de backups, filtres anti-malware).
5. **Matriu de Traçabilitat:**  
   Mapeja cada bloc de disseny amb els codis `RF-XX` de les especificacions que cobreix directament.

---

## Regles Inviolables

1. **PROHIBIT Escriure Codi de Producció:** El pla descriu el model relacional, les taules, els camps, els patrons arquitectònics i els fluxos de dades, però mai conté fitxers de codi font ni implementació directa.
2. **Sobirania Absoluta d'Emmagatzematge:** Queda vetat qualsevol patró que contempli AWS S3 o núvols privatius estrangers; tot arxiu es persisteix a discs locals de l'empresa o servidor dedicat a Hetzner (Alemanya - UE).
3. **Aïllament RLS Mandatori:** Cap taula vinculada a un tenant pot existir sense `empresa_id` ni sense la directiva `FORCE ROW LEVEL SECURITY`.
4. **Patró Outbox per a Serveis Externs Inestables:** Les comunicacions amb plataformes públiques (com l'Agència Tributària per a Veri*factu) mai es fan de forma síncrona a l'API; requereixen de forma obligatòria el patró Outbox a la base de dades processat per Celery.
5. **Zero Mock Data per Disseny:** El model de dades ha de permetre estats buits fidels i rebutjar camps per defecte amb valors simulats o de demostració.

---

## Estructura Mandatòria del Pla (`plan.md`)

```markdown
# Plan de Diseño Físico de Base de Datos e Implementación de Código — CampoPro Suite

## 1. Mòduls d'Arquitectura i Sintonització Operativa
(Descripció dels sub-sistemes: Gestió d'Oficina, PWA Operari, Superadmin i Workers)

## 2. Model de Dades Relacional (Esquema Lògic)
(Definició d'entitats per blocs amb UUID, camps, claus foranes i RLS)

## 3. Decisions Justificades i Alternatives Descartades
(Tríada: Decisió / Justificació QA / Alternativa Descartada)

## 4. Estratègia de Tests i Control de Qualitat (Zero-Mock Policy)
(Disseny de proves Pytest d'aïllament, inmutabilitat i resiliència)

## 5. Matriu de Traçabilitat dels Requisits Funcionals (RF)
(Taula creuada Bloc d'Implementació <-> Requisits EARS coberts)
```
