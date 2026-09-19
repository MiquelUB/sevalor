---
name: Strict Compliance Protocol
description: Força el seguiment estricte de les especificacions i la verificació real de tests.
scope: global
---

# STRICT COMPLIANCE PROTOCOL (ACTIU)

A partir d'ara, l'agent ha d'acatar incondicionalment les següents regles d'execució:

## 1. ZERO INVENCIONS A LA UI I SPECS
- **Llei de Lectura:** Abans de programar, l'agent està obligat a llegir l'arxiu d'especificacions exacte (ex: `spec_010.md`).
- **Llei d'Implementació:** Prohibit afegir botons, pestanyes, textos o components "mockejats" (falsos) per farcir la interfície. Si l'spec diu "A i B", es programa exclusivament "A i B".
- **Llei de Dades Reals:** Tota connexió Frontend-Backend s'ha de fer amb dades reals. Estan prohibits els arrays estàtics o dades _hardcodejades_ en el codi de producció.

## 2. VERIFICACIÓ DE TESTS ESTRICTA (ZERO MENTIDES)
- **Execució Obligatòria:** És il·legal afirmar que "els tests passen" sense haver executat explícitament `pytest` en la terminal durant l'actual torn d'execució.
- **Proves Completes:** L'agent ha d'executar el test específic afectat I la suite general per detectar efectes col·laterals (`pytest backend/tests/`).
- **Reportatge de Logs:** Si el test falla (encara que sigui per un error de tipus), l'agent no pot ocultar-ho. Ha d'enganxar l'error real, solucionar-lo, i tornar a executar.

## 3. CONFIRMACIÓ DE TASQUES
En finalitzar una tasca, l'agent només pot tancar la intervenció si respon exactament amb:
1. L'arxiu/s modificat/s.
2. L'output exacte de la terminal demostrant que compila (`npm run build`) o passa el test (`pytest`).
3. El *Hash* del commit realitzat.
