# Phase 2.5 — Smart Ingestion: Raw Text Extraction + Hybrid Mode — COMPLETE ✅

This document decomposes Phase 2.5 (from REQUIREMENTS.md §17) into six sequential units of work. Each unit has a bounded scope, clear inputs, and testable outputs. Complete them in order — each depends on the prior unit.

Reference: REQUIREMENTS.md §6.1 (AI inference engine — tagged/raw/hybrid), §6.3 (Data Requirements — Company entity `llm_context_mode`), §9.2 (Components — InferenceService two entry points), §9.3 (Data Flow — three extraction modes), §9.5 (InferenceService Contract — raw mode, company context, `RAW_SYSTEM_PROMPT`), §11.1 (companies table — `llm_context_mode` column), §16 (agent instructions).

**Scope boundary — what Phase 2.5 includes:**

- `llm_context_mode` column on `companies` table (Alembic migration + ORM + schemas)
- `BLACKBOOK_LLM_CONTEXT_MAX_CHARS` setting in `config.py`
- `RAW_SYSTEM_PROMPT` and `extract_facts_raw()` in InferenceService
- Company context assembly in IngestionService (`_build_company_context`)
- Extraction mode detection in IngestionService (`process_source` — tagged/raw/hybrid dispatch)
- Source line attribution for raw mode facts
- Frontend: `llm_context_mode` selector in company edit form

**Scope boundary — what Phase 2.5 does NOT include:**

- Changes to PrefixParserService behavior (parsing rules unchanged — Unit 4 adds a `defaulted: bool` field to `ParsedLine` for mode detection, but no parsing behavior changes)
- Changes to ReviewService (unchanged — `save_facts` and accept/dismiss work as before; Unit 5 adds a `raw_lines` parameter to `save_facts` but it defaults to `None` for backward compatibility)
- Changes to pending review queue behavior (unchanged)
- Merge and correct flows (Phase 3)
- Any new API endpoints (existing endpoints gain new behavior)

**Dependency note**: IngestionService needs to query accepted facts and optionally source content for context assembly. It currently holds `CompanyRepository`, `SourceRepository`, and `InferredFactRepository` — no new repository injections needed. New query methods are added to existing repositories.

---

## Unit 1: Database Schema + ORM + Schemas — `llm_context_mode` — COMPLETE ✅

**Goal**: add the `llm_context_mode` column to the `companies` table and expose it through ORM, Pydantic schemas, and the existing API.

- [x] Create Alembic migration: `alembic revision --autogenerate -m "add_llm_context_mode_to_companies"`
  - Add column `llm_context_mode` (text, NOT NULL, server_default `'accepted_facts'`)
  - Verify migration runs cleanly on `blackbook` DB
- [x] Update `backend/app/models/base.py` — `Company` model:
  - Add `llm_context_mode = Column(Text, nullable=False, server_default=text("'accepted_facts'"))`
  - Add to `search_vector` `Computed` expression? **No** — `llm_context_mode` is not searchable content
- [x] Update `backend/app/schemas/company.py`:
  - `CompanyCreate`: **do NOT add `llm_context_mode`** — §10.2 POST /companies payload is `{name, mission, vision}` only; the column's server_default handles new companies; the investigator can update it afterward via PUT
  - `CompanyUpdate`: add `llm_context_mode: str | None = None` — validator restricting to `("none", "accepted_facts", "full")`; optional (omittable for partial update, same pattern as `name`)
  - `CompanyDetailResponse`: add `llm_context_mode: str`
- [x] Update `backend/app/services/company_service.py`:
  - `update_company`: include `llm_context_mode` in the update dict when present in `model_fields_set`
  - `create_company`: no changes needed — server_default handles `llm_context_mode`
- [x] Update `backend/app/repositories/company_repository.py`:
  - `create()`: no changes needed — `llm_context_mode` is not passed at creation time; server_default handles it
- [x] Update `backend/app/config.py`:
  - Add `llm_context_max_chars: int = 8000` to `Settings` (env var: `BLACKBOOK_LLM_CONTEXT_MAX_CHARS`)
