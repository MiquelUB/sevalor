# Pla d'Implementació — PWA: Control Horari de Flota, Odòmetre i Carburant (/operari/vehicles — Spec 015)

Aquest pla defineix la implementació del mòdul de **Control de Flota, Registre d'Odòmetre per Foto i Tiquets de Carburant** d'acord amb la **Spec 015**, la Constitució v4.0 de SEVALOR i la política de **Zero Mock Data**.

---

## 🎯 Objectius del Mòdul
1. **Registre d'Odòmetre Inicial i Final per Càmera Obligatòria (`RF-01` a `RF-06`)**:
   - En iniciar i finalitzar la jornada, l'operari ha de capturar una fotografia de l'odòmetre del quadre de comandaments.
   - Deshabilitació de la introducció manual de quilometratge per a impedir fraus o falsificacions.
   - Extracció i verificació de continuïtat de km contra el darrer valor registrat a la base de dades.
2. **Repostatge en Ruta amb Doble Foto Obligatòria (`RF-07` a `RF-12`)**:
   - En registrar una càrrega de carburant:
     1. Fotografia del tiquet de l'estació de servei (import, litres i NIF de la benzinera).
     2. Fotografia en viu de l'odòmetre en el moment exacte del repostatge.
3. **Control d'AdBlue & Anàlisi de Consum Real (`RF-13` a `RF-16`)**:
   - Registre separat de litres d'AdBlue per a vehicles dièsel industrials.
   - Càlcul del consum mitjà L/100km per a detecció de sobreconsums o fuites.
4. **Comprovació de Càrrega EV Nocturna (`RF-17`, `RF-18`)**:
   - Check de connexió per a vehicles híbrids endollables o elèctrics de la flota en arribar a la nau.
5. **Zero Mock Data & Emmagatzematge Sobirà Hetzner (`RF-19` a `RF-22`)**:
   - Les fotografies es desen exclusivament a `/data/<empresa_id>/vehicles/` sense sortida a servidors de tercers.

---

## 🛠️ Components Tècnics
- **Frontend PWA**: `pwa/src/app/operari/vehicles/page.tsx`
- **Control de Càmera HTML5**: `accept="image/*" capture="environment"` per a forçar foto en directe.
- **Auditoria QA**: `pwa/test_pwa_audit.mjs` i `backend/tests/test_flota.py`
