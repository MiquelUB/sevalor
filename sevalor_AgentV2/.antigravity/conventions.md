# Sevalor Conventions & Rules

## 1. Zero Mock Data
**MAI S'HA D'UTILITZAR MOCK DATA (dades simulades hardcoded).** Totes les dades de l'aplicació han de provenir exclusivament de crides a l'API del backend (FastAPI). Si un endpoint no existeix, s'ha de crear al backend.

## 2. Llenguatge UI
Tota la interfície d'usuari (UI) del frontend s'ha de redactar i mantenir en **Català**. Les variables del codi i models de dades també estan majoritàriament en català (ex: `OrdreTreball`, `proveidors`, `magatzem`).

## 3. Tech Stack
- **Frontend (Gestió & PWA)**: Next.js (App Router), React, TailwindCSS, `lucide-react` per icones. Fetch natiu amb context d'autenticació i gestió de JWT.
- **Backend**: FastAPI (Python), SQLAlchemy 2.0, PostgreSQL + Supabase.
- **Asincronia**: Celery + Redis per tasques asíncrones.
- **Agent Copilot**: RAG local o via LLM segons configuració (Llama/Mistral) complint amb les normes de sobirania de dades.

## 4. Seguretat i Multi-tenant (RLS)
S'utilitza `tenant_id` amb Row Level Security (RLS) a PostgreSQL per garantir l'aïllament entre diferents empreses/usuaris dins de la mateixa base de dades. Cada taula ha de tenir la columna `tenant_id` i les polítiques adients configurades.

## 5. Codi Font
NO s'ha de moure el codi principal (`backend/`, `pwa/`, `.git`) a subcarpetes que trenquin les rutes dels *scripts* de CI/CD de GitHub Actions, tret que es reconfiguri tot el pipeline.