- [x] Write tests in `backend/tests/test_repositories/test_unit3_repositories.py` (extend existing):
  - Company create with default `llm_context_mode` → returns `"accepted_facts"` (server_default)
  - Company update `llm_context_mode` from `"accepted_facts"` to `"none"` → persists
  - Company update `llm_context_mode` from `"none"` to `"full"` → persists
- [x] Write tests in `backend/tests/test_api/test_companies.py` (extend existing):
  - `GET /companies/{id}` response includes `llm_context_mode: "accepted_facts"` (default)
  - `PUT /companies/{id}` with `llm_context_mode: "full"` updates correctly
  - `PUT /companies/{id}` with `llm_context_mode: "invalid"` returns 422
  - `POST /companies` creates with default `llm_context_mode: "accepted_facts"` (not settable at creation)
- [x] Run full test suite — all existing tests must still pass

**Why first**: the `llm_context_mode` column and setting are referenced by every subsequent unit. Getting the data model right first prevents rework.

**Rationale**: §6.3 defines `llm_context_mode` on the Company entity. §11.1 specifies the column. The setting `BLACKBOOK_LLM_CONTEXT_MAX_CHARS` is referenced in §9.5 (company context assembly). All must exist before InferenceService or IngestionService can use them.

---

## Unit 2: InferenceService — `RAW_SYSTEM_PROMPT` + `extract_facts_raw()` — COMPLETE ✅

**Goal**: add the raw extraction entry point to InferenceService. Same validation, retry, and output schema as `extract_facts()`. Does NOT write to the database.

- [x] Add `RAW_SYSTEM_PROMPT` constant in `backend/app/services/inference_service.py`:
  - Instruct LLM to read unstructured text and extract all identifiable business facts
  - Same JSON schema as tagged mode (same `category` enum, same `value`/`subordinate`/`manager` fields)
  - Instruct LLM to use company context (if provided) to disambiguate people, teams, and terminology
  - Instruct LLM to avoid extracting facts that duplicate information already in the company context
  - Instruct LLM to return only a JSON array — no prose, no explanation, no markdown wrapper
  - All categories are valid in raw mode (including CGKRA and SWOT — per §6.1 decision)
- [x] Add `_build_raw_system_prompt(company_context: str | None) -> str` private function:
  - If `company_context` is provided, append it to `RAW_SYSTEM_PROMPT` as a clearly delimited section (e.g., `RAW_SYSTEM_PROMPT + "\n\n=== COMPANY CONTEXT ===\n" + context + "\n=== END CONTEXT ==="`)
  - If `company_context` is None, return `RAW_SYSTEM_PROMPT` as-is
  - **Rationale**: §9.5 specifies "Company context is injected into the system prompt when provided." The system prompt is the instruction layer; the user message contains only the source text. This maintains the role boundary that LLM providers model their prompting on.
- [x] Add `async def extract_facts_raw(self, raw_text: str, company_context: str | None = None) -> list[LLMInferredFact]`:
  - Guard: if `raw_text` is empty or whitespace-only, return an empty list (no LLM call needed — IngestionService should not call with empty text, but defensive)
  - Build system prompt: `system_prompt = _build_raw_system_prompt(company_context)`
  - Call `self._call_llm(raw_text, system_prompt=system_prompt)` — user message is just the raw text
  - Validate response via existing `_validate_response(raw_response)`
  - Return validated facts
- [x] Refactor `_call_llm(self, user_message)` → `_call_llm(self, user_message, system_prompt=SYSTEM_PROMPT)`:
  - Add `system_prompt` parameter with default `SYSTEM_PROMPT` (backward compatible)
  - Pass `system_prompt` through to `_call_anthropic` and `_call_openai`
  - Update `_call_anthropic(self, user_message, system_prompt)` and `_call_openai(self, user_message, system_prompt)` signatures accordingly
- [x] Update `InferenceServiceProtocol` in `backend/app/services/ingestion_service.py`:
  - Add `async def extract_facts_raw(self, raw_text: str, company_context: str | None = None) -> list[Any]: ...`
