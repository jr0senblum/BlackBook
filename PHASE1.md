# Phase 1 — Foundation: Data Model + Auth + Company CRUD + Frontend Scaffold — COMPLETE ✅

This document decomposes Phase 1 (from REQUIREMENTS.md §17) into five sequential units of work. Each unit has a bounded scope, clear inputs, and testable outputs. Complete them in order — each depends on the prior unit.

Reference: REQUIREMENTS.md §10 (API), §11 (Data Model), §16 (Agent Instructions), §17 (Phase 1 definition).

---

## Unit 1: ORM Models + Alembic Migration — COMPLETE ✅

- [x] Define all SQLAlchemy ORM models in `backend/app/models/base.py` matching §11 exactly
  - All 11 tables: `companies`, `functional_areas`, `persons`, `sources`, `inferred_facts`, `relationships`, `action_items`, `cgkra_templates`, `generated_documents`, `sessions`, `credentials`
  - All columns, types, NOT NULL constraints, defaults, CHECK constraints
  - All foreign keys with CASCADE/SET NULL behavior per §11
  - All indexes (unique, GIN for tsvector, composite)
  - `search_vector` generated columns on `companies`, `persons`, `sources`, `inferred_facts`, `action_items`
- [x] Update `backend/alembic/env.py` to import `Base.metadata` for autogenerate support
- [x] Generate the initial Alembic migration
- [x] Verify: `alembic upgrade head` succeeds against a real PostgreSQL database
- [x] Verify: `alembic downgrade base` succeeds cleanly

**Why first**: everything else depends on the schema. Getting it wrong here cascades everywhere.

---

## Unit 2: Auth (Full Vertical Slice) — COMPLETE ✅

- [x] Implement `CredentialRepository` (`backend/app/repositories/credential_repository.py`)
  - `get_credential()`, `create_credential()`, `update_password_hash()`
- [x] Implement `SessionRepository` (`backend/app/repositories/session_repository.py`)
  - `create_session()`, `get_by_token()`, `update_last_active()` (touch `last_active_at` to now for rolling timeout per §7.3), `delete_by_token()`, `delete_expired()`
- [x] Implement auth Pydantic schemas (`backend/app/schemas/auth.py`)
  - Request/response models for password set, login, logout, password change
- [x] Implement `AuthService` (`backend/app/services/auth_service.py`)
  - `set_password()` — first-time only, 409 if already set
  - `login()` — validate credentials, create session, return session token
  - `logout()` — delete session
  - `change_password()` — validate current password, update hash
  - `validate_session()` — check token exists and is not expired per §7.3 timeout
- [x] Implement domain exceptions for auth (in `backend/app/exceptions.py` or auth-specific)
  - `CredentialsAlreadySetError` (409), `InvalidCredentialsError` (401), `InvalidCurrentPasswordError` (401, code `invalid_current_password` — for password change), `SessionExpiredError` (401)
- [x] Implement route handlers (`backend/app/api/v1/auth.py`)
  - `POST /auth/password/set`
  - `POST /auth/login` — sets `session` cookie (HttpOnly, Secure, SameSite=Strict per §7.3)
  - `POST /auth/logout`
  - `POST /auth/password/change`
- [x] Implement session middleware in `backend/app/dependencies.py`
  - `get_current_session()` dependency that reads the `session` cookie, validates via AuthService (checks expiry, updates `last_active_at` on success), and raises 401 if invalid/expired
- [x] Implement `config.py` (`backend/app/config.py`) — Pydantic Settings class covering all required configuration:
  - `DATABASE_URL` — PostgreSQL connection string
  - `BLACKBOOK_DATA_DIR` — root path for file storage (§8)
  - `SESSION_TIMEOUT_MINUTES` — inactivity timeout (default 30, per §7.3)
  - `LLM_API_KEY` and `LLM_PROVIDER` — API key and provider selection (Anthropic or OpenAI)
  - Settings loaded from environment variables and/or a local `.env` file; never hardcoded
- [x] Implement the error envelope and exception handler
  - Global FastAPI exception handler that catches `DomainError` subclasses and returns the error response format from §10
- [x] Implement database session dependency in `backend/app/dependencies.py`
  - `get_db()` async dependency providing a SQLAlchemy AsyncSession per request
- [x] Write tests (`backend/tests/test_services/test_auth_service.py`, `backend/tests/test_api/test_auth.py`)
  - AuthService: login, logout, session expiry, password set idempotency (409), password change with wrong current password (401)
  - API tests: all 4 auth endpoints via TestClient
- [x] Write test fixtures in `backend/tests/conftest.py`
  - Test database setup/teardown, TestClient, authenticated session fixture

**Why second**: every subsequent endpoint needs the session middleware. Building auth first means all later work can assume authentication is in place.

---

## Unit 3: Company CRUD (Full Vertical Slice) — COMPLETE ✅

- [x] Implement `CompanyRepository` (`backend/app/repositories/company_repository.py`)
  - `create()`, `get_by_id()`, `get_by_name_iexact()`, `list_all()` (with pagination: limit/offset), `update()`, `delete()`
  - `list_all()` returns `pending_count` (count of inferred_facts with status='pending' per company); ordered by `name` ascending per §10.2
