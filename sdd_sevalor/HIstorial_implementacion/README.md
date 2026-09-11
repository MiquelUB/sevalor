# SEVALOR Suite v4.0 — Historial d'Implementació i Traçabilitat

Aquest directori recull de manera exhaustiva, atòmica i fidel a la trajectòria del projecte tots els **Plans d'Implementació** (`Implementation_Plan_speccXXX.md`) i els **Walkthroughs d'Auditoria i Verificació** (`Walkthrough_speccXXX.md`) de cadascuna de les 24 especificacions tècniques de la plataforma **SEVALOR Suite v4.0 / CampoPro**.

Tots els mòduls han estat dissenyats i construïts d'acord amb la **Constitució v4.0 de SEVALOR**, complint de manera innegociable:
- **Zero Mock Data**: Estat buit canònic inicial, suport multi-tenant real i dades 100% provinents de PostgreSQL amb RLS.
- **Suport complet per a Mode Clar i Mode Fosc** a totes les vistes d'escriptori (`/gestio`), mòbils (`/operari`) i superadmin (`/superadmin`).
- **Sobirania de Dades Hetzner**: Infraestructura localitzada a la UE (Falkenstein - Alemanya), sense dependències ni sortida de dades a núvols públics privatius (com AWS S3).
- **Human-in-the-Loop (HITL)**: IA Copilot amb veto humà obligatori, sense facturació ni comandes autònomes.
- **Bateria de Proves i Auditoria Automatitzada (100% en verd)**: 87/87 proves backend i 12 suites d'auditoria frontend.

---

## 📑 Índex d'Especificacions i Documents de Traçabilitat (24/24 Specs)

| Especificació | Mòdul / Àrea | Pla d'Implementació | Walkthrough & Auditoria | Estat QA |
|---|---|---|---|---|
| **Spec 001** | Nucli Multi-Tenant, RLS & Dashboard | [`Implementation_Plan_specc001.md`](./Implementation_Plan_specc001.md) | [`Walkthrough_specc001.md`](./Walkthrough_specc001.md) | ✅ Aprovat |
| **Spec 002** | Clients i Finques Rústiques | [`Implementation_Plan_specc002.md`](./Implementation_Plan_specc002.md) | [`Walkthrough_specc002.md`](./Walkthrough_specc002.md) | ✅ Aprovat |
| **Spec 003** | Proveïdors, CAE i Prevenció de Frau BEC | [`Implementation_Plan_specc003.md`](./Implementation_Plan_specc003.md) | [`Walkthrough_specc003.md`](./Walkthrough_specc003.md) | ✅ Aprovat |
| **Spec 004** | Magatzem Central & Inventari Continu | [`Implementation_Plan_specc004.md`](./Implementation_Plan_specc004.md) | [`Walkthrough_specc004.md`](./Walkthrough_specc004.md) | ✅ Aprovat |
| **Spec 005** | Torre de Control GIS & Cockpit Únic | [`Implementation_Plan_specc005.md`](./Implementation_Plan_specc005.md) | [`Walkthrough_specc005.md`](./Walkthrough_specc005.md) | ✅ Aprovat |
| **Spec 006** | Flota i Manteniment ITV | [`Implementation_Plan_specc006.md`](./Implementation_Plan_specc006.md) | [`Walkthrough_specc006.md`](./Walkthrough_specc006.md) | ✅ Aprovat |
| **Spec 007** | Comptabilitat, Tresoreria & Veri*factu | [`Implementation_Plan_specc007.md`](./Implementation_Plan_specc007.md) | [`Walkthrough_specc007.md`](./Walkthrough_specc007.md) | ✅ Aprovat |
| **Spec 008** | Equip, Operaris i Control Horari | [`Implementation_Plan_specc008.md`](./Implementation_Plan_specc008.md) | [`Walkthrough_specc008.md`](./Walkthrough_specc008.md) | ✅ Aprovat |
| **Spec 009** | Notificacions i Canal Telegram | [`Implementation_Plan_specc009.md`](./Implementation_Plan_specc009.md) | [`Walkthrough_specc009.md`](./Walkthrough_specc009.md) | ✅ Aprovat |
| **Spec 010** | Delineació de Plànols GIS & Caixetí Oficial PDF | [`Implementation_Plan_specc010.md`](./Implementation_Plan_specc010.md) | [`Walkthrough_specc010.md`](./Walkthrough_specc010.md) | ✅ Aprovat |
| **Spec 011** | Configuració del Tenant, Jornada & Marca Camaleònica | [`Implementation_Plan_specc011.md`](./Implementation_Plan_specc011.md) | [`Walkthrough_specc011.md`](./Walkthrough_specc011.md) | ✅ Aprovat |
| **Spec 012** | Copilot IA de Camp i Gestió | [`Implementation_Plan_specc012.md`](./Implementation_Plan_specc012.md) | [`Walkthrough_specc012.md`](./Walkthrough_specc012.md) | ✅ Aprovat |
| **Spec 013** | PWA: Agenda, Ruta i Feines d'Obra | [`Implementation_Plan_specc013.md`](./Implementation_Plan_specc013.md) | [`Walkthrough_specc013.md`](./Walkthrough_specc013.md) | ✅ Aprovat |
| **Spec 014** | PWA: Materials, Picking i Sobrants | [`Implementation_Plan_specc014.md`](./Implementation_Plan_specc014.md) | [`Walkthrough_specc014.md`](./Walkthrough_specc014.md) | ✅ Aprovat |
| **Spec 015** | PWA: Control de Flota, Odòmetre i Carburant | [`Implementation_Plan_specc015.md`](./Implementation_Plan_specc015.md) | [`Walkthrough_specc015.md`](./Walkthrough_specc015.md) | ✅ Aprovat |
| **Spec 016** | PWA: Bústia d'Incidències i SOS 112 | [`Implementation_Plan_specc016.md`](./Implementation_Plan_specc016.md) | [`Walkthrough_specc016.md`](./Walkthrough_specc016.md) | ✅ Aprovat |
| **Spec 017** | PWA: Plànols Vectorials i Capes As-Built | [`Implementation_Plan_specc017.md`](./Implementation_Plan_specc017.md) | [`Walkthrough_specc017.md`](./Walkthrough_specc017.md) | ✅ Aprovat |
| **Spec 018** | PWA: Tiquets de Despesa de Camp | [`Implementation_Plan_specc018.md`](./Implementation_Plan_specc018.md) | [`Walkthrough_specc018.md`](./Walkthrough_specc018.md) | ✅ Aprovat |
| **Spec 019** | PWA: Accés, Seguretat Offline i Login PIN | [`Implementation_Plan_specc019.md`](./Implementation_Plan_specc019.md) | [`Walkthrough_specc019.md`](./Walkthrough_specc019.md) | ✅ Aprovat |
| **Spec 020** | PWA: Càmera Tècnica i Evidències WebP | [`Implementation_Plan_specc020.md`](./Implementation_Plan_specc020.md) | [`Walkthrough_specc020.md`](./Walkthrough_specc020.md) | ✅ Aprovat |
| **Spec 021** | Superadmin Tenants, Onboarding Transaccional & Cicle de Vida | [`Implementation_Plan_specc021.md`](./Implementation_Plan_specc021.md) | [`Walkthrough_specc021.md`](./Walkthrough_specc021.md) | ✅ Aprovat |
| **Spec 022** | Tauler de Salut i Telemetria Superadmin SRE | [`Implementation_Plan_specc022.md`](./Implementation_Plan_specc022.md) | [`Walkthrough_specc022.md`](./Walkthrough_specc022.md) | ✅ Aprovat |
| **Spec 023** | Microservei Bot de Telegram per a Clients Finals | [`Implementation_Plan_specc023.md`](./Implementation_Plan_specc023.md) | [`Walkthrough_specc023.md`](./Walkthrough_specc023.md) | ✅ Aprovat |
| **Spec 024** | Workers de Fons, Motor Veri*factu ReportLab i Cues Asíncrones | [`Implementation_Plan_specc024.md`](./Implementation_Plan_specc024.md) | [`Walkthrough_specc024.md`](./Walkthrough_specc024.md) | ✅ Aprovat |
| **General Desktop** | Suite d'Oficina Tècnica (`/gestio`) | [`Implementation_Plan_General_Desktop.md`](./Implementation_Plan_General_Desktop.md) | [`Walkthrough_General_Desktop.md`](./Walkthrough_General_Desktop.md) | ✅ Aprovat |
| **General PWA** | Suite Completa Mòbil Operaris (`/operari`) | [`Implementation_Plan_specc013_a_020_pwa.md`](./Implementation_Plan_specc013_a_020_pwa.md) | [`Walkthrough_specc013_a_020_pwa.md`](./Walkthrough_specc013_a_020_pwa.md) | ✅ Aprovat |
| **Tancament Final** | Certificació Global de la Suite SEVALOR v4.0 | [`Implementation_Plan_Tancament_Final.md`](./Implementation_Plan_Tancament_Final.md) | [`Walkthrough_Tancament_Final.md`](./Walkthrough_Tancament_Final.md) | ✅ Aprovat |