- [x] Write tests in `backend/tests/test_services/test_inference_service.py` (extend existing):
  - `extract_facts_raw` with valid raw text → returns list of `LLMInferredFact`
  - `extract_facts_raw` with empty raw_text → returns empty list (no LLM call made)
  - `extract_facts_raw` with company context → verify context appears in the system prompt (not user message)
  - `extract_facts_raw` without company context → verify system prompt is `RAW_SYSTEM_PROMPT` unmodified; user message is just raw text
  - `extract_facts_raw` uses `RAW_SYSTEM_PROMPT` (not `SYSTEM_PROMPT`) — verify via mock
  - `extract_facts_raw` validation failure (malformed JSON) → raises `InferenceValidationError`
  - `extract_facts_raw` validation failure (empty array) → raises `InferenceValidationError`
  - `extract_facts_raw` validation failure (missing category) → raises `InferenceValidationError`
  - `extract_facts_raw` validation failure (missing value) → raises `InferenceValidationError`
  - `extract_facts_raw` validation failure (unknown category) → raises `InferenceValidationError`
  - `extract_facts_raw` validation failure (relationship without subordinate) → raises `InferenceValidationError`
  - `extract_facts_raw` validation failure (relationship without manager) → raises `InferenceValidationError`
  - `extract_facts_raw` API failure → retries → raises `InferenceApiError`
  - Existing `extract_facts` tests still pass (backward compatible — still uses `SYSTEM_PROMPT`)
- [x] Run full test suite

**Why second**: InferenceService's `extract_facts_raw()` is the core new capability. It must be testable in isolation before IngestionService orchestrates it.

**Rationale**: §9.5 specifies `extract_facts_raw(raw_text, company_context)` as a second entry point sharing the same `_call_llm()` machinery. The system prompt is different because the LLM needs different instructions for unstructured text. Validation and retry are identical per spec.

---

## Unit 3: Context Assembly in IngestionService — `_build_company_context()` — COMPLETE ✅

**Goal**: implement the method that assembles company context for the LLM based on `llm_context_mode`. This is a query-only method with no side effects.

- [x] Add `InferredFactRepository.list_accepted_by_company(company_id, *, limit) -> list[InferredFact]`:
  - Return accepted/corrected facts for a company, ordered by `created_at DESC`
  - Used by context assembly to get the most recent facts first
  - `limit` parameter for pagination (context budget is enforced by the caller, but this prevents loading thousands of rows)
- [x] Add `SourceRepository.list_processed_content(company_id, *, limit) -> list[tuple[str, str | None]]`:
  - Return `(filename_or_subject, raw_content)` tuples for processed sources, ordered by `received_at DESC`
  - Used only when `llm_context_mode == "full"`
  - `limit` parameter to avoid loading unbounded content
- [x] Add `_build_company_context(self, company_id: UUID) -> str | None` to `IngestionService`:
  - Load the company via `self._company_repo.get_by_id(company_id)` to read `llm_context_mode`
  - If `llm_context_mode == "none"`: return None
  - If `llm_context_mode == "accepted_facts"`:
    - Query accepted/corrected facts via `self._inferred_fact_repo.list_accepted_by_company(company_id)`
    - Format as readable text: group by category, list values (e.g., "Known people: Jane Smith (VP Engineering), Bob Jones\nKnown technologies: Kubernetes, Terraform\n...")
    - **Fact-level truncation**: add facts incrementally (newest first); stop when adding the next fact would exceed `self._settings.llm_context_max_chars`; never cut mid-fact
    - Return the formatted string
  - If `llm_context_mode == "full"`:
    - Start with accepted facts (same fact-level truncation as above)
    - Append raw content from processed sources (newest first), each prefixed with source name; stop adding sources when budget is exceeded (never cut mid-source)
    - Total must not exceed `self._settings.llm_context_max_chars`
    - Return the formatted string
  - If the result would be empty (no facts, no sources): return None
- [x] Write tests in `backend/tests/test_services/test_ingestion_service.py` (extend existing):
  - `_build_company_context` with `llm_context_mode="none"` → returns None
  - `_build_company_context` with `llm_context_mode="accepted_facts"` and existing accepted facts → returns formatted string containing fact values
  - `_build_company_context` with `llm_context_mode="accepted_facts"` and no facts → returns None
  - `_build_company_context` with `llm_context_mode="full"` → returns string containing both facts and source content
  - `_build_company_context` respects character budget — stops adding facts when budget would be exceeded; output never ends mid-fact
  - `_build_company_context` orders facts newest-first
  - `_build_company_context` with `llm_context_mode="full"` and no facts AND no sources → returns None