- [x] Implement company Pydantic schemas (`backend/app/schemas/company.py`)
  - `CompanyCreate`, `CompanyUpdate`, `CompanyDetailResponse` (flat: id, name, mission, vision, llm_context_mode, created_at, updated_at, pending_count — NOT the full §10.2 composition shape; people, CGKRA, coverage, and functional areas are added in later phases), `CompanyListResponse` (paginated)
- [x] Implement `CompanyService` (`backend/app/services/company_service.py`)
  - `create_company()` — exact case-insensitive duplicate name check, block with 409 `name_conflict`
  - `get_company()` — 404 `company_not_found` if missing
  - `list_companies()` — paginated
  - `update_company()` — 404 if missing; 409 `name_conflict` if rename collides with an existing company name (case-insensitive)
  - `delete_company()` — 404 if missing; CASCADE handles related data
- [x] Implement domain exceptions for companies (in `backend/app/exceptions.py`)
  - `CompanyNotFoundError` (404), `CompanyNameConflictError` (409)
- [x] Implement route handlers (`backend/app/api/v1/companies.py`)
  - `GET /companies` — paginated list
  - `POST /companies` — manual create
  - `GET /companies/{id}`
  - `PUT /companies/{id}`
  - `DELETE /companies/{id}`
  - All endpoints require authenticated session (use `Depends(get_current_session)`)
- [x] Write tests (`backend/tests/test_services/test_company_service.py`, `backend/tests/test_api/test_companies.py`)
  - CompanyService: create, duplicate name (409), list, get, update, delete cascade
  - API tests: all 5 company endpoints via TestClient (authenticated)

**Why third**: depends on auth middleware being in place. Self-contained otherwise.

---

## Unit 4: Backend Integration Verification — COMPLETE ✅

- [x] Wire auth router into `backend/app/api/v1/router.py`
- [x] Wire companies router into `backend/app/api/v1/router.py`
- [x] Wire all dependencies in `backend/app/dependencies.py`
  - Database engine + async session factory
  - Service instantiation via `Depends()`
- [x] Verify `uvicorn app.main:app` starts and connects to PostgreSQL
- [x] Verify end-to-end flow manually or via a smoke test:
  - `POST /api/v1/auth/password/set` → `POST /api/v1/auth/login` → `GET /api/v1/companies` returns 200 with empty list
  - `POST /api/v1/companies` creates a company → `GET /api/v1/companies` returns it
- [x] Run full test suite: `pytest` — all tests pass

**Why separate**: each prior unit wrote its own layer; this step connects them. Doing it as a distinct task prevents earlier units from making incompatible wiring assumptions.

---

## Unit 5: Frontend Scaffold (React Pages + API Client) — COMPLETE ✅

- [x] Flesh out `frontend/src/api/client.ts`
  - Handle `multipart/form-data` requests (for future file uploads)
  - Handle non-JSON responses gracefully
- [x] Flesh out `frontend/src/api/auth.ts` — already stubbed with typed functions
- [x] Implement `frontend/src/api/companies.ts`
  - `listCompanies()`, `createCompany()`, `getCompany()`, `updateCompany()`, `deleteCompany()`
- [x] Define shared types in `frontend/src/types/index.ts`
  - `Company`, `CompanyListResponse`, `ApiError`
- [x] Implement `LoginPage` (`frontend/src/pages/LoginPage.tsx`)
  - Login form; first-time password set form (detect via failed login or dedicated check)
  - On success, redirect to company list
- [x] Implement `CompanyListPage` (`frontend/src/pages/CompanyListPage.tsx`)
  - Fetch and display all companies with pending counts
  - "New Company" button → create form
  - Click company → navigate to profile
- [x] Implement `CompanyProfilePage` (`frontend/src/pages/CompanyProfilePage.tsx`)
  - Display company fields (name, mission, vision)
  - Edit form for company fields (UC 17)
  - Placeholder sections for people, CGKRA, coverage, sources (labeled "Phase 2/3/4")
  - Delete company button with confirmation
- [x] Implement `SettingsPage` (`frontend/src/pages/SettingsPage.tsx`)
  - Password change form
- [x] Implement session-aware routing in `App.tsx`
  - Unauthenticated users redirect to `/login`
  - Add navigation (company list, settings, logout)
  - Add routes for settings page
- [x] Verify manually against running backend:
  - Log in, create companies, view list, open profile, edit fields, change password

**Why last**: the backend must be running and serving real responses before the frontend can be tested against it.

---

## Exit Criteria (from REQUIREMENTS.md §17 Phase 1)

All of the following are true:

- [x] All Alembic migrations apply and roll back cleanly
- [x] All pytest tests pass
- [x] Investigator can log in and set their password on first use
- [x] Investigator can create, view, edit, and delete companies
- [x] Investigator can view the company list with pending counts (all zero at this phase)
- [x] Investigator can open a company profile and edit its fields
- [x] Investigator can change their password
- [x] The application is deployable and runnable via `uvicorn` + `npm run dev`
