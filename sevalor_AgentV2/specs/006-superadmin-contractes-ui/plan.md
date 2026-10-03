# Implementation Plan: PWA Superadmin and Contractes UI

**Feature Branch**: `[006-superadmin-contractes-ui]`
**Created**: 2026-10-03
**Status**: Draft

## Phase 1: Superadmin Tenants UI (FR-001, FR-002)

1. **Routing & Structure**:
   - Create `pwa/src/app/superadmin/empreses/page.tsx` for the tenant list.
   - Create `pwa/src/app/superadmin/empreses/[id]/page.tsx` for the tenant detail view.

2. **Components**:
   - `TenantList`: A table component fetching from `/api/v1/superadmin/tenants`.
   - `TenantEditor`: A form component allowing modification of:
     - State (`trial`, `actiu`, `suspes`, `baixa`)
     - Plan (`starter`, `pro`, `enterprise`)
     - Module toggles (IA, Telegram)
     - Using `PATCH /api/v1/superadmin/tenants/{id}` (or similar existing endpoint).

## Phase 2: Contractes Gestió UI (FR-003, FR-004, FR-005)

1. **Routing & Structure**:
   - Create `pwa/src/app/(dashboard)/gestio/contractes/page.tsx` for the contract list.
   - Create `pwa/src/app/(dashboard)/gestio/contractes/[id]/page.tsx` for contract details.
   - Create `pwa/src/app/(dashboard)/gestio/contractes/nou/page.tsx` for the creation form.

2. **Components**:
   - `ContractList`: A grid/table displaying active contracts.
   - `ContractForm`: Form integrating with clients API for client selection, capturing cycle details, and submitting to `/api/v1/gestio/contractes`.
   - `ContractDetail`: View showing contract metadata, linked assets (if any), and related work orders.

## Phase 3: Fix Broken Backend Code (Audit C4)

1. **Fix `anotacions_patch.py` and `contractes_tasks.py`**:
   - The audit (C4) noted that `gestio/anotacions_patch.py` and `workers/contractes_tasks.py` have broken imports (0 imports, 38 `F821`).
   - We will implement or delete them depending on if they are actually used by the endpoints. Since `contractes_tasks.py` is mentioned in Spec 05, we must fix its imports and connect it properly to Celery.

## Phase 4: Fix `tasks.md` Citations (Audit C9)

1. **Update `tasks.md` in old specs**:
   - Review Specs 01, 02, 05 and remove checkboxes for components that were never implemented.
   - Ensure paths in `tasks.md` reflect reality (e.g., `tests/api/` vs `tests/`).
