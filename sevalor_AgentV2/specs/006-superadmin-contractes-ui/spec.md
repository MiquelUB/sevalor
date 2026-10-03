# Feature Specification: PWA Superadmin and Contractes UI

**Feature Branch**: `[006-superadmin-contractes-ui]`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Implement missing UI for Superadmin (Lifecycle, Quotas, Toggles, Offboarding) and Contractes (CRUD, details)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Superadmin Tenant Management (Priority: P1)

As a Platform Superadmin, I want a complete dashboard view to manage the lifecycle of tenants, including their license plan, modules, and suspension states, so that I can govern the platform without using API tools.

**Why this priority**: Resolves the "menu without service" complaint (C7) and provides the critical interface for managing the platform's SaaS tenants.

**Independent Test**: Can be tested by navigating to `/superadmin/empreses`, selecting a tenant, changing its state to Suspended, changing its quota, and toggling the AI module.

**Acceptance Scenarios**:

1. **Given** an authenticated Superadmin, **When** they navigate to the tenant list, **Then** they see a table of all tenants with their current states, quotas, and active modules.
2. **Given** the tenant detail view, **When** the Superadmin changes the plan from Starter to Pro, **Then** the UI reflects the new limits and updates via API.
3. **Given** a tenant in active state, **When** the Superadmin suspends the tenant, **Then** the tenant state updates to Suspended.

---

### User Story 2 - Contractes Management for Gestió (Priority: P1)

As a Gestió user (Boss/Enginyer), I want a dedicated section to view, create, and manage maintenance contracts, so that I can leverage the contract functionality already present in the backend.

**Why this priority**: Addresses the complete lack of UI for the Contractes module (C8).

**Independent Test**: Can be fully tested by navigating to `/gestio/contractes`, creating a new maintenance contract for an existing client, and viewing its details.

**Acceptance Scenarios**:

1. **Given** an authenticated Gestió user, **When** they navigate to `/gestio/contractes`, **Then** they see a list of active and pending maintenance contracts with their MRR and next revision dates.
2. **Given** the contract list, **When** the user clicks "Nou Contracte", **Then** a form appears allowing them to link a client, define the billing cycle, and set the revision frequency.
3. **Given** an existing contract, **When** the user clicks on it, **Then** they see the contract details, linked assets, and history of generated work orders.

---

### Edge Cases

- What happens when a Superadmin tries to downgrade a tenant quota below their active users? The UI should display the API error gracefully, indicating the need to remove users first.
- How does the system handle a contract creation without linked assets? It should allow creation but warn the user that no automatic work orders will have asset context.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `/superadmin/empreses` view with a data table listing all tenants and their metadata.
- **FR-002**: System MUST provide a tenant detail view in Superadmin to edit license plans, quotas, state (Trial, Active, Suspended, Baixa), and toggle modules (IA, Telegram, etc.).
- **FR-003**: System MUST provide a `/gestio/contractes` view with a list of maintenance contracts, filterable by state.
- **FR-004**: System MUST provide a form to create/edit contracts, associating them with clients and defining their cyclic properties (billing, revisions).
- **FR-005**: System MUST provide a contract detail view showing the contract's MRR, next revision date, and linked assets.

### Key Entities *(include if feature involves data)*

- **Tenant View State**: Represents the frontend state for managing tenants (list, filters, selected tenant for editing).
- **Contract View State**: Represents the frontend state for the contract CRUD operations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Superadmin can fully manage a tenant's lifecycle and quotas without relying on backend API calls directly.
- **SC-002**: Gestió users can create and manage maintenance contracts entirely through the PWA.
- **SC-003**: No mock data is used in the new UIs; all data is fetched from the existing backend endpoints.

## Assumptions

- Backend endpoints for Superadmin tenant management (FR-015 to FR-019 of Spec 04) are already fully functional and tested.
- Backend endpoints for Contractes (Spec 05) are already fully functional and tested.
- The UI will follow the established Chameleon UI engine and Tailwind conventions of the project.
