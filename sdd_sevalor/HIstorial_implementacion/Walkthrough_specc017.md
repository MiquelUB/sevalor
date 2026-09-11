# Walkthrough d'Auditoria i Verificació — PWA: Plànols Vectorials As-Built (/operari/planols — Spec 017)

Aquest document certifica la implementació i verificació del mòdul **PWA Plànols Vectorials i Capes As-Built** d'acord amb la **Spec 017**.

---

## 🎯 Proves i Regles de Negoci Verificades
1. **Visor Cartogràfic WGS84 en Camp (`RF-01` a `RF-06`)**:
   - Verificat el renderitzat de capes d'obra i la geolocalització de l'operari sobre el terreny.
2. **Anotacions As-Built No Destructives (`RF-07` a `RF-12`)**:
   - Comprovada la creació de capes derivades sense alteració del plànol mestre aprovat per enginyeria.
3. **Immutabilitat Pericial d'Obres Tancades (`RF-13` a `RF-16`)**:
   - Verificat el bloqueig d'edició amb avís pericial davant de projectes finalitzats.
4. **Simbologia de Reg Normalitzada**:
   - Verificada la coherència visual dels elements hidràulics segons l'estàndard industrial.

---

## 📊 Resultats de la Suite de Proves QA
- **Suite PWA QA**: `node pwa/test_pwa_audit.mjs` (Plànols i capes As-built 100% en verd).
