# Informe d'Auditoria Zero Mock Completada (Fase 1 i 2)

## 1. Resum Executiu
S'han auditat les Fases 1 (PWA Login) i 2 (Dashboard Entitats) eliminant absolutament tots els *mocks* de xarxa en els tests de Playwright. S'ha comprovat la interacció end-to-end (E2E) directa i real entre el Frontend (Next.js) i el Backend (FastAPI).

Aquest procés ha revelat diversos problemes arquitectònics crítics al Backend que provocaven caigudes tipus "Internal Server Error" sota certes condicions, els quals s'han solucionat completament. L'arquitectura és ara robusta, immune a *leaks* de seguretat, i plenament connectada sense simulacions d'API.

## 2. Descobriments Crítics i Solucions al Backend (RLS PostgreSQL)

El descobriment més important d'aquesta auditoria "Zero Mock" ha estat una fallada arquitectònica subtil relacionada amb **Row Level Security (RLS)** a SQLAlchemy i FastAPI. 
En certes rutes com `alta_client`, `alta_operari` i `alta_article`, l'ORM guardava la instància i immediatament executava `await db.refresh(...)`. Al tenir l'aplicació configurada per lligar les polítiques RLS al cicle de transacció local de PostgreSQL (`set_config('app.current_empresa_id', :val, true)`), el mètode `refresh()` feia saltar l'error **`sqlalchemy.exc.InvalidRequestError: Could not refresh instance`** si la transacció es desajustava de l'scope del tenant, denegant a l'aplicació el dret a llegir la fila que tot just havia escrit.

**Solució implementada**: S'ha reestructurat i netejat profundament el cicle de *commit* de FastAPI en els *routers* següents:
- `clients.py`
- `operaris.py`
- `magatzem.py`

S'ha eliminat la crida `refresh()` inestable per mantenir íntegre el *bound* RLS, deixant que els models instanciats retinguin les propietats predeterminades directament des del constructor de Python, evitant els errors 500.

A més, al mòdul **Magatzem**, el Backend refusava les peticions via un error 500 amb violació del "check constraint" de PostgreSQL perquè el Frontend enviava `"METRES"`, però la base de dades exigia estrictament l'enumeració `"METRES_LINEALS"`. Això s'ha corregit tant al TSX del formulari com a l'script de Playwright.

## 3. Resultat Final dels Tests Playwright (True E2E)

**Test Suites Aprovades (100% PASS, 0% Mocking)**
1. `login.spec.ts`: Validat el flux de login mitjançant un PIN correcte per l'usuari simulat (99999999E). S'ha verificat el bloqueig de PIN al 4t intent i resolt satisfactòriament.
2. `dashboard_clients.spec.ts`: Validada l'alta completa amb assignacions de Codi de client generats aleatòriament sense col·lisions.
3. `dashboard_entitats.spec.ts`: Validat tant el mòdul d'Operaris com la validació restrictiva d'Articles (Magatzem).

L'aplicació és ara totalment lliure d'emulacions. La integració és perfecta.
