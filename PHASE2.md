# Phase 2 — Ingestion Pipeline: Upload + Prefix Parser + LLM Extraction + Pending Review

This document decomposes Phase 2 (from REQUIREMENTS.md §17) into eight sequential units of work. Each unit has a bounded scope, clear inputs, and testable outputs. Complete them in order — each depends on the prior unit.

Reference: REQUIREMENTS.md §5 (UCs 3–5, 16–18), §6.1 (canonical prefix map), §8 (file storage), §9.3 (data flow), §9.5 (InferenceService), §9.6 (PrefixParserService), §9.7 (company routing), §10.3 (source endpoints), §10.4 (pending review endpoints), §11.2–11.7 (data model tables), §16 (agent instructions), §17 (Phase 2 definition).

**Scope boundary — what Phase 2 includes:**

- PrefixParserService (§9.6) — full implementation
- IngestionService with company routing algorithm (§9.7)
- InferenceService (§9.5) — LLM prompt construction, response validation, retry policy
- Source endpoints: POST /sources/upload, GET /companies/{id}/sources, GET /sources/{id}, GET /sources/{id}/status, POST /sources/{id}/retry
- Background worker for async ingestion (ingestion_worker.py)
- Pending review endpoints: GET /companies/{id}/pending, POST .../accept, POST .../dismiss
- Accept flow for ALL categories (person, functional-area, action-item, relationship, technology, process, product, cgkra-*, swot-*, other)
- Dismiss flow
- Frontend: file upload, source list, pending review queue, accepted entities on company profile

**Scope boundary — what Phase 2 does NOT include:**

- Merge and correct flows (Phase 3)
- Disambiguation candidates / fuzzy matching in GET .../pending (Phase 3 — Phase 2 returns empty `candidates` arrays)
- Org chart endpoint and visualization (Phase 3)
- People CRUD endpoints (Phase 3 — Phase 2 creates person records via accept, but does not expose GET/PUT/DELETE /people endpoints)
- Functional area CRUD endpoints (Phase 3)
- Email ingestion / IMAP poller (Phase 6)
- CGKRA views, coverage, search, export (Phases 4–5)

---

## Unit 1: PrefixParserService — COMPLETE ✅

**Goal**: implement the pure-computation prefix parser that normalizes raw source text into a typed `ParsedSource` struct. No I/O, no database, no LLM.

- Create `backend/app/services/prefix_parser_service.py`
  - Define `ParsedLine` dataclass: `canonical_key: str`, `text: str`, `defaulted: bool = False` (True if the line had no recognized prefix and was auto-assigned to `n:`)
  - Define `ParsedSource` dataclass: `nc`, `c`, `cid`, `who`, `date`, `src` (all `str | None`), `lines: list[ParsedLine]`
  - Define `CANONICAL_MAP: dict[str, str]` — the full alias map from §6.1
  - Define routing keys: `{"nc", "c", "cid"}`
  - Define metadata keys: `{"who", "date", "src"}`
  - Implement `parse(raw_text: str) -> ParsedSource`:
    - Split raw text into lines
    - For each non-blank line: check if it begins with `<prefix>:` where `<prefix>` (lowercased, stripped) is in `CANONICAL_MAP`
    - If matched: resolve to canonical key; extract text after the colon (stripped)
    - If canonical key is a routing key (`nc`, `c`, `cid`): store in corresponding `ParsedSource` field
    - If canonical key is a metadata key (`who`, `date`, `src`): store in corresponding `ParsedSource` field
    - If canonical key is `rel`: validate `>` separator is present in text; if absent, emit as `ParsedLine(canonical_key="n", text=<full line>, defaulted=False)` — the investigator used a recognized prefix (just with a syntax error), so `defaulted` remains False for mode detection
    - Otherwise: emit `ParsedLine(canonical_key=<canonical>, text=<text after colon>)`
    - Unrecognized prefix: emit as `ParsedLine(canonical_key="n", text=<full line>, defaulted=True)` and log warning
    - Lines with no colon or no prefix match: emit as `ParsedLine(canonical_key="n", text=<full line>, defaulted=True)`
  - PrefixParserService does NOT: call the LLM, validate routing against DB, enforce exactly-one routing field, split comma-separated values
  - **Known deferral (§6.1)**: the spec requires `CANONICAL_MAP` to be "defined in configuration and modifiable without a code change." Phase 2 hardcodes it as a Python constant — the default map from §6.1. Config-driven loading (via Settings or a JSON file) is deferred to Phase 5 when the Settings page gains real functionality. The current constant serves as the default fallback when that work is done.
