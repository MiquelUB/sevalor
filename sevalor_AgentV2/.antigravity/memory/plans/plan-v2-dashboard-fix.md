# Implementation Plan: Fix Gestió Dashboard Navigation

**Branch**: `main` | **Date**: 24/09/2026 | **Spec**: [000-high-level-definition.md]

## Summary

La Torre de Control (Dashboard) construïda a `pwa/src/app/gestio/page.tsx` no s'està mostrant en iniciar sessió perquè la lògica d'enrutament heretada redirigeix ​​forçosament tots els usuaris cap a `/gestio/mapa`. Modificarem les redireccions perquè la Torre de Control sigui la nova pàgina d'inici (Home) per a tot el backoffice.

## Technical Context

- **Framework**: Next.js App Router (TypeScript)
- **Files to Modify**: `pwa/src/middleware.ts`, `pwa/src/app/gestio/login/page.tsx`
- **Dependencies**: React, Next.js routing

## Project Structure

Aquest canvi només afecta la lògica de Client i Middleware del frontend (`pwa/`). No té cap impacte a la base de dades ni al backend de FastAPI.

```text
pwa/
├── src/
│   ├── middleware.ts                   # Modificar redirecció servidor
│   └── app/
│       └── gestio/
│           └── login/
│               └── page.tsx            # Modificar redirecció client
```

## Tasks (Passos a Executar)

1. **Editar `pwa/src/app/gestio/login/page.tsx`**:
   - Cerca: `window.location.href = "/gestio/mapa";`
   - Reemplaça per: `window.location.href = "/gestio";`
   
2. **Editar `pwa/src/middleware.ts`**:
   - Cerca: `return NextResponse.redirect(new URL('/gestio/mapa', request.url));`
   - Reemplaça per: `return NextResponse.redirect(new URL('/gestio', request.url));`

3. **Verificació Local**:
   - Executar `cd pwa && npm run build` per verificar que no hi hagi problemes de sintaxi ni conflictes als tipus de TypeScript.
   - Fer un *commit* de les correccions.

---

**NOTA:** Aquest pla està llest per a ser executat per l'Agent tan bon punt polsis el botó "Proceed" o donis confirmació per xat.
