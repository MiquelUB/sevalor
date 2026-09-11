# Pla d'Implementació — PWA: Càmera Tècnica i Evidències WebP (/operari/camera — Spec 020)

Aquest pla defineix la implementació del mòdul de **Càmera Tècnica d'Obra, Captura en Viu i Compressió WebP** d'acord amb la **Spec 020**, la Constitució v4.0 de SEVALOR i la política de **Zero Mock Data**.

---

## 🎯 Objectius del Mòdul
1. **Càmera Tècnica en Viu Obligatòria (`RF-01` a `RF-06`)**:
   - Ús estricte dels atributs HTML5 `accept="image/*" capture="environment"`.
   - Inhabilitació categòrica de pujades des de la galeria de fotos de l'aparell per a prevenir càrregues d'imatges pretèrites o manipulades.
2. **Compressió WebP en Client (<1 MB) (`RF-07` a `RF-12`)**:
   - Reducció del pes del fitxer directament al navegador del terminal mòbil abans de l'emmagatzematge o enviament.
   - Preservació de resolució nítida per a lectura de números de sèrie i caixetins d'obra.
3. **Geolocalització i Estampa Temporal Inalterables (`RF-13` a `RF-16`)**:
   - Injecció de coordenades WGS84 i timestamp UTC dins de les metadades de l'evidència pericial.
4. **Tramesa Atòmica per Blocs a Hetzner (`RF-17` a `RF-20`)**:
   - Enviament resilient a la cua d'Outbox; quan hi ha cobertura, la imatge es transfereix al directori Hetzner sobirà local de l'empresa.
5. **Zero Mock Data & Mode Fosc (`RF-21`, `RF-22`)**:
   - Disseny visual adaptat a condicions extremes de llum solar o foscor d'arquetes.

---

## 🛠️ Components Tècnics
- **Frontend PWA**: Components de càmera integrats a `/operari/incidencies`, `/operari/vehicles` i `/operari/feines`.
- **Motor de Compressió**: Canvas HTML5 amb exportació WebP (`image/webp`, qualitat 0.82).
- **Auditoria QA**: `pwa/test_pwa_audit.mjs`
