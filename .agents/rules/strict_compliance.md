---
name: Strict Compliance Protocol
description: Força el seguiment estricte de les especificacions i la verificació real de tests.
scope: global
---

# STRICT COMPLIANCE PROTOCOL (ACTIU)

A partir d'ara, l'agent ha d'acatar incondicionalment les següents regles d'execució:

## 1. ZERO INVENCIONS A LA UI I LECTURA OBLIGATÒRIA
- **Llei de Lectura Integral:** Abans de programar o tocar codi, l'agent està OBLIGAT a llegir `constitution.md`, l'arxiu d'especificacions exacte (`spec.md`), el pla d'arquitectura (`plan.md`) i les tasques específiques (`tasks.md`) de cada spec.
- **Llei d'Implementació:** Prohibit afegir botons, pestanyes, textos o components "mockejats" (falsos) per farcir la interfície. Si l'spec diu "A i B", es programa exclusivament "A i B".
- **Llei de Dades Reals (Zero Mock Data):** Tota connexió Frontend-Backend s'ha de fer amb dades reals. Estan prohibits els arrays estàtics o dades _hardcodejades_ en el codi de producció.

## 2. VERIFICACIÓ DE TESTS ESTRICTA I OBLIGATÒRIA (TESTS NETS AL 100%)
- **Execució i Aprovació Neta Mandatòria:** L'agent ha d'executar els tests i passar-los obligatòriament nets al 100% (`pytest -v`), verificant que no hi hagi falsos positius, errors d'event loop ni vulneracions de Row Level Security (RLS) segons la normativa de Fase 0 (`Auditoria_i_Normativa_Tests_Backend.md`).
- **Proves Completes:** L'agent ha d'executar el test específic afectat I la suite general per detectar efectes col·laterals (`pytest backend/tests/`).
- **Reportatge Transparent de Logs:** Si el test falla (encara que sigui per un error de tipus), l'agent no pot ocultar-ho ni fer mock de la fallada. Ha d'enganxar l'error real, solucionar-lo al codi de producció, i tornar a executar fins que quedi completament net.

## 3. CONFIRMACIÓ DE TASQUES
En finalitzar una tasca, l'agent només pot tancar la intervenció si respon exactament amb:
1. L'arxiu/s modificat/s.
2. L'output exacte de la terminal demostrant que compila (`npm run build`) o passa el test (`pytest`).
3. El *Hash* del commit realitzat.
