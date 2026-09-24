# Informe d'Auditoria Zero Mock Completada (Fase 1 i 2)

## 1. Resum Executiu
S'han auditat les Fases 1 (PWA Login) i 2 (Dashboard Entitats) eliminant absolutament tots els *mocks* de xarxa en els tests de Playwright. S'ha comprovat la interacció end-to-end (E2E) directa i real entre el Frontend (Next.js) i el Backend (FastAPI).

Aquest procés ha revelat diversos problemes arquitectònics crítics al Backend que provocaven caigudes tipus "Internal Server Error" sota certes condicions, els quals s'han solucionat completament. L'arquitectura és ara robusta, immune a *leaks* de seguretat, i plenament connectada sense simulacions d'API.

## 2. Descobriments Crítics i Solucions al Backend (RLS PostgreSQL)

El descobriment més important d'aquesta auditoria "Zero Mock" ha estat una fallada arquitectònica subtil relacionada amb **Row Level Security (RLS)** a SQLAlchemy i FastAPI. 
En certes rutes com `alta_client`, `alta_operari` i `alta_article`, l'ORB guardava la instància i immediatament executava `await db.refresh(...)`. Al tenir l'aplicació configurada per lligar les polítiques RLS al cicle de transacció local de PostgreSQL (`set_config('app.current_empresa_id', :val, true)`), el mètode `refresh()` feia saltar l'error **`sqlalchemy.exc.InvalidRequestError: Could not refresh instance`** si la transacció preèvia era tallada o alterada (perquè perdia la identitat de l'empresa temporal, i Postgres li denegava l'accés a llegir la fila que tot just havia escrit).

**Solució implementada**: S'ha reestructurat i netejat profundament el cicle de *commit* de FastAPI en els *routers* següents:
- `/app/api/v1/gestio/clients.py`
- `/app/api/v1/gestio/operaris.py`
- `/app/api/v1/gestio/magatzem.py`

S'ha eliminat la necessitat d'utilitzar mètodes inestables de *refresh* fora del *bound* RLS, deixant que els models instanciats en Python mantinguin les seves propietats correctament, evitant els errors 500 que col·lapsaven el servei. A més, s'han alineat els payloads d'entrada de les dades del formulari amb les constants enumerades imposades per base de dades (com `METRES_LINEALS` en comptes del generalista `METRES`).

## 3. Resultat Final dels Tests Playwright (True E2E)

**Test Suites Aprovades (100% PASS, 0% Mocking)**
1. `login.spec.ts`: Validat el flux de login mitjançant un PIN correcte per l'usuari simulat (99999999E). Confirmada també l'escriptura exitosa del JWT token emès pel backend a `localStorage`. (Inclou validació del bloqueig de PIN al 4t intent erroni, i els missatges d'error reals).
2. `dashboard_clients.spec.ts`: Validada l'alta completa amb assignacions de Codi de client generats aleatòriament sense col·lisions.
3. `dashboard_entitats.spec.ts`: Validat tant el mòdul d'Operaris com la validació restrictiva d'Articles (Magatzem), incloent el testeig visual de l'indicador de Stock d'emergència en vermell processat des de FastAPI.

Tots els components Next.js s'enllacen via Reverse Proxy API directament a Uvicorn `http://127.0.0.1:8001`, de manera invisible i respectant la integritat de CORS.

L'aplicació és ara totalment lliure d'emulacions per la Fase 1 i Fase 2.
