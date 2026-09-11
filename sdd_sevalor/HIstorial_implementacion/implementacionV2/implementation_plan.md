# Pla d'Execució: Reconstrucció Total (Spec 008 i 019)

Alineant-nos amb la instrucció **Terra Cremada / Destrucció Controlada**, s'han esborrat del repositori centenars de línies de codi i tests pertanyents als antics mòduls (`gestio/`, `services/`, `operari_auth.py`, `telemetria.py`, i totes les seves proves). Només s'ha deixat intacte el **Nucli de Seguretat i Base de Dades (Specs 012, 021 i 023)** que vam refer anteriorment, les quals he tornat a testejar i segueixen oferint un robust 100% verd.

Ara aplicarem el desenvolupament guiat per proves (TDD/SDD) rigorós començant pels pilars de la plataforma: els operaris.

## User Review Required

> [!WARNING] 
> **Zero Mocks & 100% SDD (Spec Driven Development):**
> No hi haurà cap dada falsa. Aquest pla crearà proves reals contra una base de dades PostgreSQL real, verificant l'aïllament del tenant per assegurar que una empresa mai veu l'operari d'una altra.
> 
> *Confirmar si el PIN de recuperació s'ha d'enviar per email o si el Boss l'ha de forçar des del dashboard de Gestió.*

## Proposed Changes

---

### [Gestió de Base d'Operaris (Spec 008)]

*   **[NEW] [backend/tests/test_gestio_operaris.py](file:///media/akaun/Project_1/SEVALOR/backend/tests/test_gestio_operaris.py)**
    - Implementació de proves asíncrones per l'alta d'operaris. S'assegurarà que el NIF és únic només per empresa (dos tenants poden tenir el mateix NIF d'operari contractat).
    - Proves per validar els llistats amb Row-Level Security (RLS) imposada; l'empresa A mai no recuperarà operaris de la B.

*   **[NEW] [backend/app/api/v1/gestio/operaris.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/gestio/operaris.py)**
    - Creació de la ruta per afegir i gestionar operaris usant FastAPI asíncron i l'injecció de la sessió de la BD de `core.db`.
    - Integració al router principal exclusivament sota l'esquema d'autenticació del Boss.

---

### [Login i Seguretat Operari (Spec 019)]

*   **[NEW] [backend/tests/test_operari_auth.py](file:///media/akaun/Project_1/SEVALOR/backend/tests/test_operari_auth.py)**
    - Proves pures sobre l'intercanvi del PIN i el NIF per a un token JWT (Auth Endpoint).
    - Prevenció d'atacs de força bruta simulant diversos errors seguits.

*   **[NEW] [backend/app/api/v1/operari_auth.py](file:///media/akaun/Project_1/SEVALOR/backend/app/api/v1/operari_auth.py)**
    - Verificació xifrada del PIN al backend (usant Bcrypt, zero text-pla).
    - Expedició i signatura de tokens JWT exclusius connectant amb la nova estratègia rotativa del secret.

## Verification Plan

### Automated Tests
- `pytest tests/test_gestio_operaris.py` - Verificació ABAC (Attribute-Based Access Control) i RLS a la DB.
- `pytest tests/test_operari_auth.py` - Garantir la impossibilitat d'adquirir un JWT si no s'és un operari legal de l'empresa o el PIN és fallit.

### Manual Verification
- Un cop verda tota la bateria, sol·licitaré que observis un procés de login manual des de Postman/cURL abans de procedir a la següent Especificació (com la gestió de Plànols o Flota).
