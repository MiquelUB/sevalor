# Implementació Frontend PWA: Consum de Material - Picking (Spec 014)

El mòdul de Picking permet als operaris reportar a temps real quin material estan utilitzant en una `OrdreTreball` directament des de la finca/obra, permetent al sistema descomptar automàticament l'estoc del magatzem.

## User Review Required
> [!IMPORTANT]
> Actualment l'API `picking.py` permet crear fulles i línies, però no hi ha cap ruta perquè la PWA pugui llistar els materials (articles) disponibles al magatzem ni obtenir el picking actiu d'una feina. Construiré aquests 2 endpoints abans del Frontend. Estàs d'acord?

## Proposed Changes

### [NEW] Endpoint Backend `/api/v1/operari_pwa/magatzem.py`
Crearem una ruta de només lectura `GET /api/v1/operari/articles` perquè el mòbil pugui fer cerques a la base de dades d'articles i saber què hi ha disponible per consumir.

### [MODIFY] Endpoint Backend `/api/v1/operari_pwa/picking.py`
Afegirem un mètode `GET /api/v1/operari/feines/{feina_id}/picking` que buscarà si la feina ja té una `FullaPicking` associada i en retornarà les línies de consum. Si no existeix, es crearà automàticament on-the-fly quan l'operari afegeixi el primer material.

### [NEW] Mòdul PWA: Detall de la Feina (`/operari/feines/[id]/page.tsx`)
Pantalla on l'operari veu les dades concretes de l'Ordre de Treball que ha seleccionat.
Tindrà 2 pestanyes / seccions:
1. **Resum**: Descripció, adreça, client.
2. **Materials**: Llista del que ja s'ha consumit i botó flotant `+ Afegir`.

### [NEW] Mòdul PWA: Cercador de Materials (Modal o Pàgina)
Un formulari on escriu el nom del material (ex: "Tub 25mm"), la PWA crida l'API d'articles, el selecciona, posa la quantitat i fa un `POST` al picking. Això registrarà el material com consumit (Pick IN).

### [NEW] `frontend/tests/operari_picking.spec.ts`
Test *Zero Mock*:
1. Creació d'Article des del Backoffice (tub).
2. Login PWA Operari.
3. Entrar a una feina, anar a Materials.
4. Cercar el tub, afegir 10 unitats, guardar.
5. Verificació a pantalla que la llista s'ha actualitzat.

## Verification Plan
1. L'Stock s'ha de mostrar reduït al backend o com a mínim vinculat correctament.
2. El Playwright ha de certificar la cerca del desplegable de materials i la inserció des de "Mobile Chrome".