- [x] Write tests in `backend/tests/test_repositories/test_unit3_repositories.py` (extend existing):
  - `list_accepted_by_company`: returns only accepted/corrected facts, ordered by created_at DESC
  - `list_accepted_by_company`: excludes pending/dismissed/merged facts
  - `list_processed_content`: returns only processed sources with raw_content
  - `list_processed_content`: ordered by received_at DESC
- [x] Run full test suite

**Why third**: context assembly is a prerequisite for mode detection (Unit 4). It depends on the `llm_context_mode` column (Unit 1) but not on `extract_facts_raw()` (Unit 2) — however, testing the full pipeline in Unit 4 requires both.

**Rationale**: §9.5 specifies that company context is assembled by IngestionService, not InferenceService. The three modes (`none`, `accepted_facts`, `full`) are defined in §6.3 and §9.5. The character budget (`BLACKBOOK_LLM_CONTEXT_MAX_CHARS`) prevents context overflow.

---

## Unit 4: Extraction Mode Detection + Hybrid Dispatch in IngestionService — COMPLETE ✅

**Goal**: update `process_source()` to detect whether the source is tagged, raw, or hybrid, and dispatch to the appropriate InferenceService method(s). This is the core orchestration change.

- [x] Define mode detection logic in `IngestionService`:
  - After `parse(source.raw_content)` produces a `ParsedSource`:
    - **Tagged lines**: lines where `canonical_key != "n"` (i.e., the investigator explicitly tagged them)
    - **Untagged lines**: lines where `canonical_key == "n"` AND the line was auto-assigned `n:` because it had no recognized prefix (need to distinguish investigator `n:` tags from defaulted lines — see note below)
  - **Mode detection**:
    - If `parsed.lines` is empty (only routing/metadata): no extraction needed, mark source as processed with zero facts
    - If all lines have explicit tags (no defaulted `n:` lines): **tagged mode**
    - If all lines are defaulted `n:` (no explicit tags): **raw mode**
    - If mix of explicitly tagged and defaulted `n:` lines: **hybrid mode**
  - **Important design note**: PrefixParserService currently treats *both* investigator-written `n:` lines and unrecognized/untagged lines as `canonical_key="n"`. To distinguish them for mode detection, add a `defaulted: bool` flag to `ParsedLine`:
    - `defaulted=False`: line had a recognized prefix (including explicit `n:`)
    - `defaulted=True`: line had no recognized prefix and was auto-assigned to `n:`
    - This flag is set by `parse()` in PrefixParserService — minor change, no behavior change for existing code
- [x] Update `backend/app/services/prefix_parser_service.py`:
  - Add `defaulted: bool = False` field to `ParsedLine` dataclass
  - In `parse()`: set `defaulted=True` on lines that had no recognized prefix (unrecognized prefix or no colon)
  - Lines with explicit `n:` or `note:` prefix keep `defaulted=False`
  - All existing tests should still pass (new field defaults to False)
- [x] Update `process_source()` in `backend/app/services/ingestion_service.py`:
  - After parsing, determine mode:
    - `tagged_lines = [l for l in parsed.lines if not l.defaulted]`
    - `untagged_lines = [l for l in parsed.lines if l.defaulted]`
    - `has_tagged = len(tagged_lines) > 0`
    - `has_untagged = len(untagged_lines) > 0`
  - **Tagged mode** (`has_tagged and not has_untagged`):
    - Call `self._inference_service.extract_facts(parsed.lines)` (unchanged from Phase 2)
    - Pass `parsed.lines` to `save_facts` for source line attribution (unchanged)
  - **Raw mode** (`not has_tagged and has_untagged`):
    - Build company context: `context = await self._build_company_context(source.company_id)`
    - Build raw text from untagged lines: `raw_text = "\n".join(l.text for l in untagged_lines)`
    - Call `self._inference_service.extract_facts_raw(raw_text, context)`
    - For source line attribution, pass raw text lines as `ParsedLine` objects (or raw strings — see Unit 5)
  - **Hybrid mode** (`has_tagged and has_untagged`):
    - **Pass 1**: `tagged_facts = await self._inference_service.extract_facts(tagged_lines)`
    - **Pass 2**: Build context, build raw text from untagged lines, `raw_facts = await self._inference_service.extract_facts_raw(raw_text, context)`
    - Combine: `all_facts = tagged_facts + raw_facts`
    - Pass combined facts + all lines to `save_facts` (dedup at save time handles any overlap)
  - **No lines**: mark source as processed (no facts to extract)
