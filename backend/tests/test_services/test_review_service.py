"""Tests for ReviewService — Unit 5 of Phase 2.

Tests cover:
  - save_facts: persists pending InferredFact rows (including relationship encoding)
  - list_pending: filters by status and category, returns source excerpts
  - accept_fact: per-category entity creation (person, functional-area, action-item,
    relationship, technology, cgkra-*, swot-*, other)
  - dismiss_fact: marks facts dismissed with reviewed_at timestamp
  - Error cases: wrong company, non-pending fact, fact not found
"""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Company, Source
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.person_repository import PersonRepository
from app.repositories.relationship_repository import RelationshipRepository
from app.repositories.source_repository import SourceRepository
from app.exceptions import FactCompanyMismatchError, FactNotFoundError, FactNotPendingError
from app.schemas.inferred_fact import LLMInferredFact
from app.services.prefix_parser_service import ParsedLine
from app.services.review_service import ReviewService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="session")
async def review_service(db_session: AsyncSession) -> ReviewService:
    """Provide a ReviewService wired to test repos."""
    return ReviewService(
        inferred_fact_repo=InferredFactRepository(db_session),
        source_repo=SourceRepository(db_session),
        person_repo=PersonRepository(db_session),
        functional_area_repo=FunctionalAreaRepository(db_session),
        action_item_repo=ActionItemRepository(db_session),
        relationship_repo=RelationshipRepository(db_session),
    )


@pytest_asyncio.fixture(loop_scope="session")
async def fact_repo(db_session: AsyncSession) -> InferredFactRepository:
    return InferredFactRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def person_repo(db_session: AsyncSession) -> PersonRepository:
    return PersonRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def area_repo(db_session: AsyncSession) -> FunctionalAreaRepository:
    return FunctionalAreaRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def action_repo(db_session: AsyncSession) -> ActionItemRepository:
    return ActionItemRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def relationship_repo(db_session: AsyncSession) -> RelationshipRepository:
    return RelationshipRepository(db_session)


# ---------------------------------------------------------------------------
# Helpers — create data inside each test's savepoint
# ---------------------------------------------------------------------------


async def _make_company(db: AsyncSession, name: str | None = None) -> Company:
    c = Company(name=name or f"ReviewTestCo-{uuid4().hex[:8]}")
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


async def _make_source(
    db: AsyncSession, company_id, raw_content: str = "p: Jane\ntech: K8s"
) -> Source:
    s = Source(
        company_id=company_id,
        type="upload",
        filename_or_subject="test-notes.txt",
        raw_content=raw_content,
    )
    db.add(s)
    await db.flush()
    await db.refresh(s)
    return s


