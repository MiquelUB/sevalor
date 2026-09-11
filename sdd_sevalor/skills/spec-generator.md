---
name: spec-generator
description: >-
  Usa aquesta skill quan l'usuari demani crear, redactar o revisar una especificació funcional (spec) d'un mòdul o funcionalitat. Guia una entrevista de requisits, aplica la notació EARS i produeix o audita un document spec.md seguint la plantilla oficial de l'equip.
---

# Generador d'Especificacions (Spec Generator)

Converteix una necessitat de negoci o idea operativa en una especificació acordada i vinculant. La spec és el contracte del sistema: **si un comportament no està explícitament a la spec, no s'implementa**.

---

## Procés d'Elaboració

1. **Llegir el Context i la Constitució:**  
   Llegeix obligatòriament `constitution.md` i les specs existents a `specs/` per respectar convencions, nomenclatura, arquitectura multi-tenant i no contradir principis acordats (Zero Mock Data, sobirania local, RLS).
2. **Entrevista de Requisits (Human-in-the-Loop):**  
   Fes preguntes d'**UNA en UNA**, màxim 5 o 6 qüestions clau, esperant resposta abans de passar a la següent. Centra't en:
   - Casos límit i comportament davant d'errors.
   - Què queda explícitament fora d'abast (*Out of Scope*).
   - Rol i actors implicats (Zero-Trust).
   *No proposis solucions tècniques de codi:* si l'usuari pregunta com es faria, redirigeix la conversa cap al **QUÈ** i el **PER QUÈ**.
3. **Assignació de Codi i Nomenclatura:**  
   Revisa `specs/` i assigna el següent identificador correlatiu disponible de tres xifres: `specs/NNN-<nom-en-kebab-case>.md`.
4. **Redacció Estricta en Notació EARS:**  
   Redacta el document cobrint totes les seccions mandatòries:
   - Context i Objectiu.
   - Usuaris / Actors i Matriu d'Accés Zero-Trust.
   - Requisits Funcionals en EARS (`RF-01`, `RF-02`...).
   - Taula de Casos Límit i Gestió d'Errors.
   - Fora d'Abast (*Out of Scope*).
   - Criteris de Finalització (*Definition of Done*) i Matriu de Traçabilitat.
5. **Detecció de Buits d'Informació:**  
   Marca qualsevol detall desconegut amb l'etiqueta explícita: `[NECESSITA ACLARACIÓ: pregunta concreta]`. **Mai omplis un buit inventant o suposant**: un buit visible és informació; una suposició silenciosa és deute tècnic.
6. **Validació i Aprovació:**  
   Sol·licita l'aprovació explícita de l'usuari en concloure la redacció. No passis mai a la planificació ni escriguis codi sense aquesta validació.

---

## Regles Inviolables

1. **QUÈ i PER QUÈ, Mai COM:** Prohibit incloure stack tecnològic intern, noms de fitxers de codi, esquemes SQL o signatures de funcions a la spec; això pertany exclusivament al pla d'arquitectura.
2. **Fora d'Abast Obligatori:** Inclou sempre la secció *Out of Scope* per evitar la proliferació de funcionalitats no acordades (*scope creep*).
3. **Un Requisit, Una Frase:** Si cal utilitzar la conjunció "i" per unir dos comportaments diferents, s'han de redactar com a dos requisits separats.
4. **Sense Adjectius Subjectius:** Paraules com *"ràpid"*, *"intuïtiu"*, *"elegant"* o *"robust"* estan prohibides. S'ha d'indicar el llindar quantitatiu mesurable (ex: *"temps de resposta inferior a 200 ms"*) o no escriure'l.
5. **Idioma:** Català per defecte (idioma oficial del projecte i de la constitució).

---

## Notació EARS (Easy Approach to Requirements Syntax)

Utilitza exclusivament un d'aquests cinc patrons per a cada requisit funcional:

| Patró | Sintaxi Obligatòria | Àmbit d'Aplicació |
|---|---|---|
| **Ubicu** | EL SISTEMA [farà l'acció] | Comportament universal permanent |
| **Dirigit per Esdeveniment** | QUAN [disparador o acció d'usuari], EL SISTEMA [farà l'acció] | Resposta immediata a un estímul |
| **Dirigit per Estat** | MENTRE [condició o estat actiu], EL SISTEMA [farà l'acció] | Comportament vigent durant un estat concret |
| **Opcional** | ON [funcionalitat o paràmetre present], EL SISTEMA [farà l'acció] | Actuació condicionada a la presència d'un mòdul |
| **Comportament No Desitjat** | SI [condició d'error o atac], ALESHORES EL SISTEMA [farà l'acció] | Gestió de fallades, errors i seguretat |

### Exemples de Contrasts

* **Exemple Ben Escrit (EARS):**  
  `RF-04: SI el subdomini sol·licitat ja es troba en ús per un altre tenant, ALESHORES EL SISTEMA bloquejarà l'avanç de l'assistent d'alta i mostrarà el missatge: "Subdomini no disponible".`
* **Exemple Mal Escrit:**  
  `RF-04: El sistema ha de gestionar bé els dominis i ser àgil quan l'usuari s'equivoqui.` *(Sense patró EARS, sense criteri mesurable, dues idees en una frase).*

---

## Protocol de Revisió d'Specs Existents

Quan l'usuari demani revisar una spec existent en lloc de crear-ne una de nova, audita i reporta estructuradament en 4 blocs:
1. **Ambigüitats:** Termes o requisits amb múltiples interpretacions.
2. **Contradiccions:** Requisits que xoquen entre si o amb altres specs de la suite.
3. **Casos Límit No Coberts:** Situacions de caiguda de xarxa, errors de disc o concurrència sense tractar.
4. **Conflictes amb la Constitució:** Violacions del principi Zero Mock Data, aïllament RLS o sobirania de dades locals.
