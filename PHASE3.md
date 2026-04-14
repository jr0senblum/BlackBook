# Phase 3 — Full Review Flow + Org Chart + Person Management

This document decomposes Phase 3 (from REQUIREMENTS.md §17) into ten sequential units of work. Each unit has a bounded scope, clear inputs, and testable outputs. Complete them in order — each depends on the prior unit.

Reference: REQUIREMENTS.md §5 (UCs 5–6, 17), §6.1 (entity disambiguation), §6.3 (entity definitions), §9.2 (component architecture, ReviewService delegation), §10.4 (merge/correct endpoints), §10.5 (people + org chart), §10.6 (functional areas), §11.2–11.7 (data model tables), §16 (agent instructions), §17 (Phase 3 definition).

**Scope boundary — what Phase 3 includes:**

- Merge flow per §10.4: person merge, functional-area merge, 422 for all other categories
- Correct flow per §10.4: person correct (parse name+title), functional-area correct (always create new row), action-item correct, relationship correct (parse `subordinate > manager`, name resolution), all others (store corrected_value, no entity creation)
- Disambiguation candidates: fuzzy matching for `GET .../pending` — ranked candidates per category (person, functional-area, relationship)
- People endpoints: `GET /companies/{id}/people`, `POST /companies/{id}/people`, `GET/PUT/DELETE /companies/{id}/people/{person_id}`
- Org chart endpoint: `GET /companies/{id}/orgchart` — roots, unplaced, recursive tree
- Functional area endpoints: `GET/POST/PUT/DELETE /companies/{id}/areas/*`
- In-place editing of accepted entities (UC 17): PUT endpoints for people, functional areas, and accepted inferred facts (corrected_value editing)
- ReviewService architectural refactor: delegate entity creation to domain services (PersonService, FunctionalAreaService, etc.) per §9.2 — resolve Phase 2 architectural debt
- Frontend: merge + correct UI in pending review queue, org chart visualization, person detail, functional area views, edit forms for all accepted entities

**Scope boundary — what Phase 3 does NOT include:**

- CGKRA aggregation endpoints and views (Phase 4 — AreaDetail will include an empty `cgkra` stub field as a forward-compatibility placeholder)
- Coverage dashboard (Phase 4)
- Search endpoint and page (Phase 4)
- Export / generated documents (Phase 5)
- Email ingestion / IMAP poller (Phase 6)
- Settings page real functionality / config-driven canonical map (Phase 5)

---

## Unit 1: PersonService + FunctionalAreaService (Domain Services for Entity Creation) — COMPLETE ✅

**Goal**: create dedicated domain services that own entity creation logic, satisfying §9.2's requirement that ReviewService delegates to domain services rather than calling repositories directly. This refactors Phase 2's architectural debt before adding merge/correct.

- [x] Create Alembic migration for schema changes since Phase 2.5:
  - Add `notes` column (text, nullable) to `functional_areas`
  - Add `updated_at` column (timestamptz, NOT NULL, server_default `now()`) to `functional_areas`
  - Add `'product'` to the `inferred_facts.category` CHECK constraint
  - Add `'prod'` to `CANONICAL_MAP` in `prefix_parser_service.py` and `'product'` to the valid category set in `inference_service.py` (code changes, not migration — but must be done alongside the migration)
  - Update ORM model in `models/base.py` to match
  - Fix `session_timeout_minutes` default in `backend/app/config.py`: change `5` to `30` per REQUIREMENTS.md §10.1 / PHASE1.md fix
  - Verify migration runs cleanly on `blackbook` DB
- [x] Create `PersonService` in `backend/app/services/person_service.py` (new file):
  - Constructor: `person_repo: PersonRepository`, `functional_area_repo: FunctionalAreaRepository`, `action_item_repo: ActionItemRepository`, `inferred_fact_repo: InferredFactRepository`
  - `create_person(company_id: UUID, *, name: str, title: str | None = None, primary_area_id: UUID | None = None, reports_to_person_id: UUID | None = None) -> Person` — insert new person row
  - `create_person_from_value(company_id: UUID, value: str) -> Person` — parse `value` by splitting on first comma (left = name, right = title); if no comma, full value is name, title is null; delegates to `create_person()`. Used by `correct_fact` (always creates a new person — the investigator explicitly chose correct over merge).
  - `get_or_create_person_from_value(company_id: UUID, value: str) -> Person` — same parse logic as `create_person_from_value`, but deduplicates: check `get_by_name_iexact(company_id, name)` first; if a match exists, reuse it (and back-fill title if the existing person has none and the fact provides one); if no match, create new. This preserves Phase 2's `_accept_person` dedup+backfill behavior. Used by `accept_fact`.
  - `resolve_person(company_id: UUID, name: str) -> UUID` — name resolution algorithm from §10.4: (1) case-insensitive exact match — if exactly one, use it; (2) multiple matches — use first (Phase 3 adds fuzzy scoring later via disambiguation, but resolution at accept time still uses first match); (3) no match — create stub person
  - `list_people(company_id: UUID) -> list[Person]` — delegates to `person_repo.list_by_company()`
  - `get_person(company_id: UUID, person_id: UUID) -> dict` — enriched with area name, reports_to name, action items, linked inferred facts
  - `update_person(company_id: UUID, person_id: UUID, **fields) -> Person` — update specified fields. **Note**: depends on `PersonRepository.update()` which is added in Unit 5. Implement as a stub (`raise NotImplementedError`) in Unit 1; complete in Unit 5 when the repository method is available.
  - `delete_person(company_id: UUID, person_id: UUID) -> None` — **Note**: depends on `PersonRepository.delete()` which is added in Unit 5. Implement as a stub in Unit 1; complete in Unit 5.
