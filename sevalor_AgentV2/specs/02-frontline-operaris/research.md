# Technical Research & Lessons Learned: Frontline Operaris

**Feature Directory**: `sevalor_AgentV2/specs/02-frontline-operaris`  
**Date**: 2026-09-29  
**Status**: Active Knowledge Base

---

## 1. Architectural Lessons Learned & Previous Pitfalls

### 1.1 Next.js Middleware Redirect Paths Must Be Absolute
- **Issue Discovered**: In early Next.js middleware iterations, relative path redirects such as `NextResponse.redirect('/gestio/login')` or `NextResponse.redirect('/operari/login')` triggered Next.js runtime exceptions or caused infinite redirect loops in reverse-proxy setups (EasyPanel, Traefik, Docker containers). When deployed behind subdomains or custom enterprise domains (`tenantA.campopro.cat`), relative paths failed to resolve the origin correctly.
- **Enforced Solution**: Redirects in Next.js middleware MUST ALWAYS construct an absolute URL using the incoming request's base URL:
  ```typescript
  // CORRECT PATTERN
  const createRedirectWithClearedCookie = (targetUrl: string) => {
    return NextResponse.redirect(new URL(targetUrl, request.url));
  };
  
  // Usage
  if (!payload) {
    return createRedirectWithClearedCookie('/operari/login');
  }
  ```
- **Rule to Avoid Mistakes**: Never use relative strings in `NextResponse.redirect()`. Always provide the target path as the first parameter and `request.url` as the second parameter to `new URL()`.

---

### 1.2 IndexedDB for Offline Sync Over LocalStorage
- **Issue Discovered**: Attempting to cache work orders, offline form submissions, and media using `localStorage` hit hard browser limits (5 MB maximum per origin), blocked the UI thread during synchronous JSON serialization, and could not persist binary `Blob` data (audio voice notes and WebP photos). Furthermore, `localStorage` is vulnerable to plain-text inspection.
- **Enforced Solution**: Deploy **Dexie.js** wrapping **IndexedDB** (`SevalorFieldDB`, version 1).
  - Schema stores:
    - `ordres`: Stores assigned tasks and technical details.
    - `tiquets`: Stores receipts, categorized metadata, and sync status.
    - `incidencies`: Stores field incidents and local audio/photo blobs.
    - `fichajes`: Stores shift timestamps and odometer readings.
    - `sync_queue`: Holds atomic serialized payloads (`FITXAR_JORNADA`, `CREAR_TIQUET`, `REPORTAR_INCIDENCIA`, `INICIAR_TRAJECTE`, `FINALITZAR_ORDRE`).
- **Rule to Avoid Mistakes**: All offline persistence must pass through `localDB` in `pwa/src/lib/db.ts`. Media blobs must be stored directly in IndexedDB. Use Workbox Background Sync to replay actions against `POST /api/v1/operari_pwa/sync/push`.

---

### 1.3 FastAPI Multipart Endpoints & Missing `UploadFile` Imports
- **Issue Discovered**: Endpoints receiving both JSON metadata and uploaded files (e.g. `/operari/feines/{id}/fotos`, `/operari/incidencies`, `/operari/tiquets/ocr`) frequently threw runtime `NameError: name 'UploadFile' is not defined` or HTTP 422 validation errors when developers forgot FastAPI's multipart imports.
- **Enforced Solution**: In every router handling media or dual-mode payloads:
  ```python
  from fastapi import UploadFile, File, Form
  ```
  Always inspect `request.headers.get("content-type")` to gracefully handle both `application/json` (used in API tests and Dexie queue replays) and `multipart/form-data` (used during direct browser photo uploads).

---

### 1.4 Multi-Tenant Database Context (`get_db_with_tenant_context`)
- **Issue Discovered**: In PostgreSQL with `FORCE ROW LEVEL SECURITY` enabled, invoking a standard `db: AsyncSession = Depends(get_db)` fails to set the session variable `app.current_empresa_id`. Consequently, PostgreSQL evaluates the RLS policy to `NULL` or empty, returning zero rows or throwing permission exceptions even for valid workers.
- **Enforced Solution**: Every router in `/operari_pwa/` must inject:
  ```python
  from app.core.db import get_db_with_tenant_context

  @router.get("/feines")
  async def llistar_les_meves_feines(
      request: Request,
      db: AsyncSession = Depends(get_db_with_tenant_context)
  ):
      ...
  ```
- **Rule to Avoid Mistakes**: Never use bare `get_db` on tenant-scoped tables. For background Celery workers, explicitly run `await session.execute(text(f"SET LOCAL app.current_empresa_id = '{empresa_id}'"))` before querying.

---