# ---------------------------------------------------------------------------
# save_facts tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_creates_pending_rows(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """save_facts persists LLMInferredFact list as pending inferred_facts rows with source_line."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    lines = [
        ParsedLine(canonical_key="p", text="Alice Brown, CTO"),
        ParsedLine(canonical_key="t", text="Docker"),
    ]
    facts = [
        LLMInferredFact(category="person", value="Alice Brown, CTO"),
        LLMInferredFact(category="technology", value="Docker"),
    ]
    await review_service.save_facts(source.id, company.id, facts, lines)

    rows, total = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    values = {r.inferred_value for r in rows}
    assert "Alice Brown, CTO" in values
    assert "Docker" in values
    assert total == 2
    for r in rows:
        assert r.status == "pending"
        assert r.source_id == source.id
        assert r.company_id == company.id
        assert r.source_line is not None  # source_line populated via matching


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_relationship_encoding(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """Relationship facts are stored as 'subordinate > manager' in inferred_value."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    lines = [
        ParsedLine(canonical_key="rel", text="Jane Smith > Bob Jones"),
    ]
    facts = [
        LLMInferredFact(
            category="relationship",
            value="Jane reports to Bob",
            subordinate="Jane Smith",
            manager="Bob Jones",
        ),
    ]
    await review_service.save_facts(source.id, company.id, facts, lines)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="relationship", limit=100, offset=0
    )
    assert len(rows) == 1
    assert rows[0].inferred_value == "Jane Smith > Bob Jones"
    assert rows[0].source_line == "rel: Jane Smith > Bob Jones"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_empty_list(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """save_facts with empty list does nothing (no error)."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    await review_service.save_facts(source.id, company.id, [])
    _, total = await fact_repo.list_by_company(
        company.id, status="pending", limit=1, offset=0
    )
    assert total == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_source_line_null_when_no_match(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """source_line is null when LLM rephrases the fact and no ParsedLine matches."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    lines = [
        ParsedLine(canonical_key="n", text="The team uses some kind of container orchestration"),
    ]
    # LLM rephrased substantially — no substring match
    facts = [LLMInferredFact(category="technology", value="Kubernetes")]
    await review_service.save_facts(source.id, company.id, facts, lines)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert len(rows) == 1
    assert rows[0].source_line is None


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_without_lines_source_line_null(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """source_line is null when save_facts is called without lines (backward compat)."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="technology", value="Redis")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert len(rows) == 1
    assert rows[0].source_line is None


# ---------------------------------------------------------------------------
# list_pending tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_default_status(
    db_session: AsyncSession, review_service: ReviewService
):
    """list_pending with default status returns only pending facts."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [
        LLMInferredFact(category="person", value="LP Person"),
        LLMInferredFact(category="technology", value="LP Tech"),
    ]
    await review_service.save_facts(source.id, company.id, facts)

    items, total = await review_service.list_pending(str(company.id))
    assert total == 2
    for item in items:
        assert item["status"] == "pending"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_source_excerpt_from_source_line(
    db_session: AsyncSession, review_service: ReviewService
):
    """list_pending uses source_line as source_excerpt when available."""
    company = await _make_company(db_session)
    source = await _make_source(
        db_session, company.id, raw_content="t: Excerpt Tech\nn: other stuff"
    )
    lines = [
        ParsedLine(canonical_key="t", text="Excerpt Tech"),
        ParsedLine(canonical_key="n", text="other stuff"),
    ]
    facts = [LLMInferredFact(category="technology", value="Excerpt Tech")]
    await review_service.save_facts(source.id, company.id, facts, lines)

    items, _ = await review_service.list_pending(str(company.id))
    assert len(items) == 1
    assert items[0]["source_excerpt"] == "t: Excerpt Tech"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_source_excerpt_fallback_no_source_line(
    db_session: AsyncSession, review_service: ReviewService
):
    """list_pending falls back to '[source] ' + raw_content[:200] when source_line is null."""
    company = await _make_company(db_session)
    source = await _make_source(
        db_session, company.id, raw_content="Some important notes about the company"
    )
    # Save without lines — source_line will be null
    facts = [LLMInferredFact(category="technology", value="Fallback Tech")]
    await review_service.save_facts(source.id, company.id, facts)

    items, _ = await review_service.list_pending(str(company.id))
    assert len(items) == 1
    assert items[0]["source_excerpt"] == "[source] Some important notes about the company"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_candidates_empty(
    db_session: AsyncSession, review_service: ReviewService
):
    """In Phase 2, candidates is always an empty list."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = [LLMInferredFact(category="technology", value="Cand Tech")]
    await review_service.save_facts(source.id, company.id, facts)

    items, _ = await review_service.list_pending(str(company.id))
    for item in items:
        assert item["candidates"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_category_filter(
    db_session: AsyncSession, review_service: ReviewService
):
    """list_pending with category filter returns only matching facts."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = [
        LLMInferredFact(category="technology", value="Cat Filter Tech"),
        LLMInferredFact(category="person", value="Cat Filter Person"),
    ]
    await review_service.save_facts(source.id, company.id, facts)

    items, total = await review_service.list_pending(
        str(company.id), category="technology"
    )
    assert total == 1
    assert items[0]["category"] == "technology"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_pagination(
    db_session: AsyncSession, review_service: ReviewService
):
    """list_pending respects limit and offset."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = [
        LLMInferredFact(category="technology", value="Page1"),
        LLMInferredFact(category="technology", value="Page2"),
        LLMInferredFact(category="technology", value="Page3"),
    ]
    await review_service.save_facts(source.id, company.id, facts)

    items_1, total = await review_service.list_pending(
        str(company.id), limit=1, offset=0
    )
    assert total == 3
    assert len(items_1) == 1

    items_2, _ = await review_service.list_pending(
        str(company.id), limit=1, offset=1
    )
    assert len(items_2) == 1
    assert items_2[0]["fact_id"] != items_1[0]["fact_id"]


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_source_deleted_fallback(
    db_session: AsyncSession, fact_repo,
):
    """list_pending returns empty source_excerpt when source_line is null and source is missing.

    The source_id FK has CASCADE, so in practice this only happens with
    corrupt data. The defensive branch returns "" for source_excerpt.
    """
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    # Create a fact without source_line, then build a ReviewService with a
    # source_repo that returns None for get_by_id (simulating a missing source).
    rows = await fact_repo.create_many([{
        "source_id": source.id,
        "company_id": company.id,
        "category": "technology",
        "inferred_value": "Phantom Tech",
    }])

    mock_source_repo = AsyncMock()
    mock_source_repo.get_by_id.return_value = None

    svc = ReviewService(
        inferred_fact_repo=fact_repo,
        source_repo=mock_source_repo,
        person_repo=AsyncMock(),
        functional_area_repo=AsyncMock(),
        action_item_repo=AsyncMock(),
        relationship_repo=AsyncMock(),
    )

    items, total = await svc.list_pending(str(company.id))
    assert total == 1
    assert items[0]["source_excerpt"] == ""


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_source_null_raw_content_fallback(
    db_session: AsyncSession, fact_repo,
):
    """list_pending returns empty source_excerpt when source_line is null and raw_content is None.

    raw_content is NOT NULL in the schema, so this guards against bad DB state.
    """
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    rows = await fact_repo.create_many([{
        "source_id": source.id,
        "company_id": company.id,
        "category": "technology",
        "inferred_value": "Null Content Tech",
    }])

    # Mock a source that exists but has raw_content = None
    mock_source = AsyncMock()
    mock_source.raw_content = None

    mock_source_repo = AsyncMock()
    mock_source_repo.get_by_id.return_value = mock_source

    svc = ReviewService(
        inferred_fact_repo=fact_repo,
        source_repo=mock_source_repo,
        person_repo=AsyncMock(),
        functional_area_repo=AsyncMock(),
        action_item_repo=AsyncMock(),
        relationship_repo=AsyncMock(),
    )

    items, total = await svc.list_pending(str(company.id))
    assert total == 1
    assert items[0]["source_excerpt"] == ""


# ---------------------------------------------------------------------------
# accept_fact tests — person
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_person_with_title(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, person_repo,
):
    """accept_fact on a person fact with comma parses name and title."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="person", value="Jane Smith, VP Engineering")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="person", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))

    assert entity_id is not None
    person = await person_repo.get_by_id(UUID(entity_id))
    assert person is not None
    assert person.name == "Jane Smith"
    assert person.title == "VP Engineering"
    assert person.company_id == company.id

    updated_fact = await fact_repo.get_by_id(fact.id)
    assert updated_fact.status == "accepted"
    assert updated_fact.reviewed_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_person_without_title(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, person_repo,
):
    """accept_fact on a person fact without comma uses full value as name."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="person", value="John Doe")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="person", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))

    person = await person_repo.get_by_id(UUID(entity_id))
    assert person.name == "John Doe"
    assert person.title is None


# ---------------------------------------------------------------------------
# accept_fact tests — functional-area
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_functional_area_new(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, area_repo,
):
    """accept_fact on a functional-area fact creates a new functional_areas row."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    area_name = f"Platform-{uuid4().hex[:6]}"

    facts = [LLMInferredFact(category="functional-area", value=area_name)]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="functional-area", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))

    assert entity_id is not None
    area = await area_repo.get_by_id(UUID(entity_id))
    assert area is not None
    assert area.name == area_name
    assert area.company_id == company.id


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_functional_area_duplicate_reuses_existing(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, area_repo,
):
    """accept_fact on a functional-area with existing name reuses the row."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    area_name = f"Engineering-{uuid4().hex[:6]}"

    # Create the area first
    existing = await area_repo.create(company_id=company.id, name=area_name)

    facts = [LLMInferredFact(category="functional-area", value=area_name)]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="functional-area", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id == str(existing.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_functional_area_duplicate_case_insensitive(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, area_repo,
):
    """accept_fact on functional-area with case-different name reuses existing."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    area_name = f"DataScience-{uuid4().hex[:6]}"

    existing = await area_repo.create(company_id=company.id, name=area_name)

    facts = [LLMInferredFact(category="functional-area", value=area_name.upper())]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="functional-area", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id == str(existing.id)


# ---------------------------------------------------------------------------
# accept_fact tests — action-item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_action_item(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, action_repo,
):
    """accept_fact on an action-item creates an action_items row."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="action-item", value="Set up CI/CD pipeline")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="action-item", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))

    assert entity_id is not None
    action_item = await action_repo.get_by_id(UUID(entity_id))
    assert action_item is not None
    assert action_item.description == "Set up CI/CD pipeline"
    assert action_item.source_id == source.id
    assert action_item.inferred_fact_id == fact.id
    assert action_item.company_id == company.id


# ---------------------------------------------------------------------------
# accept_fact tests — relationship
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_relationship_existing_persons(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, person_repo,
):
    """accept_fact on relationship resolves existing person names."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    sub_name = f"Sub-{uuid4().hex[:6]}"
    mgr_name = f"Mgr-{uuid4().hex[:6]}"
    sub = await person_repo.create(company_id=company.id, name=sub_name)
    mgr = await person_repo.create(company_id=company.id, name=mgr_name)

    facts = [
        LLMInferredFact(
            category="relationship",
            value=f"{sub_name} reports to {mgr_name}",
            subordinate=sub_name,
            manager=mgr_name,
        )
    ]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="relationship", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))

    assert entity_id is not None
    # Verify subordinate's reports_to was updated
    updated_sub = await person_repo.get_by_id(sub.id)
    assert updated_sub.reports_to_person_id == mgr.id


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_relationship_creates_stub_persons(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, person_repo,
):
    """accept_fact on relationship creates stub persons when names are unknown."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    sub_name = f"NewSub-{uuid4().hex[:6]}"
    mgr_name = f"NewMgr-{uuid4().hex[:6]}"

    facts = [
        LLMInferredFact(
            category="relationship",
            value=f"{sub_name} reports to {mgr_name}",
            subordinate=sub_name,
            manager=mgr_name,
        )
    ]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="relationship", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id is not None

    # Both stub persons should now exist
    subs = await person_repo.get_by_name_iexact(company.id, sub_name)
    mgrs = await person_repo.get_by_name_iexact(company.id, mgr_name)
    assert len(subs) == 1
    assert len(mgrs) == 1
    assert subs[0].title is None  # Stub — no title
    assert subs[0].reports_to_person_id == mgrs[0].id


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_relationship_duplicate_reuses_existing(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, person_repo,
):
    """accept_fact on duplicate relationship reuses existing row instead of crashing.

    Regression test: previously, accepting two relationship facts with the same
    (subordinate, manager) pair caused an IntegrityError on the
    uq_relationships_sub_mgr UNIQUE constraint.
    """
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    sub_name = f"DupRelSub-{uuid4().hex[:6]}"
    mgr_name = f"DupRelMgr-{uuid4().hex[:6]}"
    sub = await person_repo.create(company_id=company.id, name=sub_name)
    mgr = await person_repo.create(company_id=company.id, name=mgr_name)

    # Create two identical relationship facts
    facts = [
        LLMInferredFact(
            category="relationship",
            value=f"{sub_name} reports to {mgr_name}",
            subordinate=sub_name,
            manager=mgr_name,
        ),
        LLMInferredFact(
            category="relationship",
            value=f"{sub_name} reports to {mgr_name}",
            subordinate=sub_name,
            manager=mgr_name,
        ),
    ]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="relationship", limit=100, offset=0
    )
    assert len(rows) == 2

    # Accept the first — creates the relationship
    entity_id_1 = await review_service.accept_fact(str(company.id), str(rows[0].id))
    assert entity_id_1 is not None

    # Accept the second — should reuse the existing relationship, NOT crash
    entity_id_2 = await review_service.accept_fact(str(company.id), str(rows[1].id))
    assert entity_id_2 is not None
    assert entity_id_2 == entity_id_1  # Same relationship row reused

    # Verify subordinate's reports_to is still set
    updated_sub = await person_repo.get_by_id(sub.id)
    assert updated_sub.reports_to_person_id == mgr.id


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_relationship_malformed_value_no_separator(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, person_repo,
):
    """accept_fact on relationship with no '>' in inferred_value uses fallback.

    This is a defensive branch — in normal operation, save_facts always stores
    "sub > mgr". This test bypasses save_facts to directly insert a malformed
    inferred_value and verify the fallback behavior.
    """
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    # Directly insert a malformed relationship fact (bypassing save_facts)
    malformed_value = "Alice reports to Bob"  # no '>' separator
    rows = await fact_repo.create_many([{
        "source_id": source.id,
        "company_id": company.id,
        "category": "relationship",
        "inferred_value": malformed_value,
    }])
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))

    assert entity_id is not None
    # Fallback: entire value used as subordinate name, "Unknown" as manager
    subs = await person_repo.get_by_name_iexact(company.id, malformed_value)
    mgrs = await person_repo.get_by_name_iexact(company.id, "Unknown")
    assert len(subs) == 1
    assert len(mgrs) >= 1
    assert subs[0].reports_to_person_id == mgrs[0].id


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_relationship_multiple_person_matches_uses_first(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, person_repo,
):
    """accept_fact on relationship with multiple name matches uses the first."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    dup_name = f"DupPerson-{uuid4().hex[:6]}"
    mgr_name = f"UniqMgr-{uuid4().hex[:6]}"

    # Create two persons with the same name
    p1 = await person_repo.create(company_id=company.id, name=dup_name, title="VP")
    p2 = await person_repo.create(company_id=company.id, name=dup_name, title="Director")

    facts = [
        LLMInferredFact(
            category="relationship",
            value=f"{dup_name} reports to {mgr_name}",
            subordinate=dup_name,
            manager=mgr_name,
        )
    ]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="relationship", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id is not None

    # _resolve_person uses the first match from get_by_name_iexact.
    # Verify exactly one of the two duplicates had reports_to set.
    matches = await person_repo.get_by_name_iexact(company.id, dup_name)
    assert len(matches) == 2
    reports_to_set = [m for m in matches if m.reports_to_person_id is not None]
    assert len(reports_to_set) == 1


# ---------------------------------------------------------------------------
# accept_fact tests — categories with no entity creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_technology(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """accept_fact on technology marks accepted, no entity created."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="technology", value="GraphQL")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="technology", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id is None

    updated = await fact_repo.get_by_id(fact.id)
    assert updated.status == "accepted"
    assert updated.reviewed_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_process(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """accept_fact on process marks accepted, no entity created."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="process", value="Agile Scrum")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="process", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id is None

    updated = await fact_repo.get_by_id(fact.id)
    assert updated.status == "accepted"
    assert updated.reviewed_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_cgkra_kp(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """accept_fact on cgkra-kp marks accepted, no entity created."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="cgkra-kp", value="Scaling database writes")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="cgkra-kp", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id is None

    updated = await fact_repo.get_by_id(fact.id)
    assert updated.status == "accepted"
    assert updated.reviewed_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_swot_s(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """accept_fact on swot-s marks accepted, no entity created."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="swot-s", value="Strong engineering culture")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="swot-s", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id is None

    updated = await fact_repo.get_by_id(fact.id)
    assert updated.status == "accepted"
    assert updated.reviewed_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_other(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """accept_fact on 'other' category marks accepted, no entity created."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="other", value="Misc note about the company")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="other", limit=100, offset=0
    )
    fact = rows[0]

    entity_id = await review_service.accept_fact(str(company.id), str(fact.id))
    assert entity_id is None

    updated = await fact_repo.get_by_id(fact.id)
    assert updated.status == "accepted"
    assert updated.reviewed_at is not None


# ---------------------------------------------------------------------------
# accept_fact — error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_fact_not_found(
    db_session: AsyncSession, review_service: ReviewService
):
    """accept_fact with nonexistent fact_id raises FactNotFoundError."""
    company = await _make_company(db_session)
    with pytest.raises(FactNotFoundError):
        await review_service.accept_fact(str(company.id), str(uuid4()))


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_fact_wrong_company(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """accept_fact with wrong company_id raises FactCompanyMismatchError."""
    company = await _make_company(db_session)
    other_company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="technology", value="Redis-wrong-co")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="technology", limit=100, offset=0
    )
    fact = rows[0]

    with pytest.raises(FactCompanyMismatchError):
        await review_service.accept_fact(str(other_company.id), str(fact.id))


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_fact_not_pending(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """accept_fact on an already-accepted fact raises FactNotPendingError."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="technology", value="Terraform-double")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="technology", limit=100, offset=0
    )
    fact = rows[0]

    await review_service.accept_fact(str(company.id), str(fact.id))

    with pytest.raises(FactNotPendingError):
        await review_service.accept_fact(str(company.id), str(fact.id))


# ---------------------------------------------------------------------------
# dismiss_fact tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_fact(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """dismiss_fact sets status to dismissed and sets reviewed_at."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="technology", value="Ansible-dismiss")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="technology", limit=100, offset=0
    )
    fact = rows[0]

    await review_service.dismiss_fact(str(company.id), str(fact.id))

    updated = await fact_repo.get_by_id(fact.id)
    assert updated.status == "dismissed"
    assert updated.reviewed_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_fact_not_found(
    db_session: AsyncSession, review_service: ReviewService
):
    """dismiss_fact with nonexistent fact_id raises FactNotFoundError."""
    company = await _make_company(db_session)
    with pytest.raises(FactNotFoundError):
        await review_service.dismiss_fact(str(company.id), str(uuid4()))


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_fact_not_pending(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """dismiss_fact on an already-dismissed fact raises FactNotPendingError."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="technology", value="Puppet-dismiss-twice")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="technology", limit=100, offset=0
    )
    fact = rows[0]

    await review_service.dismiss_fact(str(company.id), str(fact.id))

    with pytest.raises(FactNotPendingError):
        await review_service.dismiss_fact(str(company.id), str(fact.id))


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_fact_wrong_company(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """dismiss_fact with wrong company_id raises FactCompanyMismatchError."""
    company = await _make_company(db_session)
    other_company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="technology", value="Chef-wrong-co-dismiss")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="technology", limit=100, offset=0
    )
    fact = rows[0]

    with pytest.raises(FactCompanyMismatchError):
        await review_service.dismiss_fact(str(other_company.id), str(fact.id))


# ---------------------------------------------------------------------------
# list_pending with status filter (accepted facts)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_status_accepted(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """list_pending with status='accepted' returns only accepted facts."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [LLMInferredFact(category="technology", value="Rust-accepted-list")]
    await review_service.save_facts(source.id, company.id, facts)

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="technology", limit=100, offset=0
    )
    fact = rows[0]
    await review_service.accept_fact(str(company.id), str(fact.id))

    items, total = await review_service.list_pending(
        str(company.id), status="accepted", category="technology"
    )
    assert total == 1
    assert items[0]["inferred_value"] == "Rust-accepted-list"
    assert items[0]["status"] == "accepted"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_status_and_category_combined(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """list_pending with both status and category filters correctly."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = [
        LLMInferredFact(category="person", value="FilterTest Person"),
        LLMInferredFact(category="technology", value="FilterTest Tech"),
    ]
    await review_service.save_facts(source.id, company.id, facts)

    rows_p, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="person", limit=100, offset=0
    )
    rows_t, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="technology", limit=100, offset=0
    )

    await review_service.accept_fact(str(company.id), str(rows_p[0].id))
    await review_service.accept_fact(str(company.id), str(rows_t[0].id))

    # Query accepted persons only
    items, total = await review_service.list_pending(
        str(company.id), status="accepted", category="person"
    )
    assert total == 1
    assert items[0]["inferred_value"] == "FilterTest Person"


# ---------------------------------------------------------------------------
# Duplicate file processing — accept all, re-process, re-accept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_file_save_facts_skips_existing_pending(
    db_session: AsyncSession, review_service: ReviewService, fact_repo,
):
    """save_facts skips facts that already exist as pending.

    Round 1: save_facts creates pending rows.
    Round 2: save_facts with identical facts creates zero new rows.
    """
    company = await _make_company(db_session)
    source1 = await _make_source(db_session, company.id)

    facts = [
        LLMInferredFact(category="person", value=f"PendingDedup-{uuid4().hex[:6]}, CTO"),
        LLMInferredFact(category="technology", value=f"Tech-{uuid4().hex[:6]}"),
    ]

    # ── Round 1 ──
    await review_service.save_facts(source1.id, company.id, facts)
    _, total1 = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert total1 == 2

    # ── Round 2: same facts, different source ──
    source2 = await _make_source(db_session, company.id)
    await review_service.save_facts(source2.id, company.id, facts)
    _, total2 = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert total2 == 2, f"Expected 2 (no new rows), got {total2}"


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_file_save_facts_skips_existing_accepted(
    db_session: AsyncSession, review_service: ReviewService, fact_repo,
):
    """save_facts skips facts that already exist as accepted.

    Round 1: save + accept all.
    Round 2: save_facts with identical facts creates zero new rows.
    """
    company = await _make_company(db_session)
    source1 = await _make_source(db_session, company.id)

    person_value = f"AcceptedDedup-{uuid4().hex[:6]}, CTO"
    area_name = f"AreaDedup-{uuid4().hex[:6]}"

    facts = [
        LLMInferredFact(category="person", value=person_value),
        LLMInferredFact(category="functional-area", value=area_name),
    ]

    # ── Round 1: save + accept ──
    await review_service.save_facts(source1.id, company.id, facts)
    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert len(rows) == 2
    for r in rows:
        await review_service.accept_fact(str(company.id), str(r.id))

    # Verify nothing pending
    _, pending_after = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert pending_after == 0

    # ── Round 2: same facts ──
    source2 = await _make_source(db_session, company.id)
    await review_service.save_facts(source2.id, company.id, facts)
    _, total2 = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert total2 == 0, f"Expected 0 new pending rows, got {total2}"


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_file_dismissed_fact_can_be_re_added(
    db_session: AsyncSession, review_service: ReviewService, fact_repo,
):
    """save_facts allows re-creating a fact that was previously dismissed.

    Dismissed facts are excluded from the dedup check — the user may want
    to reconsider.
    """
    company = await _make_company(db_session)
    source1 = await _make_source(db_session, company.id)

    tech_value = f"DismissedTech-{uuid4().hex[:6]}"
    facts = [LLMInferredFact(category="technology", value=tech_value)]

    # ── Round 1: save + dismiss ──
    await review_service.save_facts(source1.id, company.id, facts)
    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert len(rows) == 1
    await review_service.dismiss_fact(str(company.id), str(rows[0].id))

    # ── Round 2: same fact should be re-created (dismissed is excluded) ──
    source2 = await _make_source(db_session, company.id)
    await review_service.save_facts(source2.id, company.id, facts)
    _, total2 = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert total2 == 1, "Dismissed fact should be re-creatable"


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_file_full_scenario(
    db_session: AsyncSession, review_service: ReviewService,
    fact_repo, person_repo, area_repo, action_repo, relationship_repo,
):
    """Full scenario: process identical file, accept all, re-process.

    Simulates a user uploading the same notes file twice.  After accepting
    all facts from the first upload, save_facts on the second upload should
    produce zero new pending facts.
    """
    company = await _make_company(db_session)

    # Unique names so test is isolated
    suffix = uuid4().hex[:6]
    person_value = f"Alice-{suffix}, VP Engineering"
    person_name = f"Alice-{suffix}"
    area_name = f"Platform-{suffix}"
    action_desc = f"Migrate to K8s-{suffix}"
    sub_name = f"Bob-{suffix}"
    mgr_name = f"Carol-{suffix}"
    tech_value = f"GraphQL-{suffix}"

    facts = [
        LLMInferredFact(category="person", value=person_value),
        LLMInferredFact(category="functional-area", value=area_name),
        LLMInferredFact(category="action-item", value=action_desc),
        LLMInferredFact(
            category="relationship",
            value=f"{sub_name} reports to {mgr_name}",
            subordinate=sub_name,
            manager=mgr_name,
        ),
        LLMInferredFact(category="technology", value=tech_value),
    ]

    # ── Round 1: save + accept all ──
    source1 = await _make_source(db_session, company.id)
    await review_service.save_facts(source1.id, company.id, facts)
    pending1, total1 = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert total1 == 5

    for fact_row in pending1:
        await review_service.accept_fact(str(company.id), str(fact_row.id))

    # ── Round 2: save same facts — should produce zero new pending ──
    source2 = await _make_source(db_session, company.id)
    await review_service.save_facts(source2.id, company.id, facts)
    _, total2 = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert total2 == 0, f"Expected 0 new pending facts, got {total2}"

    # ── Verify: no duplicate entity rows ──
    persons = await person_repo.get_by_name_iexact(company.id, person_name)
    assert len(persons) == 1, f"Expected 1 person '{person_name}', got {len(persons)}"

    areas = await area_repo.list_by_company(company.id)
    area_matches = [a for a in areas if a.name.lower() == area_name.lower()]
    assert len(area_matches) == 1, f"Expected 1 area '{area_name}', got {len(area_matches)}"

    subs = await person_repo.get_by_name_iexact(company.id, sub_name)
    assert len(subs) == 1, f"Expected 1 person '{sub_name}', got {len(subs)}"

    mgrs = await person_repo.get_by_name_iexact(company.id, mgr_name)
    assert len(mgrs) == 1, f"Expected 1 person '{mgr_name}', got {len(mgrs)}"


# ---------------------------------------------------------------------------
# save_facts — raw_lines attribution (Unit 5 of Phase 2.5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_raw_lines_matched(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """save_facts with raw_lines — raw mode fact matched to originating line."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    raw_lines = [
        "Alice is the CEO and runs the company",
        "They use Kubernetes for container orchestration",
    ]
    facts = [
        LLMInferredFact(category="person", value="Alice"),
        LLMInferredFact(category="technology", value="Kubernetes"),
    ]
    await review_service.save_facts(
        source.id, company.id, facts, raw_lines=raw_lines
    )

    rows, total = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert total == 2
    # Find each fact and check source_line is the raw line (no prefix)
    by_cat = {r.category: r for r in rows}
    assert by_cat["person"].source_line == "Alice is the CEO and runs the company"
    assert by_cat["technology"].source_line == "They use Kubernetes for container orchestration"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_raw_lines_no_match(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """save_facts with raw_lines — no match found → source_line is null."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    raw_lines = [
        "The team discussed cloud migration strategies",
    ]
    # LLM extracted something not present in the raw text
    facts = [LLMInferredFact(category="technology", value="Terraform")]
    await review_service.save_facts(
        source.id, company.id, facts, raw_lines=raw_lines
    )

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert len(rows) == 1
    assert rows[0].source_line is None


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_hybrid_attribution(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """save_facts with both lines and raw_lines (hybrid) — tagged fact matched
    via lines, raw fact matched via raw_lines."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    lines = [
        ParsedLine(canonical_key="p", text="Alice Brown, CTO"),
    ]
    raw_lines = [
        "They use Docker for containerization",
    ]
    facts = [
        LLMInferredFact(category="person", value="Alice Brown, CTO"),
        LLMInferredFact(category="technology", value="Docker"),
    ]
    await review_service.save_facts(
        source.id, company.id, facts, lines=lines, raw_lines=raw_lines
    )

    rows, total = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert total == 2
    by_cat = {r.category: r for r in rows}
    # Tagged fact: source_line has canonical_key prefix
    assert by_cat["person"].source_line == "p: Alice Brown, CTO"
    # Raw fact: source_line is raw text (no prefix)
    assert by_cat["technology"].source_line == "They use Docker for containerization"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_raw_lines_relationship_match(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """save_facts with raw_lines — relationship fact matched against subordinate/manager."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    raw_lines = [
        "Jane reports to Bob in the engineering org",
        "The team ships weekly",
    ]
    facts = [
        LLMInferredFact(
            category="relationship",
            value="Jane reports to Bob",
            subordinate="Jane",
            manager="Bob",
        ),
    ]
    await review_service.save_facts(
        source.id, company.id, facts, raw_lines=raw_lines
    )

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", category="relationship", limit=100, offset=0
    )
    assert len(rows) == 1
    # Matched against "Jane" in the raw line — returns raw line as-is
    assert rows[0].source_line == "Jane reports to Bob in the engineering org"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_raw_lines_no_prefix_in_attribution(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """Raw-mode attribution returns the raw line as-is — no canonical_key: prefix
    is injected, unlike tagged-mode attribution which prepends 'key: '."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    raw_lines = [
        "Alice is the CEO and founded the company in 2019",
    ]
    facts = [LLMInferredFact(category="person", value="Alice")]
    await review_service.save_facts(
        source.id, company.id, facts, raw_lines=raw_lines
    )

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert len(rows) == 1
    # Raw line returned as-is — no "n:" or other prefix prepended
    assert rows[0].source_line == "Alice is the CEO and founded the company in 2019"
    assert not rows[0].source_line.startswith("n:")