- [x] Create `FunctionalAreaService` in `backend/app/services/functional_area_service.py` (new file):
  - Constructor: `area_repo: FunctionalAreaRepository`, `person_repo: PersonRepository`, `action_item_repo: ActionItemRepository`
  - `create_area(company_id: UUID, name: str, *, notes: str | None = None) -> FunctionalArea` — insert new row; **does NOT deduplicate** (spec says "create new" for both accept and correct; the UNIQUE constraint on `(company_id, name)` will raise IntegrityError if a true duplicate is created — this is the correct behavior per spec; the investigator's tool for linking to an existing area is merge)
  - `create_area_safe(company_id: UUID, name: str) -> FunctionalArea` — deduplicating variant used only by `accept_fact` (Phase 2 behavior preserved to prevent UNIQUE constraint violations on accept; the distinction: accept deduplicates because the investigator chose "accept as-is" and an exact name match is a clear duplicate; correct does NOT deduplicate because the investigator explicitly typed a corrected value and chose correct over merge)
  - `list_areas(company_id: UUID) -> list[FunctionalArea]`
  - `get_area(company_id: UUID, area_id: UUID) -> dict` — enriched with people assigned to this area, action items, and notes
  - `update_area(company_id: UUID, area_id: UUID, *, name: str | None = None, notes: str | None = None) -> FunctionalArea` — check for name conflict before renaming; update notes if provided
  - `delete_area(company_id: UUID, area_id: UUID) -> None`
- [x] Add domain exceptions to `backend/app/exceptions.py`:
  - `PersonNotFoundError` — code `person_not_found`, status 404
  - `PersonCompanyMismatchError` — code `person_company_mismatch`, status 404
  - `AreaNotFoundError` — code `area_not_found`, status 404
  - `AreaNameConflictError` — code `area_name_conflict`, status 409
- [x] Refactor `ReviewService` to delegate entity creation:
  - Add `PersonService` and `FunctionalAreaService` to constructor (alongside existing repos it still owns: `InferredFactRepository`, `SourceRepository`)
  - Remove direct usage of `PersonRepository`, `FunctionalAreaRepository`, `ActionItemRepository`, `RelationshipRepository` from ReviewService constructor — these are now owned by the domain services
  - **Exception**: ReviewService still needs `RelationshipRepository` directly for relationship accept/correct (there is no dedicated RelationshipService in the spec). Keep it as a constructor dependency.
  - **Exception**: ReviewService still needs `ActionItemRepository` directly for action-item accept/correct (no ActionItemService in the spec yet — §9.2 mentions it but §17 Phase 3 doesn't define it as a separate unit). Keep it temporarily; extract to ActionItemService if/when the spec adds action-item CRUD endpoints.
  - Refactor `_accept_person` → calls `person_service.get_or_create_person_from_value()` (preserves dedup+backfill)
  - Refactor `_accept_functional_area` → calls `functional_area_service.create_area_safe()`
  - Refactor `_resolve_person` → calls `person_service.resolve_person()`
  - Keep `_accept_action_item` and `_accept_relationship` using repos directly (no domain service exists for these yet)
- [x] Update `dependencies.py`:
  - `_build_review_service()` now constructs PersonService and FunctionalAreaService and passes them to ReviewService
  - Add `get_person_service(db) -> PersonService` and `get_functional_area_service(db) -> FunctionalAreaService` for future route DI
- [x] Write tests:
  - `backend/tests/test_services/test_person_service.py` (new file):
    - `test_create_person` — creates person with name and title
    - `test_create_person_from_value_with_comma` — "Jane Smith, VP" -> name="Jane Smith", title="VP"
    - `test_create_person_from_value_without_comma` — "Jane Smith" -> name="Jane Smith", title=None
    - `test_get_or_create_person_dedup_existing` — existing person with same name (case-insensitive) -> reuses existing row
    - `test_get_or_create_person_backfill_title` — existing person with no title, fact has title -> title back-filled
    - `test_get_or_create_person_no_match_creates` — no match -> creates new person
    - `test_resolve_person_exact_match` — one match -> returns existing ID
    - `test_resolve_person_multiple_matches_uses_first` — multiple matches -> first
    - `test_resolve_person_no_match_creates_stub` — no match -> creates stub
  - `backend/tests/test_services/test_functional_area_service.py` (new file):
    - `test_create_area` — creates new area
    - `test_create_area_safe_deduplicates` — existing name (case-insensitive) -> returns existing ID
    - `test_create_area_no_dedup` — `create_area()` does NOT deduplicate (will raise IntegrityError on exact duplicate)
  - Update existing `test_review_service.py` tests to verify delegation works (existing tests should still pass after refactor)
- [x] Run full test suite — 456 tests passing (444 existing + 12 new)

**Why first**: §9.2 requires ReviewService to delegate to domain services. Phase 2 violated this for pragmatic reasons (domain services didn't exist yet). Phase 3 introduces PersonService and FunctionalAreaService — creating them first gives merge/correct (Unit 2) the right delegation targets from the start, rather than adding more debt and refactoring later.

**Rationale**: §9.2 line 442: "on accept/correct, delegates entity creation to the appropriate domain service (PersonService, ActionItemService, etc.) — never calls another service's repository directly." This unit partially resolves Phase 2 architectural debt by extracting PersonService and FunctionalAreaService. Full §9.2 compliance (ActionItemService, RelationshipService) is deferred — these categories lack dedicated CRUD endpoints in Phase 3, making full extraction premature.

---

## Unit 2: Merge + Correct in ReviewService

**Goal**: extend ReviewService with `merge_fact()` and `correct_fact()` methods, implementing the full §10.4 merge and correct specifications. Delegates entity creation to domain services from Unit 1.

- [ ] Add new domain exceptions to `backend/app/exceptions.py`:
  - `MergeNotApplicableError` — code `merge_not_applicable`, status 422, message "Merge is not supported for this category"
  - `InvalidCorrectedValueError` — code `invalid_corrected_value`, status 422, message "Corrected value is invalid for this category"
  - `MergeTargetNotFoundError` — code `merge_target_not_found`, status 404, message "Merge target entity not found"
- [ ] Extend `ReviewService` in `backend/app/services/review_service.py`:
  - `merge_fact(company_id: str, fact_id: str, target_entity_id: str) -> None`
    - Validate fact exists, belongs to company, is pending (same guards as accept/dismiss)
    - Branch on `category`:
      - `person`: verify `target_entity_id` is an existing person for this company via `person_service.get_person()` or direct repo check + company_id guard; if not found, raise `MergeTargetNotFoundError`; call `inferred_fact_repo.update_status()` with `status="merged"`, `merged_into_entity_type="person"`, `merged_into_entity_id=target_entity_id`
      - `functional-area`: verify target is an existing functional area for this company via `functional_area_service` or repo check + company_id guard; if not found, raise `MergeTargetNotFoundError`; update status with `merged_into_entity_type="functional_area"`
      - All other categories (`relationship`, `action-item`, `technology`, `process`, `product`, `cgkra-*`, `swot-*`, `other`): raise `MergeNotApplicableError`
  - `correct_fact(company_id: str, fact_id: str, corrected_value: str) -> str | None`
    - Validate fact exists, belongs to company, is pending
    - Branch on `category`:
      - `person`: delegate to `person_service.create_person_from_value(company_id, corrected_value)` (always creates new — correct is not dedup'd); the new person is created with the parsed name and title from `corrected_value`; update fact with `status="corrected"`, `corrected_value=corrected_value`; return person ID. **Note**: correct does NOT mutate an existing person row — it creates a new person entity. The `corrected_value` on the fact records what the investigator intended.
      - `functional-area`: delegate to `functional_area_service.create_area(company_id, corrected_value)` — **no deduplication** per §10.4 ("create new functional_areas row with name = corrected_value"); if the investigator wanted to link to an existing area, they should have used merge; **wrap in try/except for IntegrityError** — if the corrected name collides with an existing area's `(company_id, name)` UNIQUE constraint, catch `IntegrityError` and raise `AreaNameConflictError` (409) so the investigator knows to use merge instead; update fact status; return area ID
      - `action-item`: create new action item with `description=corrected_value` via `action_item_repo`; same dedup rule as accept — if an open action item with the same description (case-insensitive) already exists for this company, reuse the existing row (do NOT update the existing row's description); if no match, create new row with `description=corrected_value`; update fact status to `corrected` with `corrected_value`; return action item ID
      - `relationship`: parse `corrected_value` as `<subordinate> > <manager>` — if no `>` separator, raise `InvalidCorrectedValueError`; delegate name resolution to `person_service.resolve_person()` for each name; create relationship row via `relationship_repo`; update `reports_to_person_id` on subordinate via `person_service`; update fact status; return relationship ID
      - All other categories: store `corrected_value` on the fact; update status to `corrected`; return None (no entity creation)
  - `update_fact_value(company_id: str, fact_id: str, corrected_value: str) -> None` — UC 17 in-place editing of already-accepted/corrected InferredFacts; validates fact exists, belongs to company, status is `accepted` or `corrected`; rejects `pending`, `dismissed`, and `merged` facts (merged facts belong to another entity — editing them would be incoherent); sets `corrected_value` on the fact; does NOT change status (an accepted fact stays accepted; a corrected fact stays corrected); the original `inferred_value` is never overwritten per §6.3
- [ ] Write tests in `backend/tests/test_services/test_review_service.py`:
  - Merge tests:
    - `test_merge_person_success` — merge to existing person, verify status=merged, merged_into fields set
    - `test_merge_functional_area_success` — merge to existing area
    - `test_merge_target_not_found` — target_entity_id doesn't exist -> 404
    - `test_merge_target_wrong_company` — target exists but belongs to different company -> 404
    - `test_merge_relationship_returns_422` — relationship category -> MergeNotApplicableError
    - `test_merge_action_item_returns_422`
    - `test_merge_technology_returns_422`
    - `test_merge_fact_not_pending` — fact already accepted -> FactNotPendingError
    - `test_merge_fact_not_found` — fact doesn't exist -> FactNotFoundError
    - `test_merge_fact_wrong_company` — fact belongs to different company -> FactCompanyMismatchError
  - Correct tests:
    - `test_correct_person_with_comma` — corrected_value "Jane Smith, VP" -> person created with name+title
    - `test_correct_person_without_comma` — corrected_value "Jane Smith" -> person created with name only
    - `test_correct_functional_area_creates_new` — always creates new area (no dedup)
    - `test_correct_action_item` — creates action item with corrected description
    - `test_correct_relationship_valid` — "Alice > Bob" parsed, persons resolved/created, relationship created
    - `test_correct_relationship_no_separator` — raises InvalidCorrectedValueError
    - `test_correct_technology` — stores corrected_value, no entity, returns None
    - `test_correct_cgkra` — same as technology
    - `test_correct_fact_not_pending` — FactNotPendingError
    - `test_correct_fact_not_found` — FactNotFoundError
    - `test_correct_fact_wrong_company` — FactCompanyMismatchError
  - Update fact value tests (UC 17):
    - `test_update_fact_value_accepted_fact` — sets corrected_value on accepted fact, status stays accepted
    - `test_update_fact_value_corrected_fact` — overwrites corrected_value on corrected fact, status stays corrected
    - `test_update_fact_value_pending_fact_rejected` — pending fact -> error (must accept/correct first)
    - `test_update_fact_value_dismissed_fact_rejected` — dismissed fact -> error
    - `test_update_fact_value_merged_fact_rejected` — merged fact -> error (merged facts belong to another entity)
    - `test_update_fact_value_not_found` — FactNotFoundError
    - `test_update_fact_value_wrong_company` — FactCompanyMismatchError

**Why second**: merge, correct, and update_fact_value are the core review flow extensions. All three depend on the domain services from Unit 1. Everything else (routes, disambiguation, frontend) depends on these service methods.

**Rationale**: §10.4 specifies merge and correct as the two remaining review actions. UC 17 specifies that "the corrected value of any accepted InferredFact" can be edited from the company profile. `update_fact_value` handles the post-review editing case (distinct from the initial pending review).

**DECISION**: `correct_fact` for `functional-area` does NOT deduplicate — it always creates a new row per §10.4 ("create new functional_areas row with name = corrected_value"). This differs from `accept_fact` which deduplicates (Phase 2 behavior). The rationale: when an investigator uses "correct," they're explicitly providing a replacement value; if they wanted the existing area, they'd use "merge." If the corrected name happens to collide with an existing area (violating the UNIQUE constraint), the IntegrityError surfaces as a 409 — this is correct behavior indicating the investigator should merge instead.

---

## Unit 3: Merge + Correct + Update Fact API Endpoints

**Goal**: expose merge, correct, and update-fact-value as REST endpoints, add request/response schemas, and wire into the router.

- [ ] Add Pydantic schemas to `backend/app/schemas/inferred_fact.py`:
  - `MergeRequest` — `target_entity_id: str`
  - `MergeResponse` — `fact_id: UUID`, `status: str` (always "merged")
  - `CorrectRequest` — `corrected_value: str`
  - `CorrectResponse` — `fact_id: UUID`, `status: str` (always "corrected"), `entity_id: str | None`
  - `UpdateFactValueRequest` — `corrected_value: str`
  - `UpdateFactValueResponse` — `fact_id: UUID`, `status: str`, `corrected_value: str`
- [ ] Add route handlers in `backend/app/api/v1/pending.py`:
  - `POST /{company_id}/pending/{fact_id}/merge` — parse `MergeRequest` body; call `review_service.merge_fact()`; return `MergeResponse`
  - `POST /{company_id}/pending/{fact_id}/correct` — parse `CorrectRequest` body; call `review_service.correct_fact()`; return `CorrectResponse`
- [ ] Add route handler in `backend/app/api/v1/facts.py` (new file):
  - `PUT /companies/{company_id}/facts/{fact_id}` — parse `UpdateFactValueRequest` body; call `review_service.update_fact_value()`; return `UpdateFactValueResponse`. **Note**: this is deliberately NOT under `/pending/` — UC 17 edits apply to accepted/corrected facts, which are no longer pending. The `/facts/` path accurately represents the target resource.
- [ ] Register `facts` router in `backend/app/api/v1/router.py`
- [ ] Write API-level tests in `backend/tests/test_api/test_pending.py`:
  - `test_merge_person_fact` — POST merge with valid target -> 200, status "merged"
  - `test_merge_unsupported_category_returns_422` — technology fact -> 422 merge_not_applicable
  - `test_merge_target_not_found_returns_404` — invalid target_entity_id -> 404
  - `test_merge_unauthenticated` — no session -> 401
  - `test_correct_person_fact` — POST correct with "Jane Smith, CTO" -> 200, entity_id returned
  - `test_correct_relationship_fact` — POST correct with "Alice > Bob" -> 200
  - `test_correct_relationship_no_separator_returns_422` — "Alice Bob" -> 422
  - `test_correct_technology_fact` — POST correct -> 200, entity_id null
  - `test_correct_unauthenticated` — no session -> 401
- [ ] Write API-level tests in `backend/tests/test_api/test_facts.py` (new file):
  - `test_update_fact_value` — PUT `/companies/{id}/facts/{fact_id}` with corrected_value on accepted fact -> 200
  - `test_update_fact_value_pending_returns_error` — PUT on pending fact -> error
  - `test_update_fact_value_unauthenticated` — no session -> 401

**Why third**: the API layer is a thin wrapper over the service methods from Units 1–2. Tested independently to verify HTTP semantics, authentication, and serialization.

**Rationale**: §10.4 defines POST `.../merge` and POST `.../correct` as required endpoints. UC 17 requires PUT for editing accepted fact values. Merge and correct are routed through `pending.py` because they act on pending facts. `update_fact_value` is routed through a new `facts.py` because it acts on accepted/corrected facts — routing it through `/pending/` would be semantically incorrect.

---

## Unit 4: Disambiguation Candidates (Fuzzy Matching)

**Goal**: enhance `ReviewService.list_pending()` to return ranked disambiguation candidates for each fact. Add fuzzy similarity scoring.

- [ ] Add a fuzzy similarity utility:
  - Create `backend/app/services/fuzzy_match.py`
  - Implement `similarity_score(a: str, b: str) -> float` — normalized token-based similarity (0.0–1.0)
  - **Implementation**: use `difflib.SequenceMatcher` from the standard library (no new dependencies). Normalize by lowercasing and stripping whitespace before comparison.
- [ ] Extend repository methods for candidate retrieval:
  - `PersonRepository.list_by_company(company_id)` — already exists, returns all persons ordered by name
  - `FunctionalAreaRepository.list_by_company(company_id)` — already exists
- [ ] Modify `ReviewService.list_pending()`:
  - After fetching each fact, compute candidates based on category:
    - `person`: fetch all persons for the company via `person_service.list_people()`; score each against `fact.inferred_value` using `similarity_score(person.name, inferred_value)`; return sorted by score desc; each candidate: `{ "entity_id": str(person.id), "value": person.name, "similarity_score": float }`
    - `functional-area`: fetch all areas via `functional_area_service.list_areas()`; score each against `fact.inferred_value` using `similarity_score(area.name, inferred_value)`; sort by score desc
    - `relationship`: **polymorphic shape** — fetch all persons via `person_service.list_people()`; for each person, compute score against `subordinate` and `manager` fields (parsed from `inferred_value` which is stored as "sub > mgr"); return `{ "subordinate": [...candidates scored against sub name...], "manager": [...candidates scored against mgr name...] }` (object, not array — frontend must handle this type difference)
    - All other categories (`action-item`, `technology`, `process`, `product`, `cgkra-*`, `swot-*`, `other`): empty list — no entity disambiguation
  - **Performance note**: candidate computation scans all entities per fact per page. For Phase 3's expected data volumes (small — single user, modest companies), this is acceptable. **Optimization**: cache the entity lists (persons, areas) per page request — fetch once at the start of `list_pending()`, then reuse for all facts on that page. This avoids N+1 queries (one per fact) while still being O(facts * entities) for scoring. Phase 5+ can add further caching or limit candidate lists if needed.
- [ ] Update `PendingFactItem` schema in `backend/app/schemas/inferred_fact.py`:
  - Define `CandidateItem(BaseModel)` — `entity_id: str`, `value: str`, `similarity_score: float`
  - Define `RelationshipCandidates(BaseModel)` — `subordinate: list[CandidateItem]`, `manager: list[CandidateItem]`
  - Change `PendingFactItem.candidates` type to `list[CandidateItem] | RelationshipCandidates` with default `[]`
- [ ] Update frontend type in `frontend/src/types/index.ts`:
  - `CandidateItem = { entity_id: string; value: string; similarity_score: number }`
  - `RelationshipCandidates = { subordinate: CandidateItem[]; manager: CandidateItem[] }`
  - Update `PendingFactItem.candidates` type to `CandidateItem[] | RelationshipCandidates`
- [ ] Write tests:
  - In `backend/tests/test_services/test_fuzzy_match.py` (new file):
    - `test_exact_match_score_1` — identical strings -> 1.0
    - `test_no_overlap_score_0` — completely different strings -> ~0.0
    - `test_partial_match` — "Eng" vs "Engineering" -> high score
    - `test_case_insensitive` — "kubernetes" vs "Kubernetes" -> 1.0
    - `test_abbreviation` — "k8s" vs "Kubernetes" -> low score (no magic, just sequence matching)
  - In `backend/tests/test_services/test_review_service.py`:
    - `test_list_pending_person_candidates` — person fact returns ranked person candidates
    - `test_list_pending_area_candidates` — area fact returns ranked area candidates
    - `test_list_pending_relationship_candidates` — relationship fact returns `{ subordinate: [...], manager: [...] }` structure (object, not array)
    - `test_list_pending_technology_no_candidates` — technology fact returns empty candidates
    - `test_list_pending_action_item_no_candidates` — action-item fact returns empty candidates (no disambiguation for action-items)
    - `test_list_pending_product_no_candidates` — product fact returns empty candidates
    - `test_list_pending_no_entities_empty_candidates` — no entities in company -> empty candidates list

**Why fourth**: disambiguation depends on the list_pending API already working (Phase 2) and domain services from Unit 1. It must be complete before the frontend can show candidate lists.

**Rationale**: §10.4 specifies candidates as a ranked list of existing same-category entities ordered by fuzzy similarity. §6.1 calls out "k8s" -> "Kubernetes" and "Eng" -> "Engineering" as example scenarios. The spec does not mandate a specific fuzzy algorithm — `SequenceMatcher` provides reasonable results for this use case.

---

## Unit 5: People CRUD API Endpoints

**Goal**: implement the full people REST API from §10.5 — list, create, get detail (with action items and inferred facts), update, and delete. The service methods were created in Unit 1; this unit adds the route handlers, schemas, and tests.

- [ ] Extend `PersonRepository` in `backend/app/repositories/person_repository.py`:
  - `update(person_id: UUID, **fields) -> Person` — update specified fields; raise ValueError if not found
  - `delete(person_id: UUID) -> None` — delete person; raise ValueError if not found. **Note**: CASCADE behavior is DB-level — relationships referencing this person (as subordinate or manager) have ON DELETE CASCADE per §11.6; action items have ON DELETE SET NULL on `person_id` per §11.4; no manual cascade code is needed in the repository
- [ ] Extend `ActionItemRepository` in `backend/app/repositories/action_item_repository.py`:
  - `list_by_person(person_id: UUID) -> list[ActionItem]` — return action items where `person_id` matches, ordered by `created_at` desc
- [ ] Extend `InferredFactRepository` in `backend/app/repositories/inferred_fact_repository.py`:
  - `list_linked_to_person(company_id: UUID, person_id: UUID, primary_area_id: UUID | None) -> list[InferredFact]` — return accepted/corrected facts linked to this person; query strategy per §10.5:
    - Facts with `category = 'person'` where `inferred_value` matches the person's name (case-insensitive) — these are the facts that were accepted/corrected to create/identify this person
    - Facts with any category where `functional_area_id` matches the person's `primary_area_id` (if the person has one) — these are facts tagged to the same functional area
    - Union of both, deduplicated by fact ID, ordered by `created_at`
- [ ] Add Pydantic schemas to `backend/app/schemas/person.py` (new file):
  - `PersonCreateInput` — `name: str`, `title: str | None = None`, `primary_area_id: str | None = None`, `reports_to_person_id: str | None = None`
  - `PersonUpdateInput` — all fields optional; same null-rejection pattern as `CompanyUpdate`
  - `ActionItemSummary` — `item_id: UUID`, `description: str`, `status: str`, `notes: str | None`, `created_at: str`
  - `LinkedFactSummary` — `fact_id: UUID`, `category: str`, `value: str`, `source_id: UUID`
  - `PersonDetail` — `person_id: UUID`, `name: str`, `title: str | None`, `primary_area_id: UUID | None`, `primary_area_name: str | None`, `reports_to_person_id: UUID | None`, `reports_to_name: str | None`, `action_items: list[ActionItemSummary]`, `inferred_facts: list[LinkedFactSummary]`
  - `PersonListItem` — `person_id: UUID`, `name: str`, `title: str | None`, `primary_area_id: UUID | None`, `primary_area_name: str | None`
  - `PersonListResponse` — `items: list[PersonListItem]`
  - `PersonCreatedResponse` — `person_id: UUID`, `name: str`
- [ ] Create route handlers in `backend/app/api/v1/people.py` (new file):
  - `GET /companies/{company_id}/people` — list all people
  - `POST /companies/{company_id}/people` — create a person
  - `GET /companies/{company_id}/people/{person_id}` — person detail
  - `PUT /companies/{company_id}/people/{person_id}` — update person
  - `DELETE /companies/{company_id}/people/{person_id}` — delete person
- [ ] Register in `backend/app/api/v1/router.py`
- [ ] Write tests in `backend/tests/test_api/test_people.py` (new file):
  - `test_list_people` — returns all people for company
  - `test_list_people_empty` — no people -> empty items
  - `test_create_person` — POST with name+title -> 201, person created
  - `test_create_person_minimal` — name only -> 201
  - `test_get_person_detail` — returns enriched detail with area name, action items, linked facts
  - `test_get_person_detail_linked_facts_by_area` — person assigned to area -> facts tagged to that area appear in linked facts
  - `test_get_person_not_found` — 404
  - `test_update_person_name` — PUT with new name -> 200
  - `test_update_person_area` — PUT with primary_area_id -> 200
  - `test_update_person_not_found` — 404
  - `test_delete_person` — DELETE -> 204
  - `test_delete_person_not_found` — 404
  - `test_people_unauthenticated` — 401

**Why fifth**: people CRUD depends on PersonService (Unit 1) for the service layer. The route handlers are a thin REST wrapper.

**Rationale**: §10.5 defines five people endpoints. Person detail (GET) includes action items and linked inferred facts per the spec response shape: "inferred_facts contains accepted and corrected facts linked to this person's primary functional area via functional_area_id."

---

## Unit 6: Org Chart Endpoint

**Goal**: implement `GET /companies/{id}/orgchart` per §10.5 — recursive tree construction from the relationships table.

- [ ] Extend `RelationshipRepository` in `backend/app/repositories/relationship_repository.py`:
  - `list_by_company(company_id: UUID) -> list[Relationship]` — return all relationships for a company
- [ ] Create `OrgChartService` in `backend/app/services/orgchart_service.py` (new file):
  - Constructor: `person_repo`, `relationship_repo`
  - `build_orgchart(company_id: str) -> dict` — returns `{ "roots": [...], "unplaced": [...] }`
  - **Algorithm**:
    1. Fetch all persons for the company
    2. Fetch all relationships for the company
    3. Build a mapping: `subordinate_id -> manager_id` and `manager_id -> list[subordinate_ids]`
    4. Identify roots: persons who appear as `manager_person_id` in at least one relationship row but never as `subordinate_person_id` (known to manage others, not known to report to anyone)
    5. Identify unplaced: persons where no relationship row references `person.id` in either column (neither subordinate nor manager in any relationship — completely disconnected); mutually exclusive with roots
    6. Build recursive tree from each root: `{ "person_id", "name", "title", "reports_to": null, "reports": [ {...recursive...} ] }`
    7. Unplaced nodes: `{ "person_id", "name", "title" }`
  - **Edge cases**: handle cycles defensively (visited set to prevent infinite recursion); handle empty company (no persons -> empty roots + empty unplaced)
- [ ] Add Pydantic schemas to `backend/app/schemas/orgchart.py` (new file):
  - `OrgChartNode` — `person_id: UUID`, `name: str`, `title: str | None`, `reports_to: UUID | None`, `reports: list[OrgChartNode]`
    - Use `model_rebuild()` for self-referential schema
  - `OrgChartResponse` — `roots: list[OrgChartNode]`, `unplaced: list[OrgChartUnplacedNode]`
  - `OrgChartUnplacedNode` — `person_id: UUID`, `name: str`, `title: str | None`
- [ ] Add route handler in `backend/app/api/v1/orgchart.py` (new file):
  - `GET /companies/{company_id}/orgchart` — call `orgchart_service.build_orgchart()`; return `OrgChartResponse`
- [ ] Register in `backend/app/api/v1/router.py`
- [ ] Add DI provider: `get_orgchart_service(db) -> OrgChartService`
- [ ] Write tests in `backend/tests/test_api/test_orgchart.py` (new file):
  - `test_orgchart_single_root` — CEO -> VP -> Engineer hierarchy -> one root with nested reports
  - `test_orgchart_multiple_roots` — two independent trees -> two roots
  - `test_orgchart_no_relationships` — people exist but no relationships -> all unplaced
  - `test_orgchart_mixed_roots_and_unplaced` — some in tree, some unplaced
  - `test_orgchart_empty_company` — no people -> empty roots + empty unplaced
  - `test_orgchart_person_is_manager_only` — person who manages others but isn't subordinate -> appears as root
  - `test_orgchart_leaf_node` — person who is subordinate but manages no one -> appears in tree with empty `reports` list
  - `test_orgchart_unauthenticated` — 401
- [ ] Write service-level tests in `backend/tests/test_services/test_orgchart_service.py` (new file):
  - `test_build_orgchart_basic_tree` — verify recursive structure
  - `test_build_orgchart_cycle_protection` — A reports to B, B reports to A -> no infinite loop

**Why sixth**: org chart depends on people (Unit 5) and relationships (already in DB from Phase 2). It's a read-only aggregation endpoint with no side effects.

**Rationale**: §10.5 defines the org chart response shape. §11.6 specifies how roots and unplaced are derived from the relationships table.

---

## Unit 7: Functional Area CRUD Endpoints

**Goal**: implement the full functional area REST API from §10.6 — list, create, get detail, update (rename), and delete. The service methods were created in Unit 1; this unit adds the route handlers, schemas, and tests.

- [ ] Extend `FunctionalAreaRepository`:
  - `update(area_id: UUID, *, name: str | None = None, notes: str | None = None) -> FunctionalArea` — update specified fields; **set `updated_at = func.now()`** on every update (the ORM model should use `onupdate=func.now()` on the column, but the repository explicitly sets it as belt-and-suspenders); raise ValueError if not found
  - `delete(area_id: UUID) -> None` — delete area (does not delete linked entities — FK is ON DELETE SET NULL); raise ValueError if not found
- [ ] Add Pydantic schemas to `backend/app/schemas/functional_area.py` (new file):
  - `AreaCreateInput` — `name: str`, `notes: str | None = None`
  - `AreaUpdateInput` — `name: str | None = None`, `notes: str | None = None` (partial update, same pattern as `CompanyUpdate`)
  - `AreaListItem` — `area_id: UUID`, `name: str`, `notes: str | None`, `created_at: str`
  - `AreaListResponse` — `items: list[AreaListItem]`
  - `AreaDetail` — `area_id: UUID`, `name: str`, `notes: str | None`, `created_at: str`, `updated_at: str`, `people: list[PersonListItem]`, `action_items: list[ActionItemSummary]`, `inferred_facts: list[LinkedFactSummary]` (accepted/corrected facts linked to this area via `functional_area_id`), `cgkra: None` (stub — populated in Phase 4 when CGKRA aggregation is implemented)
  - `AreaCreatedResponse` — `area_id: UUID`, `name: str`
- [ ] Extend repositories for area detail queries:
  - `PersonRepository.list_by_area(area_id: UUID) -> list[Person]` — persons where `primary_area_id` matches
  - `ActionItemRepository.list_by_area(area_id: UUID) -> list[ActionItem]` — action items where `functional_area_id` matches
  - `InferredFactRepository.list_by_area(area_id: UUID) -> list[InferredFact]` — accepted/corrected facts where `functional_area_id` matches, ordered by `created_at`
- [ ] Create route handlers in `backend/app/api/v1/areas.py` (new file):
  - `GET /companies/{company_id}/areas` — list areas
  - `POST /companies/{company_id}/areas` — create area
  - `GET /companies/{company_id}/areas/{area_id}` — area detail
  - `PUT /companies/{company_id}/areas/{area_id}` — update area (name, notes)
  - `DELETE /companies/{company_id}/areas/{area_id}` — delete area
- [ ] Register in `backend/app/api/v1/router.py`
- [ ] Write tests in `backend/tests/test_api/test_areas.py` (new file):
  - `test_list_areas` — returns all areas
  - `test_list_areas_empty` — empty list
  - `test_create_area` — POST -> 201
  - `test_create_area_duplicate_name_409` — same name (case-insensitive) -> 409
  - `test_get_area_detail` — returns area with people, action items, inferred_facts, notes, and cgkra=None
  - `test_get_area_detail_linked_facts` — area with linked inferred facts -> facts appear in `inferred_facts` list
  - `test_get_area_not_found` — 404
  - `test_update_area_rename` — PUT with new name -> 200
  - `test_update_area_notes` — PUT with notes -> 200, notes persisted
  - `test_update_area_name_conflict` — rename to existing name -> 409
  - `test_delete_area` — DELETE -> 204
  - `test_delete_area_not_found` — 404
  - `test_areas_unauthenticated` — 401

**Why seventh**: functional area CRUD depends on FunctionalAreaService (Unit 1) and the person list (Unit 5, for area detail). Independent of org chart.

**Rationale**: §10.6 defines five area endpoints. Delete does not cascade to linked persons or action items — their FK is ON DELETE SET NULL per §11.2. AreaDetail includes notes (§11.2), inferred_facts (accepted/corrected facts linked via `functional_area_id`), and a `cgkra: None` stub — §10.6 says the detail includes "people, CGKRA, action items, facts, notes." CGKRA aggregation is deferred to Phase 4. The stub ensures the response shape is forward-compatible.

---

## Unit 8: Frontend — Merge + Correct + Disambiguation UI

**Goal**: upgrade the PendingReviewQueue component to support merge, correct, and disambiguation candidate selection. Replace the Phase 2 workaround entity display with real API calls. Add in-place fact value editing.

- [ ] Add frontend API functions in `frontend/src/api/pending.ts`:
  - `mergeFact(companyId, factId, targetEntityId) -> MergeResponse`
  - `correctFact(companyId, factId, correctedValue) -> CorrectResponse`
- [ ] Add frontend API function in `frontend/src/api/facts.ts` (new file):
  - `updateFactValue(companyId, factId, correctedValue) -> UpdateFactValueResponse` — calls `PUT /companies/{id}/facts/{fact_id}` (not `/pending/`)
- [ ] Add frontend API functions in `frontend/src/api/people.ts` (new file):
  - `listPeople(companyId) -> PersonListResponse`
  - `createPerson(companyId, data) -> PersonCreatedResponse`
  - `getPerson(companyId, personId) -> PersonDetail`
  - `updatePerson(companyId, personId, data) -> PersonDetail`
  - `deletePerson(companyId, personId) -> void`
- [ ] Add frontend API functions in `frontend/src/api/areas.ts` (new file):
  - `listAreas(companyId) -> AreaListResponse`
  - `createArea(companyId, { name, notes? }) -> AreaCreatedResponse`
  - `getArea(companyId, areaId) -> AreaDetail`
  - `updateArea(companyId, areaId, { name?, notes? }) -> AreaDetail`
  - `deleteArea(companyId, areaId) -> void`
- [ ] Add frontend API function in `frontend/src/api/orgchart.ts` (new file):
  - `getOrgChart(companyId) -> OrgChartResponse`
- [ ] Update TypeScript types in `frontend/src/types/index.ts`:
  - `MergeResponse`, `CorrectResponse`, `UpdateFactValueResponse`
  - `PersonListItem`, `PersonListResponse`, `PersonDetail`, `PersonCreateInput`, `PersonUpdateInput`, `PersonCreatedResponse`
  - `AreaListItem`, `AreaListResponse`, `AreaDetail`, `AreaCreateInput`, `AreaCreatedResponse`
  - `OrgChartNode`, `OrgChartUnplacedNode`, `OrgChartResponse`
  - `CandidateItem`, `RelationshipCandidates`
  - `ActionItemSummary`, `LinkedFactSummary`
- [ ] Upgrade `PendingReviewQueue.tsx`:
  - Show candidates list below each fact item (collapsible)
  - For person/functional-area facts: show ranked candidate list with similarity scores; "Merge" button beside each candidate
  - For relationship facts: show subordinate and manager candidate lists separately
  - "Correct" button that opens inline text input; submit sends `correctFact()`
  - Keep existing Accept and Dismiss buttons
  - Handle 422 errors (merge_not_applicable, invalid_corrected_value) with user-visible messages
- [ ] Replace Phase 2 workaround in `CompanyProfilePage.tsx`:
  - Remove `acceptedPersons`, `acceptedTech`, `acceptedProcesses`, `acceptedAreas` state (fetched from `listPending` with status=accepted)
  - Replace People section with `listPeople()` API call — show real person entities with click-through to detail
  - Replace Functional Areas section with `listAreas()` API call — show real area entities with click-through to detail
  - Keep Technologies, Processes, and Products sections using `listPending(status=accepted, category=...)` — these categories have no dedicated entity table
  - Add inline edit button for accepted fact values (calls `updateFactValue()`) — UC 17 for technology, process, cgkra, swot, and other facts that have no dedicated entity
- [ ] Update CSS in `frontend/src/index.css` as needed for candidate lists, merge/correct buttons, inline edit inputs, and fact value editing

**Why eighth**: the frontend depends on all backend endpoints (Units 1–7) being complete. Building it last avoids churn from API changes.

**Rationale**: UC 5 requires the investigator to see candidates and choose merge/correct/accept/dismiss. UC 17 requires in-place editing of accepted fact values. The Phase 2 PendingReviewQueue only had accept/dismiss — this unit completes the review UI.

---

## Unit 9: Frontend — Org Chart + Person Detail + Area Views + Editing

**Goal**: implement org chart visualization, person detail page, functional area pages, and in-place editing of people and areas (UC 17).

- [ ] Create `OrgChartView.tsx` component in `frontend/src/components/`:
  - Renders the recursive tree structure from `getOrgChart()`
  - Multiple roots displayed as parallel trees
  - Unplaced section displayed separately with clear label
  - Click on any person navigates to person detail
  - Handles empty state (no people / no relationships)
- [ ] Create `PersonDetailPage.tsx` in `frontend/src/pages/`:
  - Route: `/companies/:id/people/:personId`
  - Displays: name, title, primary area (linked), reports-to (linked), action items list, linked inferred facts
  - Edit button opens inline form (UC 17): name, title, primary_area_id (dropdown from areas), reports_to_person_id (dropdown from people)
  - Delete button with confirmation
- [ ] Create `AreaListPage.tsx` or section in CompanyProfilePage:
  - Lists all functional areas for the company
  - Click navigates to area detail
- [ ] Create `AreaDetailPage.tsx` in `frontend/src/pages/`:
  - Route: `/companies/:id/areas/:areaId`
  - Displays: name, notes, people assigned to this area, action items, cgkra placeholder ("Coming in Phase 4")
  - Edit button for name and notes (UC 17)
  - Delete button with confirmation
- [ ] Add org chart section to `CompanyProfilePage.tsx`:
  - New section between People and Technologies
  - Shows org chart inline or as expandable panel
- [ ] Update `App.tsx` with new routes:
  - `/companies/:id/people/:personId` -> PersonDetailPage
  - `/companies/:id/areas/:areaId` -> AreaDetailPage
- [ ] Update CSS for org chart tree layout, person detail, area detail, edit forms

**Why ninth**: this unit depends on all backend endpoints (Units 5–7) and the API client functions from Unit 8. It's pure frontend.

**Rationale**: UC 6 (org chart), UC 17 (in-place editing of people and areas), and §10.5/§10.6 response shapes drive the page designs.

---

## Unit 10: Integration Verification + Test Suite Completion

**Goal**: verify the full Phase 3 feature set end-to-end, ensure all tests pass, frontend builds, and uvicorn starts cleanly.

- [ ] Write e2e integration tests in `backend/tests/test_api/test_e2e_phase3.py` (new file):
  - `test_full_review_flow` — upload source -> process -> list pending with candidates -> merge a person fact -> correct another fact -> verify entity state
  - `test_orgchart_after_relationship_acceptance` — upload source with relationship lines -> accept -> verify org chart shows correct hierarchy
  - `test_people_crud_full_lifecycle` — create person -> update -> assign to area -> delete -> verify cascade behavior
  - `test_area_crud_with_linked_entities` — create area -> assign person -> delete area -> verify person's primary_area_id is null
  - `test_update_accepted_fact_value` — accept a technology fact -> update corrected_value via PUT -> verify value is persisted and original inferred_value unchanged
- [ ] Run full test suite — all tests must pass
- [ ] Verify frontend builds (`npm run build`)
- [ ] Verify uvicorn starts and route count matches expectations
- [ ] Update `PHASE3.md` with completion status (checkboxes, `COMPLETE` annotations)

**Why last**: integration verification is the final gate before the phase is considered complete.

**Rationale**: §17 exit criteria for Phase 3: "investigator can merge, correct, and dismiss facts; navigate the org chart; click into person details; manage people and functional areas directly."

---

## Exit Criteria (from REQUIREMENTS.md §17 Phase 3)

- [ ] Investigator can merge a pending person or functional-area fact with an existing entity
- [ ] Investigator can correct a pending fact (person, functional-area, action-item, relationship, or other)
- [ ] Investigator can edit the corrected_value of any accepted/corrected InferredFact from the company profile (UC 17)
- [ ] Merge returns 422 for unsupported categories (relationship, action-item, technology, process, product, cgkra-*, swot-*, other)
- [ ] Correct returns 422 for relationship facts without `>` separator
- [ ] Correct for functional-area always creates a new row (no deduplication — use merge for linking to existing)
- [ ] Disambiguation candidates are ranked by fuzzy similarity and returned in `GET .../pending`
- [ ] ReviewService delegates entity creation to PersonService/FunctionalAreaService (partial §9.2 compliance — ActionItemRepository and RelationshipRepository remain on ReviewService directly; ActionItemService extraction deferred until action-item CRUD endpoints are added in a future phase)
- [ ] People CRUD endpoints work (list, create, get detail with area-linked facts, update, delete)
- [ ] Org chart endpoint returns correct tree with roots and unplaced
- [ ] Functional area CRUD endpoints work (list, create, get detail with notes and cgkra stub, update name/notes, delete)
- [ ] Frontend pending review queue supports merge, correct, accept, and dismiss
- [ ] Frontend shows org chart visualization with clickable person nodes
- [ ] Frontend shows person detail with action items and linked facts
- [ ] Frontend supports in-place editing of people, functional areas, and accepted fact values (UC 17)
- [ ] All tests pass across two consecutive runs (isolation verified)
- [ ] Frontend builds cleanly
- [ ] Uvicorn starts and serves all endpoints