- Write exhaustive tests in `backend/tests/test_services/test_prefix_parser_service.py`
  - Every canonical key resolves correctly (one test per alias group: `contact`→`who`, `from`→`who`, `d`→`date`, etc.)
  - Routing fields (`nc`, `c`, `cid`) are extracted into `ParsedSource` fields, NOT into `lines`
  - Metadata fields (`who`, `date`, `src`) are extracted into `ParsedSource` fields, NOT into `lines`
  - All other keys emit into `lines` with correct canonical key
  - Unrecognized prefix treated as `n:` with full line as text
  - Lines without any prefix treated as `n:` with full line as text
  - Blank lines discarded
  - Well-formed `rel:` line (with `>`) emitted normally
  - Malformed `rel:` line (without `>`) emitted as `n:` with full line as text
  - Multiple routing prefixes all stored (validation is IngestionService's job)
  - Prefix matching is case-insensitive (`PERSON:` → `p`)
  - Colon immediately after prefix or with spaces (`tech: Kubernetes` and `tech:Kubernetes` both work)
  - Content after colon is stripped of leading/trailing whitespace

**Why first**: PrefixParserService is pure computation with zero dependencies. Every downstream service (IngestionService, InferenceService) depends on its output. Getting the parser right is the foundation of the pipeline.

**Rationale**: §9.6 specifies that PrefixParserService is the single owner of prefix parsing — no other service re-parses raw text. The `ParsedSource` struct is the contract boundary between parsing and the rest of the pipeline.

---

## Unit 2: InferenceService — LLM Prompt + Validation + Retry — COMPLETE ✅

**Status**: Implementation complete. 59 tests passing. Dependencies wired in `dependencies.py`.

**Goal**: implement the service that constructs the LLM prompt from parsed lines, calls the LLM API with retry, and validates the response. Does NOT write to the database — returns validated facts as Pydantic models.

- [x] Create `backend/app/schemas/inferred_fact.py`
  - [x] Define `LLMInferredFact` Pydantic model: `category: str`, `value: str`, `subordinate: str | None = None`, `manager: str | None = None`
  - [x] Validation: `category` must be in the valid enum; `value` must be non-empty; if `category == "relationship"`, `subordinate` and `manager` must both be non-empty
  - [x] Define request/response schemas for pending review endpoints (GET pending list, accept response, dismiss response) — these will be used in later units
- [x] Create `backend/app/services/inference_service.py`
  - [x] Constructor accepts: LLM provider config (from `settings`), an HTTP client (for dependency injection / mocking in tests)
  - [x] `async def extract_facts(lines: list[ParsedLine]) -> list[LLMInferredFact]`:
    - [x] Construct user message: format each `(canonical_key, text)` pair as `"canonical_key: text"`, one per line
    - [x] Construct system prompt: instruct the LLM to read tagged lines, extract InferredFacts, return only a JSON array (per §9.5)
    - [x] Call LLM API (Anthropic or OpenAI depending on `settings.llm_provider`)
    - [x] On API-level failure: apply retry policy (§9.5):
      - [x] Retry on HTTP 429, 500, 502, 503, 504, network timeout
      - [x] Do NOT retry on HTTP 400, 401
      - [x] Max 3 attempts total (initial + 2 retries)
      - [x] Exponential backoff with jitter: ~1s retry 1, ~2-4s retry 2
      - [x] For HTTP 429: use `Retry-After` header if present
    - [x] On success: validate response:
      1. [x] Parseable as JSON
      2. [x] Top-level is a non-empty array
      3. [x] Every element has a `category` matching the valid enum
      4. [x] Every element has a non-empty `value`
      5. [x] `relationship` elements have non-empty `subordinate` and `manager`
    - [x] On validation failure: raise `InferenceValidationError` with raw LLM response and error description
    - [x] On API failure after retries exhausted: raise `InferenceApiError` with descriptive message
    - [x] On success: return `list[LLMInferredFact]`
- [x] Create domain exceptions in `backend/app/exceptions.py` (or a separate ingestion exceptions section):
  - [x] `InferenceValidationError(DomainError)` — code: `inference_validation_failed`, status: 500
  - [x] `InferenceApiError(DomainError)` — code: `inference_api_failed`, status: 500
- [x] Write tests in `backend/tests/test_services/test_inference_service.py`
  - [x] Mock the HTTP client (never call a real LLM API in tests)
  - [x] Valid LLM response: returns list of `LLMInferredFact` objects
  - [x] Malformed JSON response: raises `InferenceValidationError`
  - [x] Empty array response: raises `InferenceValidationError`
  - [x] Missing `category` field: raises `InferenceValidationError`
  - [x] Missing `value` field: raises `InferenceValidationError`
  - [x] Unknown category: raises `InferenceValidationError`
  - [x] Relationship without `subordinate`: raises `InferenceValidationError`
  - [x] Relationship without `manager`: raises `InferenceValidationError`
  - [x] Valid response with markdown code fence wrapper: test whether service strips it (nice-to-have robustness)
  - [x] HTTP 429 → retries → eventual success
  - [x] HTTP 500 → retries → still fails → raises `InferenceApiError`
  - [x] HTTP 401 → no retry → raises `InferenceApiError` immediately
  - [x] Prompt construction: verify the user message format matches §9.5 (one line per ParsedLine)

**Why second**: InferenceService has a complex contract (§9.5) with validation, retry, and error handling. It depends only on `ParsedLine` from Unit 1. Testing it in isolation with mocked HTTP ensures correctness before wiring into the pipeline.

**Rationale**: §9.5 specifies single-pass extraction, strict validation (reject entire response on any failure), and a precise retry policy. The service must distinguish API-level failures (retryable) from validation failures (not retryable). Per §16, InferenceService never writes to the database — it returns Pydantic models for IngestionService to persist.

---

## Unit 3: Source + InferredFact Repositories — COMPLETE ✅

**Goal**: implement the repository layer for `sources` and `inferred_facts` tables. Pure data access, no business logic.

- Create `backend/app/repositories/source_repository.py`
  - `async def create(session, *, company_id, type, filename_or_subject, raw_content, file_path, who, interaction_date, src) -> Source`
  - `async def get_by_id(session, source_id) -> Source | None`
  - `async def list_by_company(session, company_id, *, status, limit, offset) -> tuple[list[Source], int]` — returns (items, total); ordered by `received_at DESC`; `status` filter (default "all")
  - `async def update_status(session, source_id, *, status, error=None, raw_llm_response=None) -> Source`
- Create `backend/app/repositories/inferred_fact_repository.py`
  - `async def create_many(session, facts: list[dict]) -> list[InferredFact]` — bulk insert
  - `async def get_by_id(session, fact_id) -> InferredFact | None`
  - `async def list_by_company(session, company_id, *, status: str = "pending", category: str | None = None, limit: int, offset: int) -> tuple[list[InferredFact], int]` — filter by `status` (default `'pending'`); optional `category` filter; ordered by `created_at ASC`; returns (items, total)
  - `async def update_status(session, fact_id, *, status, reviewed_at, corrected_value=None, merged_into_entity_type=None, merged_into_entity_id=None) -> InferredFact`
- Create `backend/app/repositories/functional_area_repository.py`
  - `async def create(session, *, company_id, name) -> FunctionalArea`
  - `async def get_by_id(session, area_id) -> FunctionalArea | None`
  - `async def get_by_name_iexact(session, company_id, name) -> FunctionalArea | None` — case-insensitive exact match on `(company_id, lower(name))`; returns the existing row or None
  - `async def list_by_company(session, company_id) -> list[FunctionalArea]`
- Create `backend/app/repositories/person_repository.py`
  - `async def create(session, *, company_id, name, title=None, primary_area_id=None, reports_to_person_id=None) -> Person`
  - `async def get_by_id(session, person_id) -> Person | None`
  - `async def get_by_name_iexact(session, company_id, name) -> list[Person]` — case-insensitive exact match; may return 0, 1, or multiple
  - `async def list_by_company(session, company_id) -> list[Person]`
  - `async def update_reports_to(session, person_id, manager_person_id) -> Person`
- Create `backend/app/repositories/relationship_repository.py`
  - `async def create(session, *, company_id, subordinate_person_id, manager_person_id, inferred_fact_id=None) -> Relationship`
- Create `backend/app/repositories/action_item_repository.py`
  - `async def create(session, *, company_id, description, source_id=None, inferred_fact_id=None, person_id=None, functional_area_id=None) -> ActionItem`
  - `async def get_by_id(session, item_id) -> ActionItem | None`

**Why third**: repositories are pure data access. They are needed by IngestionService (Unit 4) and ReviewService (Unit 5). Building them before the services keeps each unit focused.

**Rationale**: §16 mandates one repository per table, explicit method names, no business logic in repositories. These repositories match the tables from §11.2–11.7. Person and relationship repositories are needed for the accept flow even though full people CRUD endpoints are Phase 3.

---

## Unit 4: IngestionService + Company Routing + Background Worker — COMPLETE ✅

**Goal**: implement the orchestrator that ties PrefixParserService → company routing → InferenceService → fact persistence. Includes the upload endpoint and the background worker.

- Create `backend/app/services/ingestion_service.py`
  - Constructor accepts: `SourceRepository`, `InferredFactRepository`, `CompanyRepository`, `InferenceService`, `ReviewService` (for `save_facts`), `Settings`. NOTE: `PrefixParserService` is not injected — `parse()` is a module-level function imported directly.
  - `async def ingest_upload(file_content: str, filename: str, company_id: str | None = None) -> str`:
    - Parse raw text via PrefixParserService → `ParsedSource`
    - Apply company routing (§9.7):
      - If `company_id` param is provided: treat as `cid:` shortcut; takes precedence over any in-file routing prefix
      - Validate exactly one of `nc`, `c`, `cid` is set (counting the `company_id` param as `cid`)
      - `nc:` — query companies by exact name (case-insensitive); match found → fail `"company name already exists; use c: to route to it"`; no match → create new company
      - `c:` — query companies by exact name (case-insensitive); no match → fail `"no company found with name '{value}'; check spelling or use cid:"`
      - `cid:` — query companies by primary key; no match → fail `"no company found with id '{value}'"`
    - Create Source record: `type='upload'`, `filename_or_subject=filename`, `raw_content=file_content`, `status='pending'`, populate `who`, `interaction_date`, `src` from `ParsedSource` metadata
    - Save uploaded file to `BLACKBOOK_DATA_DIR/sources/{company_id}/{source_id}_{sanitized_filename}`
    - Return `source_id`; actual LLM processing happens asynchronously via background worker
  - `async def process_source(source_id: str) -> None`:
    - Load Source record; set status → `processing`
    - Re-parse raw_content via PrefixParserService (to get `ParsedSource.lines`)
    - Call `InferenceService.extract_facts(parsed_source.lines)`
    - On success: call `ReviewService.save_facts(source_id, company_id, facts, parsed_source.lines)`; set source status → `processed`
    - On `InferenceValidationError`: set source status → `failed`; store raw LLM response and error message on Source record
    - On `InferenceApiError`: set source status → `failed`; store error message on Source record
  - `async def retry_source(source_id: str) -> None`:
    - Load Source record; if status != `failed` → raise `SourceNotFailedError` (409)
    - Reset status → `pending`; clear error and raw_llm_response fields
    - Enqueue for background processing
  - `async def get_source(source_id: str) -> Source`:
    - Return source or raise `SourceNotFoundError` (404)
  - `async def get_source_status(source_id: str) -> str`:
    - Return status string or raise `SourceNotFoundError` (404)
  - `async def list_sources(company_id: str, *, status, limit, offset) -> tuple[list[Source], int]`:
    - Delegate to SourceRepository
  - Helper: `sanitize_filename(name: str) -> str` — strip chars outside `[a-zA-Z0-9._-]`, truncate to 100 chars (§8)
- Create domain exceptions:
  - `RoutingError(DomainError)` — code: `routing_error`, status: 422
  - `SourceNotFoundError(DomainError)` — code: `source_not_found`, status: 404
  - `SourceNotFailedError(DomainError)` — code: `state_conflict`, status: 409
- Implement background worker in `backend/app/workers/ingestion_worker.py`
  - Simple in-process asyncio task queue (per §8 — no Celery, no SQS)
  - `IngestionQueue` class:
    - `async def enqueue(source_id: str) -> None` — add to asyncio.Queue
    - `async def start_worker() -> None` — loop: dequeue source_id, call `IngestionService.process_source(source_id)`, catch and log exceptions (worker must not crash)
  - Wire worker startup in `backend/app/main.py` via FastAPI lifespan event
- Create source Pydantic schemas in `backend/app/schemas/source.py`
  - `SourceUploadResponse`: `source_id: str`, `status: str`
  - `SourceListItem`: `source_id`, `type`, `subject_or_filename` (aliased from `filename_or_subject`), `received_at`, `status`, `error: str | None`
  - `SourceListResponse`: `total`, `limit`, `offset`, `items: list[SourceListItem]`
  - `SourceDetail`: full source fields including `raw_content`, `who`, `interaction_date`, `src`
  - `SourceStatusResponse`: `source_id`, `status`
- Create source route handlers in `backend/app/api/v1/sources.py`
  - `POST /sources/upload` — accept `multipart/form-data` with `file` and optional `company_id`; read file content; call `ingestion_service.ingest_upload()`; enqueue source for background processing; return `SourceUploadResponse`
  - `GET /companies/{id}/sources` — query params: `status`, `limit`, `offset`; return `SourceListResponse`
  - `GET /sources/{id}` — return `SourceDetail`
  - `GET /sources/{id}/status` — lightweight poll; return `SourceStatusResponse`
  - `POST /sources/{id}/retry` — call `ingestion_service.retry_source()`; enqueue; return `SourceUploadResponse`
  - All endpoints require authenticated session (`Depends(get_current_session)`)
- Wire source router into `backend/app/api/v1/router.py`
- Wire dependency providers in `backend/app/dependencies.py`
  - `get_source_repository()`, `get_inferred_fact_repository()`
  - ~~`get_prefix_parser_service()`~~ — **NOT NEEDED**: Unit 1 implemented `parse()` as a module-level function, not a class. IngestionService imports it directly as `from app.services.prefix_parser_service import parse` — no dependency injection required.
  - `get_inference_service()` — needs settings + HTTP client
  - `get_ingestion_service()` — needs all of the above + company_repo + review_service (but NOT prefix_parser_service — it's a direct import)
  - `get_ingestion_queue()` — singleton queue instance
- Write tests in `backend/tests/test_services/test_ingestion_service.py`
  - Routing: `nc:` with new name → creates company, returns source_id
  - Routing: `nc:` with existing name → raises `RoutingError`
  - Routing: `c:` with matching name → routes to company
  - Routing: `c:` with no match → raises `RoutingError`
  - Routing: `cid:` with valid ID → routes to company
  - Routing: `cid:` with invalid ID → raises `RoutingError`
  - Routing: no routing prefix and no company_id → raises `RoutingError`
  - Routing: multiple routing prefixes → raises `RoutingError`
  - Routing: `company_id` param takes precedence over in-file prefix
  - `process_source`: valid flow → source status becomes `processed`, InferredFacts created
  - `process_source`: InferenceValidationError → source status `failed`, error stored
  - `process_source`: InferenceApiError → source status `failed`, error stored
  - `retry_source`: failed source → resets to `pending`
  - `retry_source`: non-failed source → raises `SourceNotFailedError` (409)
  - Filename sanitization: strips invalid chars, truncates
- Write API tests in `backend/tests/test_api/test_sources.py`
  - `POST /sources/upload` with file and `company_id` → 200, source_id returned
  - `POST /sources/upload` without `company_id` and file contains `nc:` → 200
  - `POST /sources/upload` without any routing → 422
  - `GET /companies/{id}/sources` → paginated list
  - `GET /sources/{id}` → source detail
  - `GET /sources/{id}/status` → status only
  - `POST /sources/{id}/retry` on failed source → 200
  - `POST /sources/{id}/retry` on non-failed source → 409

**Why fourth**: this is the core of Phase 2 — the full ingestion pipeline. It depends on PrefixParserService (Unit 1), InferenceService (Unit 2), and all repositories (Unit 3). The background worker is included here because it's tightly coupled to the ingestion flow.

**Rationale**: §9.3 defines the data flow: `IngestionService → PrefixParserService → company routing → InferenceService → ReviewService.save_facts()`. The worker is described in §9.2 as "asyncio tasks running within the same process". File storage follows §8 conventions. The upload endpoint shortcut (`company_id` param → `cid:`) is specified in §9.7.

---

## Unit 5: ReviewService — Accept + Dismiss — COMPLETE ✅

**Goal**: implement the ReviewService that owns the InferredFact lifecycle — saving facts from ingestion, listing pending facts, and processing accept/dismiss actions.

- Create `backend/app/services/review_service.py`
  - Constructor accepts: `InferredFactRepository`, `SourceRepository`, `PersonRepository`, `FunctionalAreaRepository`, `ActionItemRepository`, `RelationshipRepository`
  - `async def save_facts(source_id: str, company_id: str, facts: list[LLMInferredFact], lines: list[ParsedLine]) -> None`:
    - Convert each `LLMInferredFact` to an `inferred_facts` row: `source_id`, `company_id`, `category`, `inferred_value=fact.value`, `status='pending'`
    - For `relationship` facts: store `subordinate` and `manager` values — see "Handle relationship `inferred_value` parsing" below
    - Source line attribution (§9.5): match each fact back to its originating `ParsedLine` to populate `source_line`. For each fact, find the `ParsedLine` whose `text` contains the fact's `value` (substring, case-insensitive); for relationship facts match against `subordinate` or `manager`. Store the matched line formatted as `"canonical_key: text"`. If no match, `source_line` is null.
    - Bulk insert via `InferredFactRepository.create_many()`
  - `async def list_pending(company_id: str, *, status: str = "pending", category: str | None = None, limit: int, offset: int) -> tuple[list, int]`:
    - Query facts via `InferredFactRepository.list_by_company(company_id, status=status, category=category, limit=limit, offset=offset)`
    - For each fact, compute `source_excerpt` per §10.4: if the fact's `source_line` is non-null, use it as the excerpt; otherwise fall back to `"[source] " + source.raw_content[:200]` (loaded via `SourceRepository.get_by_id(fact.source_id)`). NOTE: the fallback path is an N+1 query pattern acceptable at Phase 2 volumes; if performance becomes an issue, enhance the repository method to JOIN sources and return `raw_content` directly.
    - For Phase 2: `candidates` is always an empty array (disambiguation is Phase 3)
    - Return items with `fact_id`, `category`, `inferred_value`, `status`, `source_id`, `source_excerpt`, `candidates: []`
  - `async def accept_fact(company_id: str, fact_id: str) -> str | None`:
    - Load InferredFact; verify `status == 'pending'` and `company_id` matches; raise if not
    - Branch on `category` (per §10.4):
      - `**person`**: parse `inferred_value` — split on first comma: left = `name`, right (stripped) = `title`; no comma → full value is `name`, `title` is null. Create `persons` row via `PersonRepository.create()`. Return the new person's ID.
      - `**functional-area**`: check if a functional area with the same name already exists for this company via `FunctionalAreaRepository.get_by_name_iexact(company_id, inferred_value)`; if found, reuse the existing row (do NOT create a duplicate) and mark the fact accepted; if not found, create a new `functional_areas` row with `name = inferred_value` via `FunctionalAreaRepository.create()`. This handles the `UNIQUE(company_id, name)` constraint — multiple inferred facts referencing the same functional area (common across sources) will not cause an IntegrityError. Return the functional area's ID (new or existing).
      - `**action-item**`: create `action_items` row with `description = inferred_value`, `source_id` from fact's source, `inferred_fact_id = fact_id`, `company_id`, `person_id = null`, `functional_area_id = null` via `ActionItemRepository.create()`. Return the new action item's ID.
      - `**relationship**`: parse `inferred_value` to extract subordinate and manager names. For each name: (1) case-insensitive exact match against persons for this company — exactly one match → use that ID; (2) no match → create stub person (`name`, `title=null`); (3) multiple matches → use first match (Phase 3 will add fuzzy scoring). Insert `relationships` row. Set `persons.reports_to_person_id = manager_person_id` on the subordinate record. Return the new relationship row's ID.
      - **All others** (`technology`, `process`, `product`, `cgkra-`*, `swot-*`, `other`): no entity creation — just mark accepted. Return `None`.
    - Set InferredFact `status = 'accepted'`, `reviewed_at = now()`
  - `async def dismiss_fact(company_id: str, fact_id: str) -> None`:
    - Load InferredFact; verify `status == 'pending'` and `company_id` matches
    - Set `status = 'dismissed'`, `reviewed_at = now()`
- Handle relationship `inferred_value` parsing:
  - §9.5 worked example shows relationship `value` as `"Jane Smith reports to Bob Jones"` with separate `subordinate` and `manager` fields on the LLM output
  - The `inferred_facts` table only has `inferred_value` (text) — no separate subordinate/manager columns
  - DECISION: store the `value` field from LLM output in `inferred_value`. Store subordinate and manager names by encoding them in a parseable format within `inferred_value` (e.g., `"subordinate_name > manager_name"`) OR store the full LLM JSON element and re-parse. The cleanest approach: use the LLM's `value` field as `inferred_value` (human-readable), and store `subordinate` and `manager` as a JSON string in an additional convention. However, the schema has no extra columns — so parse from the human-readable value using a heuristic (look for "reports to") or store as `"subordinate > manager"` format in `inferred_value` for reliable re-parsing at accept time.
  - **Implementation**: store `inferred_value = f"{subordinate} > {manager}"` (matching the `rel:` prefix syntax). This guarantees reliable re-parsing at accept time. The `value` field from LLM output (human-readable summary) is logged but not stored separately. This mirrors the investigator's own `rel:` input syntax and the `correct` endpoint's expected format (§10.4).
- Create domain exceptions:
  - `FactNotFoundError(DomainError)` — code: `fact_not_found`, status: 404
  - `FactNotPendingError(DomainError)` — code: `fact_not_pending`, status: 409
  - `FactCompanyMismatchError(DomainError)` — code: `fact_company_mismatch`, status: 404
- Write tests in `backend/tests/test_services/test_review_service.py`
  - `save_facts`: creates pending InferredFact rows with `source_line` populated via ParsedLine matching
  - `save_facts`: `source_line` is null when no ParsedLine matches the fact's value
  - `list_pending` with default status: returns only pending facts for the company with `source_excerpt` derived from `source_line` (or fallback)
  - `list_pending` with `status='accepted'`: returns only accepted facts
  - `list_pending` with `status='accepted'` and `category='person'`: returns only accepted person facts
  - `accept_fact` — **person**: parses "Jane Smith, VP Engineering" → creates person with name="Jane Smith", title="VP Engineering"
  - `accept_fact` — **person** without comma: "John Doe" → creates person with name="John Doe", title=null
  - `accept_fact` — **functional-area**: creates functional_areas row when name is new
  - `accept_fact` — **functional-area** duplicate: reuses existing row when name matches (case-insensitive), does not raise IntegrityError
  - `accept_fact` — **action-item**: creates action_items row with correct source_id and inferred_fact_id
  - `accept_fact` — **relationship**: resolves names to person IDs; creates relationship row; sets reports_to_person_id
  - `accept_fact` — **relationship** with unknown names: creates stub person records
  - `accept_fact` — **technology**: marks accepted, no entity creation
  - `accept_fact` — **product**: marks accepted, no entity creation
  - `accept_fact` — **cgkra-kp**: marks accepted, no entity creation
  - `accept_fact` — **swot-s**: marks accepted, no entity creation
  - `accept_fact` — **other**: marks accepted, no entity creation
  - `accept_fact` on non-pending fact: raises `FactNotPendingError`
  - `accept_fact` with wrong company_id: raises `FactCompanyMismatchError`
  - `dismiss_fact`: sets status to dismissed, sets reviewed_at
  - `dismiss_fact` on non-pending fact: raises `FactNotPendingError`

**Why fifth**: ReviewService is the second half of the ingestion pipeline — it receives facts from IngestionService (via `save_facts`) and implements the accept/dismiss state machine. It depends on all entity repositories from Unit 3.

**Rationale**: §10.4 defines the full accept branching logic per category. Phase 2 implements accept and dismiss only — merge and correct are Phase 3. The relationship accept flow (§10.4) is the most complex: it involves name resolution, stub person creation, and denormalization updates. This must be correct from the start because accepting relationships creates permanent data.

---

## Unit 6: Pending Review API Endpoints — COMPLETE ✅

**Goal**: expose the pending review queue and accept/dismiss actions via REST.

- Complete `backend/app/schemas/inferred_fact.py` (if not done in Unit 2)
  - `PendingFactItem`: `fact_id`, `category`, `inferred_value`, `status`, `source_id`, `source_excerpt`, `candidates: list` (empty in Phase 2)
  - `PendingFactListResponse`: `total`, `limit`, `offset`, `items: list[PendingFactItem]`
  - `AcceptResponse`: `fact_id`, `status: str` (= "accepted"), `entity_id: str | None` (the ID of the created entity, if any — for `person`: the new person's ID; for `functional-area`: the functional area's ID (new or existing); for `action-item`: the new action item's ID; for `relationship`: the new relationship row's ID; for all other categories: null)
  - `DismissResponse`: `fact_id`, `status: str` (= "dismissed")
- Create route handlers in `backend/app/api/v1/pending.py`
  - `GET /companies/{id}/pending` — query params: `status` (default `"pending"`; valid values: `pending`, `accepted`, `corrected`, `merged`, `dismissed`), `category` (optional), `limit`, `offset`; call `review_service.list_pending()`; return `PendingFactListResponse`. **Extension beyond §10.4**: the `status` query param is not in the original spec, which only lists `limit`, `offset`, and `category`. We add it so the frontend can query accepted facts for profile display without a separate endpoint. The path `/companies/{id}/pending` is retained to match §10.4.
  - `POST /companies/{id}/pending/{fact_id}/accept` — call `entity_id = review_service.accept_fact()`; return `AcceptResponse(fact_id=fact_id, status="accepted", entity_id=entity_id)`
  - `POST /companies/{id}/pending/{fact_id}/dismiss` — call `review_service.dismiss_fact()`; return `DismissResponse`
  - All endpoints require authenticated session
- Wire pending router into `backend/app/api/v1/router.py`
- Wire `get_review_service()` dependency in `backend/app/dependencies.py`
  - Needs: `InferredFactRepository`, `SourceRepository`, `PersonRepository`, `FunctionalAreaRepository`, `ActionItemRepository`, `RelationshipRepository`
- Write API tests in `backend/tests/test_api/test_pending.py`
  - [x] `GET /companies/{id}/pending` (default status=pending) returns pending facts
  - [x] `GET /companies/{id}/pending?category=person` filters by category
  - [x] `GET /companies/{id}/pending?status=accepted` returns accepted facts only
  - [x] `GET /companies/{id}/pending?status=accepted&category=person` returns accepted person facts
  - [x] `GET /companies/{id}/pending` pagination (limit/offset)
  - [x] `GET /companies/{id}/pending?status=garbage` → 422 (Literal validation)
  - [x] `POST .../accept` on a person fact → 200, entity_id returned, round-trip confirmed via `?status=accepted`
  - [x] `POST .../accept` on an action-item fact → 200, entity_id returned, round-trip confirmed
  - [x] `POST .../accept` on a functional-area fact → 200, entity_id returned, round-trip confirmed
  - [x] `POST .../accept` on a relationship fact → 200, entity_id returned, round-trip confirmed
  - [x] `POST .../accept` on a technology fact → 200, `entity_id` is null
  - [x] `POST .../accept` on non-pending fact → 409
  - [x] `POST .../accept` with wrong company_id → 404
  - [x] `POST .../accept` with nonexistent fact_id → 404
  - [x] `POST .../dismiss` → 200, fact dismissed, confirmed gone from pending list
  - [x] `POST .../dismiss` on non-pending fact → 409
  - [x] `POST .../dismiss` with wrong company_id → 404
  - [x] `POST .../dismiss` with nonexistent fact_id → 404
  - [x] All three endpoints return 401 without session cookie (try/finally cookie restore)

**Why sixth**: the API layer is a thin composition layer over ReviewService. It depends on ReviewService (Unit 5) being complete and tested.

**Rationale**: §16 mandates that route handlers contain no business logic — they call services and return responses. The pending endpoint paths match §10.4. The `GET /companies/{id}/pending` endpoint adds a `status` query param beyond what §10.4 specifies — this is a backward-compatible extension (default remains `"pending"`) needed so the frontend can query accepted facts for company profile display without a separate endpoint. Phase 2 only exposes accept and dismiss; merge and correct endpoints will be added in Phase 3.

---

## Unit 7: Frontend — File Upload + Source List + Pending Review Queue — COMPLETE ✅

**Goal**: add file upload, source management, and pending review functionality to the frontend.

- [x] Create frontend API modules:
  - [x] `frontend/src/api/sources.ts`:
    - [x] `uploadSource(file: File, companyId?: string): Promise<SourceUploadResponse>` — uses `apiUpload`
    - [x] `listSources(companyId: string, params?): Promise<SourceListResponse>`
    - [x] `getSource(sourceId: string): Promise<SourceDetail>`
    - [x] `getSourceStatus(sourceId: string): Promise<SourceStatusResponse>`
    - [x] `retrySource(sourceId: string): Promise<SourceUploadResponse>`
  - [x] `frontend/src/api/pending.ts`:
    - [x] `listPending(companyId: string, params?: { status?, category?, limit?, offset? }): Promise<PendingFactListResponse>` — defaults to `status=pending`; also used with `status=accepted` to fetch accepted entities for profile display
    - [x] `acceptFact(companyId: string, factId: string): Promise<AcceptResponse>`
    - [x] `dismissFact(companyId: string, factId: string): Promise<DismissResponse>`
- [x] Add TypeScript types in `frontend/src/types/index.ts`:
  - [x] `SourceUploadResponse`, `SourceListItem`, `SourceListResponse`, `SourceDetail`, `SourceStatusResponse`
  - [x] `PendingFactItem`, `PendingFactListResponse`, `AcceptResponse`, `DismissResponse`
- [x] Create `frontend/src/components/SourceList.tsx`
  - [x] Display sources for a company: filename, type, received date, status
  - [x] Failed sources highlighted with error message and "Retry" button
  - [x] Status polling: while any source is `pending` or `processing`, poll `GET /sources/{id}/status` every 3 seconds and update display
  - [x] Clicking a source shows raw content in an expandable section or modal
- [x] Create `frontend/src/components/PendingReviewQueue.tsx`
  - [x] List pending facts for a company: category badge, inferred value, source excerpt
  - [x] "Accept" button per fact — calls `acceptFact()`, removes from list on success
  - [x] "Dismiss" button per fact — calls `dismissFact()`, removes from list on success
  - [x] Pagination if more than 50 pending facts
- [x] Create file upload component on `CompanyProfilePage.tsx`
  - [x] File input with "Upload Notes" button
  - [x] On upload: call `uploadSource(file, companyId)`, show success message, refresh source list
  - [x] Show upload progress / loading state
- [x] Update `CompanyProfilePage.tsx` to integrate new sections:
  - [x] Replace "People" placeholder with a simple list of accepted persons fetched via `listPending(companyId, { status: 'accepted', category: 'person' })`. **This is a Phase 2 workaround that MUST be replaced in Phase 3** when `GET /companies/{id}/people` is implemented, because this reads from `inferred_facts` (the inferred value) rather than from the `persons` table and will not reflect edits made directly to person records.
  - [x] Replace "Sources" placeholder with `<SourceList companyId={id} />`
  - [x] Add "Pending Review" section with `<PendingReviewQueue companyId={id} />` — shown prominently if `pending_count > 0`
   - [x] Show accepted technologies via `listPending(companyId, { status: 'accepted', category: 'technology' })`, processes via `listPending(companyId, { status: 'accepted', category: 'process' })`, and products via `listPending(companyId, { status: 'accepted', category: 'product' })` as simple lists
  - [x] Show accepted functional areas via `listPending(companyId, { status: 'accepted', category: 'functional-area' })`
- [x] Update `frontend/src/index.css` with styles for:
  - [x] Source list items with status badges (pending=yellow, processing=blue, processed=green, failed=red)
  - [x] Pending review queue with category badges
  - [x] File upload area
  - [x] Accept/dismiss button styles

**Why seventh**: the frontend consumes all the backend work from Units 1–6. It cannot be tested against real data until the backend pipeline is working end-to-end.

**Rationale**: §17 Phase 2 frontend requirements: file upload component, source list (UC 18), pending review queue (UC 5), accepted entities on company profile. The frontend does NOT need merge/correct UI (Phase 3) or fuzzy candidate lists (Phase 3).

---

## Unit 8: Integration Verification + Test Suite Completion — COMPLETE ✅

**Goal**: verify the full end-to-end flow works and all tests pass.

- [x] Write an end-to-end integration test (in `backend/tests/test_api/test_e2e_ingestion.py`):
  - [x] Upload a file with prefix tags (nc:, p:, fn:, tech:, rel:, kp:, a:)
  - [x] Process source with mocked InferenceService returning canned facts
  - [x] Verify InferredFacts were created with correct categories
  - [x] Accept a person fact → verify persons row created
  - [x] Accept a functional-area fact → verify functional_areas row created
  - [x] Accept an action-item fact → verify action_items row created
  - [x] Accept a relationship fact → verify relationship row created, reports_to updated
  - [x] Accept a technology fact → verify marked accepted (no entity)
  - [x] Dismiss a fact → verify status is dismissed
  - [x] Verify company's pending_count decrements as facts are accepted/dismissed
  - [x] Test source list shows processed status after processing
  - [x] Test failed source → retry → re-process → success flow
- [x] Fix: `CompanyService.get_company()` and `update_company()` hardcoded `pending_count: 0` (Phase 1 placeholder) — replaced with `CompanyRepository.get_pending_count()` query
- [x] Verify `uvicorn app.main:app` starts cleanly with the background worker
  - [x] App creates successfully with 21 routes
  - [x] All imports resolve without errors
  - [x] Worker starts and stops via lifespan simulation
- [x] Run full test suite: `pytest` — ALL 367 tests pass (Phase 1 + Phase 2)
  - [x] No regressions in all existing Phase 1 tests
  - [x] All new Phase 2 tests pass
- [ ] Verify frontend manually against running backend (deferred — requires LLM API key configuration)
- [x] Verify test isolation:
  - [x] Run `pytest` twice in a row — both runs pass (367 + 367)
  - [x] No leftover data between test runs (savepoint pattern from Phase 1 conftest)

**Why last**: integration verification catches wiring issues, missing imports, and incorrect assumptions between units. It also validates that Phase 1 functionality is preserved (no regressions).

**Rationale**: §17 Phase 2 exit criteria: "investigator can upload a document with prefix tags, the system extracts facts, the investigator can review and accept/dismiss them, and accepted facts appear in the company profile." This unit verifies that exact flow.

---

## Exit Criteria (from REQUIREMENTS.md §17 Phase 2)

All of the following are true:

- [x] PrefixParserService correctly normalizes all canonical keys, aliases, routing fields, and metadata (Unit 1 — 92 tests)
- [x] InferenceService constructs correct LLM prompts, validates responses, and applies retry policy (Unit 2 — 59 tests)
- [x] Company routing (nc/c/cid) works correctly with proper error messages on failure (Unit 4 — 12 routing tests)
- [x] File upload stores the file and creates a Source record (Unit 4 — service + API tests)
- [x] Background worker processes sources asynchronously (LLM extraction via InferenceService) (Unit 4 — 4 worker tests)
- [x] Failed sources are surfaced with error messages; retry re-enters the queue (Unit 4 — service + API tests)
- [x] Pending review queue lists all pending InferredFacts for a company (Unit 5 service + Unit 6 API — list_pending tests)
- [x] Accept flow works correctly for ALL categories: person (name+title parse), functional-area (create row), action-item (promote to action_items), relationship (name resolution + stub creation), all others (mark accepted) (Unit 5 — 16 accept tests + Unit 6 API tests)
- [x] Dismiss flow marks InferredFacts as dismissed (Unit 5 + Unit 6)
- [x] Company profile page shows: file upload, source list with status, pending review queue, accepted people/technologies/processes/products (Unit 7 — frontend build verified)
- [x] All pytest tests pass (Phase 1 + Phase 2), repeatable across runs (367 passing)
- [x] No regressions in Phase 1 functionality

