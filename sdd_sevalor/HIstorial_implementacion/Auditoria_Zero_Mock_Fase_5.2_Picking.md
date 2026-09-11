# Auditoria Zero Mock: Fase 5.2 (Picking i Detall PWA) Completada ✅

L'ecosistema PWA de l'Operari ara està totalment integrat amb l'estructura de la Base de Dades i l'assignació tècnica.

## Què s'ha validat (Test E2E de 17.5 segons)
1. **Backoffice a PWA**: Es crea una Feina (`OT-***`) i s'assigna a un client, cap de colla, i material (`Tub PVC ***`).
2. **Connexió Privada**: Només el Cap de Colla autenticat té accés exclusiu a aquesta fulla de Picking. No s'exposa mai la llista completa del magatzem, acomplint amb les regles de privacitat exigides.
3. **Tot en Una Plana**: 
   - L'operari llegeix el destí.
   - Té un "botó" de Plànols adjunts (placeholder) i vehicle.
   - Veu en una llista clara quin material té previst gastar (Assignat per Enginyeria prèviament a `linies_picking`).
   - L'operari pot fer "+ / -" per determinar quina ha estat la quantitat final utilitzada (`quantitat_carregada_pick_in`).
4. **Alerta de Material Faltant**: Un botó llança un Modal PWA natiu dissenyat en Mobile First, i s'enregistra automàticament com a `Incidència` tipus `MATERIAL` (Estat `VERMELL`) amb l'Ordre de Treball associada.

Tot programat de forma Reactiva amb `Next.js` i guardat directament contra els esquemes `LiniaPicking` de Postgres de forma bidireccional sense Mocking de dades.

El sistema està llest per la següent iteració: Mòdul global de report d'incidències generals (Spec 016).
