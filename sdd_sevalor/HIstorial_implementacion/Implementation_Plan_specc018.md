# Pla d'Implementació — PWA: Tiquets de Despesa de Camp (/operari/tiquets — Spec 018)

Aquest pla defineix la implementació del mòdul de **Captura i Liquidació de Tiquets de Despesa en Ruta** d'acord amb la **Spec 018**, la Constitució v4.0 de SEVALOR i la política de **Zero Mock Data**.

---

## 🎯 Objectius del Mòdul
1. **Captura Fotogràfica de Tiquets d'Obra (`RF-01` a `RF-06`)**:
   - Despeses imprevistes de ferreteria, peatges, material auxiliar o dietes d'urgència.
   - Captura directa mitjançant càmera obligatòria sense pujades de galeria.
2. **Límit de Seguretat Diari (100 €/dia) (`RF-07` a `RF-10`)**:
   - Control de seguretat automàtic: les despeses acumulades per operari que superin els 100 €/dia requereixen autorització expressa del Boss o Secretaria.
3. **Emmagatzematge Asíncron al Directori Sobirà Hetzner (`RF-11` a `RF-15`)**:
   - Desat dels comprovants a `/docs/<empresa_id>/tiquets/` de manera asíncrona des de la cua Outbox.
4. **Associació a Ordre de Treball (`RF-16`, `RF-17`)**:
   - Imputació del cost del tiquet a l'expedient d'obra per a la posterior reconciliació financera (Spec 012).
5. **Zero Mock Data & Mode Fosc (`RF-18` a `RF-21`)**:
   - Estat buit canònic sense despeses fictícies.

---

## 🛠️ Components Tècnics
- **Frontend PWA**: `pwa/src/app/operari/tiquets/page.tsx`
- **Validació de Límits**: Càlcul de saldo diari en client i verificació transaccional al backend.
- **Auditoria QA**: `pwa/test_pwa_audit.mjs`