---

## 🧪 Bateries de Proves i Scripts d'Auditoria QA

Totes les implementacions disposen de scripts d'auditoria automatitzada que contrasten els selectors, les regles de negoci i els estats visuals:

- **Proveïdors & CAE (Spec 003)**: `node pwa/test_proveidors_audit.mjs`
- **Flota & ITV (Spec 006)**: `node pwa/test_flota_audit.mjs`
- **Operaris & Control Horari (Spec 008)**: `node pwa/test_operaris_audit.mjs`
- **Notificacions & Telegram (Spec 009)**: `node pwa/test_notificacions_audit.mjs`
- **Plànols GIS & Caixetí PDF (Spec 010)**: `node pwa/test_planols_audit.mjs`
- **Configuració, Jornada & Marca Camaleònica (Spec 011)**: `node pwa/test_configuracio_audit.mjs`
- **Copilot IA (Spec 012)**: `node pwa/test_copilot_audit.mjs`
- **PWA de Camp (Specs 013 a 020)**: `node pwa/test_pwa_audit.mjs`
- **Criptografia Offline PIN (Spec 019)**: `node pwa/test_crypto.mjs`
- **Superadmin Tenants & Onboarding (Spec 021)**: `node pwa/test_tenants_audit.mjs`
- **Superadmin Telemetria (Spec 022)**: `node pwa/test_superadmin_audit.mjs`
- **Bot de Telegram Clients (Spec 023)**: `node pwa/test_bot_telegram_audit.mjs`
- **Central d'Oficina Tècnica Desktop (Specs 001-007)**: `node pwa/test_gestio_audit.mjs`
- **Suite Backend Completa (87/87 proves)**: `python3 backend/run_tests.py`