- [x] Handle errors: wrap both LLM calls in the existing try/except for `InferenceValidationError` and `InferenceApiError`. In hybrid mode, if either pass fails, the entire source is marked `failed` — no partial persistence. This follows §9.5's failure path: "On any validation failure: the Source status is set to failed." The error message should indicate which pass failed (e.g., "Raw extraction failed: LLM returned invalid JSON")
- [x] Write tests in `backend/tests/test_services/test_ingestion_service.py` (extend existing):
  - Source with all tagged lines → calls `extract_facts()` only, not `extract_facts_raw()`
  - Source with no tags (all defaulted `n:` lines) → calls `extract_facts_raw()` only, not `extract_facts()`
  - Source with mix of tagged and untagged → calls both `extract_facts()` and `extract_facts_raw()`; combined facts passed to `save_facts`
  - Source with only routing/metadata (no content lines) → marked processed with zero facts
  - Hybrid mode: tagged pass succeeds, raw pass fails → source marked failed, no facts persisted (fail-all per §9.5)
  - Hybrid mode: tagged pass fails → source marked failed (raw pass not attempted)
  - Raw mode: context is passed to `extract_facts_raw()` when `llm_context_mode != "none"`
  - Raw mode: context is None when `llm_context_mode == "none"`
  - Raw mode: verify the exact `raw_text` content passed to `extract_facts_raw()` — should be the joined text of defaulted lines, preserving original content
- [x] Write tests in `backend/tests/test_services/test_prefix_parser_service.py` (extend existing):
  - Line with no prefix → `defaulted=True`
  - Line with unrecognized prefix → `defaulted=True`
  - Line with explicit `n:` prefix → `defaulted=False`
  - Line with explicit `note:` prefix → `defaulted=False`
  - Line with any other recognized prefix → `defaulted=False`
  - Existing tests still pass (defaulted field defaults to False)
- [x] Run full test suite

**Why fourth**: this unit wires everything together — mode detection, context assembly (Unit 3), and `extract_facts_raw()` (Unit 2). It depends on all prior units.

**Rationale**: §9.3 defines three extraction modes. The `defaulted` flag on `ParsedLine` is necessary to distinguish investigator-intended `n:` notes (which should go through tagged extraction) from genuinely untagged text (which should go through raw extraction). Hybrid mode follows §9.5's fail-all policy — if either pass fails, the source is marked failed and the investigator can retry.

---

## Unit 5: Source Line Attribution for Raw Mode — COMPLETE ✅

**Goal**: extend source line attribution to work with raw-mode facts, matching against raw text lines instead of `ParsedLine` objects.

- [x] Update `ReviewService.save_facts()` signature and logic:
  - Current signature: `save_facts(source_id, company_id, facts, lines: list[ParsedLine] | None = None)`
  - Add parameter: `raw_lines: list[str] | None = None` — raw text lines for raw-mode attribution
  - New signature: `save_facts(source_id, company_id, facts, lines: list[ParsedLine] | None = None, raw_lines: list[str] | None = None)`
  - Attribution logic:
    - If `lines` is provided: use existing `_match_source_line(fact, lines)` (tagged mode — unchanged)
    - If `raw_lines` is provided: use new `_match_raw_source_line(fact, raw_lines)` (raw mode)
    - If both are provided (hybrid mode): try `_match_source_line` first, fall back to `_match_raw_source_line`
    - If neither: `source_line` is null
- [x] Add `_match_raw_source_line(fact, raw_lines: list[str]) -> str | None` to `ReviewService`:
  - Same matching algorithm as `_match_source_line` (substring match, case-insensitive, first match wins)
  - For relationship facts: match against `subordinate` or `manager`
  - For all others: match against `fact.value`
  - Returns the matched raw line as-is (no `canonical_key:` prefix) per §9.5
  - Returns None if no match