### 1.5 Client-Side Image Compression & HTML5 Live Capture Anti-Fraud
- **Issue Discovered**: Field smartphones with 50-megapixel sensors take photos of 10–20 MB each. Uploading raw files on rural 3G networks caused browser memory crashes, exhausted IndexedDB quotas (triggering `QuotaExceededError`), and slowed uploads to a crawl. In addition, operators were occasionally selecting old photos from the device gallery instead of proving real-time presence on site.
- **Enforced Solution**:
  1. **Anti-Fraud HTML5 Capture**: Enforce `<input type="file" accept="image/*" capture="environment">`. This instructs mobile operating systems to trigger the rear camera directly, disallowing the file picker / photo gallery.
  2. **Canvas / WebWorker Compression**: Compress every photo in the client browser using HTML Canvas or OffscreenCanvas to **WebP format** at quality `0.80`, capping image size strictly below 1 MB while preserving readability of pipe labels, meter digits, and odometer numbers.

---

### 1.6 Web Crypto API for Zero-Trust Offline PIN Verification
- **Issue Discovered**: Storing PINs in plaintext or weakly hashed in IndexedDB creates a catastrophic security vulnerability if a mobile phone is lost or stolen in the field.
- **Enforced Solution**:
  - The browser derives a cryptographic key using the native Web Crypto API:
    - Algorithm: `PBKDF2` with `100,000` iterations, `SHA-256`, and a device-unique salt.
    - Derived Key: AES-GCM 256 bits.
  - A test block (`CAMPOPRO_SENTINEL`) is decrypted with the derived key. If decryption succeeds, the PIN is authentic, and the application unlocks IndexedDB for the day.
  - The derived key remains strictly in volatile JavaScript RAM and is purged upon shift closure, manual logout, or after 5 minutes in the app background.

---

### 1.7 Pure Python Geofencing Without Third-Party Services
- **Issue Discovered**: Relying on external map APIs for checking whether a worker has arrived on-site fails in zero-coverage rural areas and exposes company coordinates to third-party providers.
- **Enforced Solution**: Use the Haversine formula directly in Python backend and in JavaScript frontend:
  ```python
  def calcular_distancia_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
      R = 6371000.0  # Earth's radius in meters
      phi1 = math.radians(lat1)
      phi2 = math.radians(lat2)
      delta_phi = math.radians(lat2 - lat1)
      delta_lambda = math.radians(lon2 - lon1)
      a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
      c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
      return R * c
  ```
- **Rule to Avoid Mistakes**: Enforce 50m tolerance. If exceeded, provide an "Inici per Desviació" workflow requiring a photo of the surrounding environment rather than completely blocking work.

---

### 1.8 Non-Destructive Blueprint Layers & Geometry Simplification
- **Issue Discovered**: Directly editing or drawing on CAD/GIS blueprints creates unresolvable merge conflicts when multiple technicians work on the same network, and overwriting historical files violates auditability regulations. Additionally, vector GeoJSON files with >50,000 nodes froze mobile browser canvas renderers.
- **Enforced Solution**:
  - **Isolated As-Built Layers**: Field markups are always written to `capes_vectorials` with an explicit timestamp and operator ID, keeping `planols_base` immutable.
  - **Douglas-Peucker Simplification**: Heavy GIS layers are simplified by a Celery task using `shapely.simplify(tolerance=0.5)` before being transferred to mobile IndexedDB, ensuring smooth 60 fps rendering.

---

## 2. Developer Rules of Thumb (Checklist)

| Check | Requirement | Verification Method |
|---|---|---|
| [x] | Next.js redirects use absolute URLs | Grep for `NextResponse.redirect` and check `new URL(..., request.url)` |
| [x] | IndexedDB stores binary data | Check `pwa/src/lib/db.ts` for Blobs in `LocalTiquetDespesa` and `LocalIncidencia` |
| [x] | FastAPI multipart imports present | Grep for `UploadFile, File, Form` in routers accepting photos |
| [x] | RLS tenant context active | Verify `db: AsyncSession = Depends(get_db_with_tenant_context)` on all operari routers |
| [x] | Camera input has anti-fraud tags | Verify `accept="image/*"` and `capture="environment"` in camera inputs |
| [x] | Photos compressed to WebP < 1MB | Check client-side canvas compression pipeline before Dexie write |
| [x] | 3-Phase photos validated on finish | Ensure `PUT /feines/{id}/finalitzar` checks initial, intermedia, and final photos |
| [x] | 4-Color limit on blueprint canvas | Ensure palette is strictly restricted to Red, Blue, Green, Black |
| [x] | Dual photo enforced on fuel refuel | Ensure both receipt and odometer photos are required for fuel category |