# ---------------------------------------------------------------------------
# _match_raw_source_line — direct unit tests
# ---------------------------------------------------------------------------


def test_match_raw_source_line_case_insensitive():
    """Substring matching is case-insensitive."""
    fact = LLMInferredFact(category="technology", value="kubernetes")
    raw_lines = ["They use KUBERNETES for orchestration"]
    result = ReviewService._match_raw_source_line(fact, raw_lines)
    assert result == "They use KUBERNETES for orchestration"


def test_match_raw_source_line_first_match_wins():
    """When multiple lines match, the first one wins (preserves document order)."""
    fact = LLMInferredFact(category="technology", value="Docker")
    raw_lines = [
        "The team uses Docker for local development",
        "Docker is also used in CI/CD pipelines",
    ]
    result = ReviewService._match_raw_source_line(fact, raw_lines)
    assert result == "The team uses Docker for local development"


def test_match_raw_source_line_empty_list():
    """Empty raw_lines list returns None."""
    fact = LLMInferredFact(category="technology", value="Python")
    result = ReviewService._match_raw_source_line(fact, [])
    assert result is None


def test_match_raw_source_line_relationship():
    """Relationship facts match against subordinate or manager name."""
    fact = LLMInferredFact(
        category="relationship",
        value="Alice reports to Bob",
        subordinate="Alice",
        manager="Bob",
    )
    raw_lines = [
        "The engineering team is growing",
        "Alice reports directly to Bob in the org chart",
    ]
    result = ReviewService._match_raw_source_line(fact, raw_lines)
    assert result == "Alice reports directly to Bob in the org chart"


@pytest.mark.asyncio(loop_scope="session")
async def test_save_facts_hybrid_tagged_takes_precedence(
    db_session: AsyncSession, review_service: ReviewService, fact_repo
):
    """Hybrid attribution: fact value appears in both a tagged line and a raw line →
    tagged match takes precedence (best-effort per §9.5)."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    lines = [
        ParsedLine(canonical_key="t", text="Docker and containerization"),
    ]
    raw_lines = [
        "They also mentioned Docker in passing",
    ]
    facts = [LLMInferredFact(category="technology", value="Docker")]
    await review_service.save_facts(
        source.id, company.id, facts, lines=lines, raw_lines=raw_lines
    )

    rows, _ = await fact_repo.list_by_company(
        company.id, status="pending", limit=100, offset=0
    )
    assert len(rows) == 1
    # Tagged match takes precedence — has canonical_key prefix
    assert rows[0].source_line == "t: Docker and containerization"