- [x] Update `ReviewServiceProtocol` in `backend/app/services/ingestion_service.py`:
  - Add `raw_lines: list[str] | None = None` parameter to `save_facts` protocol
- [x] Update `IngestionService.process_source()` callers:
  - Tagged mode: `save_facts(source_id, company_id, facts, lines=parsed.lines)` (unchanged)
  - Raw mode: `save_facts(source_id, company_id, facts, raw_lines=raw_text.split("\n"))`
  - Hybrid mode: `save_facts(source_id, company_id, all_facts, lines=tagged_lines, raw_lines=[l.text for l in untagged_lines])`
- [x] Write tests in `backend/tests/test_services/test_review_service.py` (extend existing):
  - `save_facts` with `raw_lines` — raw mode fact matched to originating line
  - `save_facts` with `raw_lines` — no match found → `source_line` is null
  - `save_facts` with both `lines` and `raw_lines` (hybrid) — tagged fact matched via `lines`, raw fact matched via `raw_lines`
  - `save_facts` with `raw_lines` — relationship fact matched against subordinate/manager
  - `_match_raw_source_line` returns raw line as-is (no `canonical_key:` prefix)
  - `save_facts` hybrid attribution ambiguity — fact value appears in both a tagged line and a raw line → tagged match takes precedence (best-effort per §9.5)
- [x] Run full test suite

**Why fifth**: attribution is a read-time concern that doesn't affect extraction correctness. It depends on the `save_facts` call patterns established in Unit 4.

**Rationale**: §9.5 specifies that raw-mode attribution uses the same matching algorithm but returns raw text lines without `canonical_key:` prefix. The hybrid mode falls back to raw matching if tagged matching finds no match, maximizing attribution coverage.

---

## Unit 6: Frontend — `llm_context_mode` Selector — COMPLETE ✅

**Goal**: expose the `llm_context_mode` setting in the company edit form so the investigator can configure context behavior per company.

- [x] Update `frontend/src/types/index.ts`:
  - Add `llm_context_mode: string` to `CompanyDetail` interface
  - Add `llm_context_mode?: string` to `CompanyUpdateInput` interface
  - `CompanyCreateInput`: no change — `llm_context_mode` is not settable at creation time (server default applies)
- [x] Update `frontend/src/pages/CompanyProfilePage.tsx`:
  - Add `editContextMode` state variable (initialized from `company.llm_context_mode`)
  - Add a `<select>` dropdown in the edit form with three options:
    - `none` — "No context"
    - `accepted_facts` — "Accepted facts only (default)"
    - `full` — "Full context (facts + prior sources)"
  - Include `llm_context_mode` in the update payload when saving
  - Display current `llm_context_mode` in the read-only company detail view (label: "LLM Context Mode")
- [x] Verify build: `npm run build` succeeds with no TypeScript errors
- [x] Manual smoke test: edit a company's context mode, verify it persists after reload

**Why last**: frontend changes are cosmetic and have no impact on backend correctness. All backend work must be complete and tested first.

**Rationale**: the investigator needs to be able to configure `llm_context_mode` per company from the UI. The selector is minimal — three radio buttons or a dropdown. No new pages or components needed.

---

## Exit Criteria (Phase 2.5 Complete When All Are True)

- [x] `llm_context_mode` column exists on `companies` table with correct default
- [x] `InferenceService.extract_facts_raw()` extracts facts from raw text with same validation/retry as tagged mode
- [x] `RAW_SYSTEM_PROMPT` instructs LLM for unstructured text extraction with company context
- [x] `IngestionService.process_source()` correctly detects tagged/raw/hybrid mode and dispatches accordingly
- [x] Company context assembly respects `llm_context_mode` and character budget
- [x] Source line attribution works for raw-mode facts (matching against raw text lines)
- [x] Hybrid mode: tagged pass + raw pass combined; if either pass fails, source marked failed (fail-all per §9.5)
- [x] Frontend: company edit form includes `llm_context_mode` selector
- [x] All existing tests pass (backward compatible)
- [x] All new tests pass
- [x] Live test: upload unannotated text file → facts extracted → appear in pending review queue
- [x] Live test: upload mixed file (some tagged, some plain text) → hybrid extraction produces combined facts
