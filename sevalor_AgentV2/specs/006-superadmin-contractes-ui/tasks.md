# Tasks: PWA Superadmin and Contractes UI

**Feature Path**: `specs/006-superadmin-contractes-ui`
**Prerequisites**: `spec.md`, `plan.md`

## Phase 1: Superadmin Tenants UI (P1)

- [ ] T001: Create `TenantList` component and `pwa/src/app/superadmin/empreses/page.tsx` that fetches and displays the list of tenants from the backend API.
- [ ] T002: Create `TenantEditor` component and `pwa/src/app/superadmin/empreses/[id]/page.tsx` that allows changing tenant state, plan, and toggling modules via API PATCH.
- [ ] T003: Integrate the `TenantEditor` with the existing `superadmin` layout/navigation.

## Phase 2: Contractes Gestió UI (P1)

- [ ] T004: Create `ContractList` component and `pwa/src/app/(dashboard)/gestio/contractes/page.tsx` fetching contracts from the API.
- [ ] T005: Create `ContractForm` component and `pwa/src/app/(dashboard)/gestio/contractes/nou/page.tsx` for creating a new contract.
- [ ] T006: Create `ContractDetail` component and `pwa/src/app/(dashboard)/gestio/contractes/[id]/page.tsx` to view contract specifics.

## Phase 3: Fix Broken Backend Code (Audit C4, P1)

- [ ] T007: Review and fix imports and `F821` errors in `backend/app/api/v1/gestio/anotacions_patch.py`. Connect to `main.py` if needed, or safely delete if obsolete.
- [ ] T008: Review and fix imports in `backend/app/workers/contractes_tasks.py`. Ensure it is registered in `celery_app.py`.

## Phase 4: Fix tasks.md Citations (Audit C9, P2)

- [ ] T009: Audit and fix the incorrect paths and fake checkboxes in `specs/01-backoffice-gestio/tasks.md` and `specs/02-frontline-operaris/tasks.md`.
