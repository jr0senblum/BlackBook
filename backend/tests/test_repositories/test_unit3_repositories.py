"""Tests for Phase 2 Unit 3 repositories.

Covers: SourceRepository, InferredFactRepository, FunctionalAreaRepository,
PersonRepository, RelationshipRepository, ActionItemRepository.
"""

from uuid import uuid4

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


# ── Fixtures ─────────────────────────────────────────────────────


@pytest_asyncio.fixture(loop_scope="session")
async def source_repo(db_session: AsyncSession) -> SourceRepository:
    return SourceRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def fact_repo(db_session: AsyncSession) -> InferredFactRepository:
    return InferredFactRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def area_repo(db_session: AsyncSession) -> FunctionalAreaRepository:
    return FunctionalAreaRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def person_repo(db_session: AsyncSession) -> PersonRepository:
    return PersonRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def relationship_repo(db_session: AsyncSession) -> RelationshipRepository:
    return RelationshipRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def action_item_repo(db_session: AsyncSession) -> ActionItemRepository:
    return ActionItemRepository(db_session)


async def _make_company(db_session: AsyncSession, name: str | None = None) -> Company:
    """Helper: insert a company row and return it."""
    company = Company(name=name or f"TestCo-{uuid4().hex[:8]}")
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


async def _make_source(
    db_session: AsyncSession,
    company_id,
    *,
    raw_content: str = "some raw text",
    filename: str = "notes.txt",
    status: str | None = None,
) -> Source:
    """Helper: insert a source row and return it."""
    source = Source(
        company_id=company_id,
        type="upload",
        filename_or_subject=filename,
        raw_content=raw_content,
    )
    if status is not None:
        source.status = status
    db_session.add(source)
    await db_session.flush()
    await db_session.refresh(source)
    return source


# ═════════════════════════════════════════════════════════════════
# SourceRepository
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_source_create(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """create() inserts a source and returns it with an ID."""
    company = await _make_company(db_session)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="test.txt",
        raw_content="nc: Foo\np: Alice, CEO",
        who="Jim",
        interaction_date="2025-01-15",
        src="meeting",
    )
    assert source.id is not None
    assert source.company_id == company.id
    assert source.type == "upload"
    assert source.filename_or_subject == "test.txt"
    assert source.raw_content == "nc: Foo\np: Alice, CEO"
    assert source.who == "Jim"
    assert source.interaction_date == "2025-01-15"
    assert source.src == "meeting"
    assert source.status == "pending"
    assert source.received_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_source_create_minimal(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """create() with only required fields defaults optional fields to None."""
    company = await _make_company(db_session)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject=None,
        raw_content="hello",
    )
    assert source.who is None
    assert source.interaction_date is None
    assert source.src is None
    assert source.file_path is None


@pytest.mark.asyncio(loop_scope="session")
async def test_source_get_by_id(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """get_by_id() returns the source when it exists."""
    company = await _make_company(db_session)
    created = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="f.txt",
        raw_content="data",
    )
    fetched = await source_repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.raw_content == "data"


@pytest.mark.asyncio(loop_scope="session")
async def test_source_get_by_id_not_found(
    source_repo: SourceRepository,
) -> None:
    """get_by_id() returns None for a non-existent ID."""
    result = await source_repo.get_by_id(uuid4())
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_source_list_by_company_basic(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """list_by_company() returns sources for the given company."""
    company = await _make_company(db_session)
    await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="a.txt",
        raw_content="aaa",
    )
    await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="b.txt",
        raw_content="bbb",
    )
    items, total = await source_repo.list_by_company(company.id)
    assert total == 2
    assert len(items) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_source_list_by_company_ordered_by_received_at_desc(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """list_by_company() returns sources ordered by received_at DESC."""
    from datetime import datetime, timezone, timedelta
    from app.models.base import Source as SourceModel

    company = await _make_company(db_session)
    # Create two sources with explicit different received_at timestamps
    # to guarantee ordering (within a single transaction server_default
    # can produce identical timestamps).
    now = datetime.now(timezone.utc)
    s1 = SourceModel(
        company_id=company.id,
        type="upload",
        filename_or_subject="first.txt",
        raw_content="first",
        received_at=now - timedelta(seconds=10),
    )
    s2 = SourceModel(
        company_id=company.id,
        type="upload",
        filename_or_subject="second.txt",
        raw_content="second",
        received_at=now,
    )
    db_session.add(s1)
    db_session.add(s2)
    await db_session.flush()
    await db_session.refresh(s1)
    await db_session.refresh(s2)

    items, _ = await source_repo.list_by_company(company.id)
    # Most recent first
    assert items[0].id == s2.id
    assert items[1].id == s1.id


@pytest.mark.asyncio(loop_scope="session")
async def test_source_list_by_company_status_filter(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """list_by_company() filters by status when specified."""
    company = await _make_company(db_session)
    await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="pending.txt",
        raw_content="p",
    )
    s2 = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="processed.txt",
        raw_content="done",
    )
    # Manually set status via update_status
    await source_repo.update_status(s2.id, status="processed")

    pending_items, pending_total = await source_repo.list_by_company(
        company.id, status="pending"
    )
    assert pending_total == 1
    assert pending_items[0].status == "pending"

    processed_items, processed_total = await source_repo.list_by_company(
        company.id, status="processed"
    )
    assert processed_total == 1
    assert processed_items[0].status == "processed"

    all_items, all_total = await source_repo.list_by_company(
        company.id, status="all"
    )
    assert all_total == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_source_list_by_company_pagination(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """list_by_company() respects limit and offset."""
    company = await _make_company(db_session)
    for i in range(5):
        await source_repo.create(
            company_id=company.id,
            type="upload",
            filename_or_subject=f"file{i}.txt",
            raw_content=f"content{i}",
        )
    items, total = await source_repo.list_by_company(
        company.id, limit=2, offset=0
    )
    assert total == 5
    assert len(items) == 2

    items2, total2 = await source_repo.list_by_company(
        company.id, limit=2, offset=3
    )
    assert total2 == 5
    assert len(items2) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_source_list_by_company_empty(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """list_by_company() returns empty list for a company with no sources."""
    company = await _make_company(db_session)
    items, total = await source_repo.list_by_company(company.id)
    assert total == 0
    assert items == []


@pytest.mark.asyncio(loop_scope="session")
async def test_source_update_status(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """update_status() changes the status and optional error/raw_llm_response."""
    company = await _make_company(db_session)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="f.txt",
        raw_content="data",
    )
    assert source.status == "pending"

    updated = await source_repo.update_status(
        source.id, status="failed", error="LLM timeout"
    )
    assert updated.status == "failed"
    assert updated.error == "LLM timeout"
    assert updated.raw_llm_response is None


@pytest.mark.asyncio(loop_scope="session")
async def test_source_update_status_with_raw_llm_response(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """update_status() stores raw_llm_response when provided."""
    company = await _make_company(db_session)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="g.txt",
        raw_content="data",
    )
    updated = await source_repo.update_status(
        source.id,
        status="failed",
        error="bad json",
        raw_llm_response='{"invalid": true}',
    )
    assert updated.raw_llm_response == '{"invalid": true}'


@pytest.mark.asyncio(loop_scope="session")
async def test_source_update_status_to_processed(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """update_status() to processed clears error."""
    company = await _make_company(db_session)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="h.txt",
        raw_content="data",
    )
    updated = await source_repo.update_status(source.id, status="processed")
    assert updated.status == "processed"
    assert updated.error is None


@pytest.mark.asyncio(loop_scope="session")
async def test_source_update_status_not_found(
    source_repo: SourceRepository,
) -> None:
    """update_status() raises ValueError for a non-existent source."""
    with pytest.raises(ValueError, match="Source not found"):
        await source_repo.update_status(uuid4(), status="processed")


@pytest.mark.asyncio(loop_scope="session")
async def test_source_list_by_company_cross_company_isolation(
    db_session: AsyncSession, source_repo: SourceRepository
) -> None:
    """list_by_company() does not return sources from a different company."""
    company1 = await _make_company(db_session)
    company2 = await _make_company(db_session)
    await source_repo.create(
        company_id=company1.id,
        type="upload",
        filename_or_subject="c1.txt",
        raw_content="belongs to company1",
    )
    await source_repo.create(
        company_id=company2.id,
        type="upload",
        filename_or_subject="c2.txt",
        raw_content="belongs to company2",
    )
    items1, total1 = await source_repo.list_by_company(company1.id)
    assert total1 == 1
    assert items1[0].raw_content == "belongs to company1"

    items2, total2 = await source_repo.list_by_company(company2.id)
    assert total2 == 1
    assert items2[0].raw_content == "belongs to company2"


# ═════════════════════════════════════════════════════════════════
# InferredFactRepository
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_create_many(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """create_many() bulk inserts facts and returns them with IDs."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)

    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "person",
            "inferred_value": "Alice, CEO",
        },
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "technology",
            "inferred_value": "Kubernetes",
        },
    ])
    assert len(facts) == 2
    assert facts[0].id is not None
    assert facts[0].category == "person"
    assert facts[0].inferred_value == "Alice, CEO"
    assert facts[0].status == "pending"
    assert facts[1].category == "technology"


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_create_many_empty(
    fact_repo: InferredFactRepository,
) -> None:
    """create_many() with an empty list returns an empty list."""
    facts = await fact_repo.create_many([])
    assert facts == []


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_get_by_id(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """get_by_id() returns the fact when it exists."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    created = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "process",
            "inferred_value": "Agile",
        },
    ])
    fetched = await fact_repo.get_by_id(created[0].id)
    assert fetched is not None
    assert fetched.inferred_value == "Agile"


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_get_by_id_not_found(
    fact_repo: InferredFactRepository,
) -> None:
    """get_by_id() returns None for a non-existent ID."""
    result = await fact_repo.get_by_id(uuid4())
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_list_by_company_default_pending(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """list_by_company() returns only pending facts by default."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "person",
            "inferred_value": "Bob",
        },
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "technology",
            "inferred_value": "Docker",
        },
    ])
    # Accept the first fact
    from datetime import datetime, timezone

    await fact_repo.update_status(
        facts[0].id, status="accepted", reviewed_at=datetime.now(timezone.utc)
    )

    items, total = await fact_repo.list_by_company(company.id)
    assert total == 1
    assert items[0].inferred_value == "Docker"


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_list_by_company_status_filter(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """list_by_company() filters by status parameter."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "person",
            "inferred_value": "Carol",
        },
    ])
    from datetime import datetime, timezone

    await fact_repo.update_status(
        facts[0].id, status="accepted", reviewed_at=datetime.now(timezone.utc)
    )

    accepted_items, accepted_total = await fact_repo.list_by_company(
        company.id, status="accepted"
    )
    assert accepted_total == 1
    assert accepted_items[0].status == "accepted"

    pending_items, pending_total = await fact_repo.list_by_company(
        company.id, status="pending"
    )
    assert pending_total == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_list_by_company_category_filter(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """list_by_company() filters by category when specified."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "person",
            "inferred_value": "Dave",
        },
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "technology",
            "inferred_value": "React",
        },
    ])

    person_items, person_total = await fact_repo.list_by_company(
        company.id, category="person"
    )
    assert person_total == 1
    assert person_items[0].category == "person"


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_list_by_company_pagination(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """list_by_company() respects limit and offset."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "technology",
            "inferred_value": f"Tech-{i}",
        }
        for i in range(5)
    ])

    items, total = await fact_repo.list_by_company(
        company.id, limit=2, offset=0
    )
    assert total == 5
    assert len(items) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_list_by_company_ordered_by_created_at_asc(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """list_by_company() returns facts ordered by created_at ASC."""
    from datetime import datetime, timezone, timedelta
    from app.models.base import InferredFact as InferredFactModel

    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    now = datetime.now(timezone.utc)

    # Create with explicit timestamps to guarantee ordering
    f1 = InferredFactModel(
        source_id=source.id,
        company_id=company.id,
        category="technology",
        inferred_value="First",
        created_at=now - timedelta(seconds=10),
    )
    f2 = InferredFactModel(
        source_id=source.id,
        company_id=company.id,
        category="technology",
        inferred_value="Second",
        created_at=now,
    )
    db_session.add(f1)
    db_session.add(f2)
    await db_session.flush()
    await db_session.refresh(f1)
    await db_session.refresh(f2)

    items, _ = await fact_repo.list_by_company(company.id)
    assert items[0].inferred_value == "First"
    assert items[1].inferred_value == "Second"


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_list_by_company_empty(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """list_by_company() returns empty list for a company with no facts."""
    company = await _make_company(db_session)
    items, total = await fact_repo.list_by_company(company.id)
    assert total == 0
    assert items == []


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_update_status_accepted(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """update_status() sets accepted status and reviewed_at."""
    from datetime import datetime, timezone

    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "person",
            "inferred_value": "Eve",
        },
    ])
    now = datetime.now(timezone.utc)
    updated = await fact_repo.update_status(
        facts[0].id, status="accepted", reviewed_at=now
    )
    assert updated.status == "accepted"
    assert updated.reviewed_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_update_status_dismissed(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """update_status() sets dismissed status."""
    from datetime import datetime, timezone

    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "other",
            "inferred_value": "misc note",
        },
    ])
    updated = await fact_repo.update_status(
        facts[0].id,
        status="dismissed",
        reviewed_at=datetime.now(timezone.utc),
    )
    assert updated.status == "dismissed"


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_update_status_with_merge_fields(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """update_status() stores merged_into_entity_type and merged_into_entity_id."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "functional-area",
            "inferred_value": "Engineering",
        },
    ])
    from datetime import datetime, timezone

    entity_id = uuid4()
    updated = await fact_repo.update_status(
        facts[0].id,
        status="merged",
        reviewed_at=datetime.now(timezone.utc),
        merged_into_entity_type="functional_area",
        merged_into_entity_id=entity_id,
    )
    assert updated.status == "merged"
    assert updated.merged_into_entity_type == "functional_area"
    assert updated.merged_into_entity_id == entity_id


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_update_status_corrected(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """update_status() stores corrected_value when provided."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "person",
            "inferred_value": "Alic",
        },
    ])
    from datetime import datetime, timezone

    updated = await fact_repo.update_status(
        facts[0].id,
        status="corrected",
        reviewed_at=datetime.now(timezone.utc),
        corrected_value="Alice",
    )
    assert updated.status == "corrected"
    assert updated.corrected_value == "Alice"


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_update_status_not_found(
    fact_repo: InferredFactRepository,
) -> None:
    """update_status() raises ValueError for a non-existent fact."""
    from datetime import datetime, timezone

    with pytest.raises(ValueError, match="InferredFact not found"):
        await fact_repo.update_status(
            uuid4(),
            status="accepted",
            reviewed_at=datetime.now(timezone.utc),
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_list_by_company_cross_company_isolation(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """list_by_company() does not return facts from a different company."""
    company1 = await _make_company(db_session)
    company2 = await _make_company(db_session)
    source1 = await _make_source(db_session, company1.id)
    source2 = await _make_source(db_session, company2.id)
    await fact_repo.create_many([
        {
            "source_id": source1.id,
            "company_id": company1.id,
            "category": "person",
            "inferred_value": "Alice",
        },
    ])
    await fact_repo.create_many([
        {
            "source_id": source2.id,
            "company_id": company2.id,
            "category": "technology",
            "inferred_value": "Kubernetes",
        },
    ])
    items1, total1 = await fact_repo.list_by_company(company1.id)
    assert total1 == 1
    assert items1[0].inferred_value == "Alice"

    items2, total2 = await fact_repo.list_by_company(company2.id)
    assert total2 == 1
    assert items2[0].inferred_value == "Kubernetes"


@pytest.mark.asyncio(loop_scope="session")
async def test_fact_list_by_company_status_and_category_combined(
    db_session: AsyncSession, fact_repo: InferredFactRepository
) -> None:
    """list_by_company() filters by both status and category simultaneously."""
    from datetime import datetime, timezone

    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "person",
            "inferred_value": "PendingPerson",
        },
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "technology",
            "inferred_value": "PendingTech",
        },
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "person",
            "inferred_value": "AcceptedPerson",
        },
    ])
    # Accept the third fact (person)
    await fact_repo.update_status(
        facts[2].id,
        status="accepted",
        reviewed_at=datetime.now(timezone.utc),
    )

    # pending + person → only PendingPerson
    items, total = await fact_repo.list_by_company(
        company.id, status="pending", category="person"
    )
    assert total == 1
    assert items[0].inferred_value == "PendingPerson"

    # accepted + person → only AcceptedPerson
    items2, total2 = await fact_repo.list_by_company(
        company.id, status="accepted", category="person"
    )
    assert total2 == 1
    assert items2[0].inferred_value == "AcceptedPerson"

    # pending + technology → only PendingTech
    items3, total3 = await fact_repo.list_by_company(
        company.id, status="pending", category="technology"
    )
    assert total3 == 1
    assert items3[0].inferred_value == "PendingTech"

    # accepted + technology → nothing
    items4, total4 = await fact_repo.list_by_company(
        company.id, status="accepted", category="technology"
    )
    assert total4 == 0
    assert items4 == []


# ═════════════════════════════════════════════════════════════════
# FunctionalAreaRepository
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_area_create(
    db_session: AsyncSession, area_repo: FunctionalAreaRepository
) -> None:
    """create() inserts a functional area and returns it."""
    company = await _make_company(db_session)
    area = await area_repo.create(company_id=company.id, name="Engineering")
    assert area.id is not None
    assert area.company_id == company.id
    assert area.name == "Engineering"
    assert area.created_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_area_get_by_id(
    db_session: AsyncSession, area_repo: FunctionalAreaRepository
) -> None:
    """get_by_id() returns the area when it exists."""
    company = await _make_company(db_session)
    created = await area_repo.create(company_id=company.id, name="Sales")
    fetched = await area_repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.name == "Sales"


@pytest.mark.asyncio(loop_scope="session")
async def test_area_get_by_id_not_found(
    area_repo: FunctionalAreaRepository,
) -> None:
    """get_by_id() returns None for a non-existent ID."""
    result = await area_repo.get_by_id(uuid4())
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_area_get_by_name_iexact_found(
    db_session: AsyncSession, area_repo: FunctionalAreaRepository
) -> None:
    """get_by_name_iexact() finds an area with case-insensitive match."""
    company = await _make_company(db_session)
    await area_repo.create(company_id=company.id, name="Marketing")
    found = await area_repo.get_by_name_iexact(company.id, "marketing")
    assert found is not None
    assert found.name == "Marketing"


@pytest.mark.asyncio(loop_scope="session")
async def test_area_get_by_name_iexact_upper(
    db_session: AsyncSession, area_repo: FunctionalAreaRepository
) -> None:
    """get_by_name_iexact() matches regardless of casing."""
    company = await _make_company(db_session)
    await area_repo.create(company_id=company.id, name="Finance")
    found = await area_repo.get_by_name_iexact(company.id, "FINANCE")
    assert found is not None
    assert found.name == "Finance"


@pytest.mark.asyncio(loop_scope="session")
async def test_area_get_by_name_iexact_not_found(
    db_session: AsyncSession, area_repo: FunctionalAreaRepository
) -> None:
    """get_by_name_iexact() returns None when no match exists."""
    company = await _make_company(db_session)
    result = await area_repo.get_by_name_iexact(company.id, "NonExistent")
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_area_get_by_name_iexact_different_company(
    db_session: AsyncSession, area_repo: FunctionalAreaRepository
) -> None:
    """get_by_name_iexact() does not match areas from a different company."""
    company1 = await _make_company(db_session)
    company2 = await _make_company(db_session)
    await area_repo.create(company_id=company1.id, name="Legal")
    result = await area_repo.get_by_name_iexact(company2.id, "Legal")
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_area_list_by_company(
    db_session: AsyncSession, area_repo: FunctionalAreaRepository
) -> None:
    """list_by_company() returns all areas for a company, ordered by name."""
    company = await _make_company(db_session)
    await area_repo.create(company_id=company.id, name="Zulu")
    await area_repo.create(company_id=company.id, name="Alpha")
    areas = await area_repo.list_by_company(company.id)
    assert len(areas) == 2
    assert areas[0].name == "Alpha"
    assert areas[1].name == "Zulu"


@pytest.mark.asyncio(loop_scope="session")
async def test_area_list_by_company_empty(
    db_session: AsyncSession, area_repo: FunctionalAreaRepository
) -> None:
    """list_by_company() returns empty list when no areas exist."""
    company = await _make_company(db_session)
    areas = await area_repo.list_by_company(company.id)
    assert areas == []


# ═════════════════════════════════════════════════════════════════
# PersonRepository
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_person_create(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """create() inserts a person and returns it with an ID."""
    company = await _make_company(db_session)
    person = await person_repo.create(
        company_id=company.id,
        name="Alice Smith",
        title="VP Engineering",
    )
    assert person.id is not None
    assert person.company_id == company.id
    assert person.name == "Alice Smith"
    assert person.title == "VP Engineering"
    assert person.primary_area_id is None
    assert person.reports_to_person_id is None
    assert person.created_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_person_create_with_area_and_reports_to(
    db_session: AsyncSession,
    person_repo: PersonRepository,
    area_repo: FunctionalAreaRepository,
) -> None:
    """create() with optional area and reports_to fields."""
    company = await _make_company(db_session)
    area = await area_repo.create(company_id=company.id, name="Engineering")
    manager = await person_repo.create(
        company_id=company.id, name="Bob Manager"
    )
    person = await person_repo.create(
        company_id=company.id,
        name="Carol Worker",
        title="Engineer",
        primary_area_id=area.id,
        reports_to_person_id=manager.id,
    )
    assert person.primary_area_id == area.id
    assert person.reports_to_person_id == manager.id


@pytest.mark.asyncio(loop_scope="session")
async def test_person_create_minimal(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """create() with only required fields defaults title to None."""
    company = await _make_company(db_session)
    person = await person_repo.create(
        company_id=company.id, name="Stub Person"
    )
    assert person.title is None


@pytest.mark.asyncio(loop_scope="session")
async def test_person_get_by_id(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """get_by_id() returns the person when it exists."""
    company = await _make_company(db_session)
    created = await person_repo.create(
        company_id=company.id, name="Dave Test"
    )
    fetched = await person_repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.name == "Dave Test"


@pytest.mark.asyncio(loop_scope="session")
async def test_person_get_by_id_not_found(
    person_repo: PersonRepository,
) -> None:
    """get_by_id() returns None for a non-existent ID."""
    result = await person_repo.get_by_id(uuid4())
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_person_get_by_name_iexact_single_match(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """get_by_name_iexact() returns a list with one match."""
    company = await _make_company(db_session)
    await person_repo.create(company_id=company.id, name="Eve Johnson")
    results = await person_repo.get_by_name_iexact(company.id, "eve johnson")
    assert len(results) == 1
    assert results[0].name == "Eve Johnson"


@pytest.mark.asyncio(loop_scope="session")
async def test_person_get_by_name_iexact_multiple_matches(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """get_by_name_iexact() can return multiple matches (no unique constraint on name)."""
    company = await _make_company(db_session)
    await person_repo.create(
        company_id=company.id, name="John Smith", title="CEO"
    )
    await person_repo.create(
        company_id=company.id, name="John Smith", title="Intern"
    )
    results = await person_repo.get_by_name_iexact(company.id, "john smith")
    assert len(results) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_person_get_by_name_iexact_no_match(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """get_by_name_iexact() returns empty list when no match."""
    company = await _make_company(db_session)
    results = await person_repo.get_by_name_iexact(company.id, "Nobody")
    assert results == []


@pytest.mark.asyncio(loop_scope="session")
async def test_person_get_by_name_iexact_different_company(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """get_by_name_iexact() does not match persons from a different company."""
    company1 = await _make_company(db_session)
    company2 = await _make_company(db_session)
    await person_repo.create(company_id=company1.id, name="Frank Solo")
    results = await person_repo.get_by_name_iexact(company2.id, "Frank Solo")
    assert results == []


@pytest.mark.asyncio(loop_scope="session")
async def test_person_list_by_company(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """list_by_company() returns all persons ordered by name."""
    company = await _make_company(db_session)
    await person_repo.create(company_id=company.id, name="Zara")
    await person_repo.create(company_id=company.id, name="Anna")
    persons = await person_repo.list_by_company(company.id)
    assert len(persons) == 2
    assert persons[0].name == "Anna"
    assert persons[1].name == "Zara"


@pytest.mark.asyncio(loop_scope="session")
async def test_person_list_by_company_empty(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """list_by_company() returns empty list when no persons exist."""
    company = await _make_company(db_session)
    persons = await person_repo.list_by_company(company.id)
    assert persons == []


@pytest.mark.asyncio(loop_scope="session")
async def test_person_update_reports_to(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """update_reports_to() sets the reports_to_person_id."""
    company = await _make_company(db_session)
    manager = await person_repo.create(
        company_id=company.id, name="Grace Manager"
    )
    subordinate = await person_repo.create(
        company_id=company.id, name="Heidi Worker"
    )
    assert subordinate.reports_to_person_id is None

    updated = await person_repo.update_reports_to(subordinate.id, manager.id)
    assert updated.reports_to_person_id == manager.id


@pytest.mark.asyncio(loop_scope="session")
async def test_person_update_reports_to_clear(
    db_session: AsyncSession, person_repo: PersonRepository
) -> None:
    """update_reports_to() can clear the reports_to by setting None."""
    company = await _make_company(db_session)
    manager = await person_repo.create(
        company_id=company.id, name="Ivan Boss"
    )
    subordinate = await person_repo.create(
        company_id=company.id,
        name="Judy Worker",
        reports_to_person_id=manager.id,
    )
    # Refresh to ensure we see the initial state
    fetched = await person_repo.get_by_id(subordinate.id)
    assert fetched is not None
    assert fetched.reports_to_person_id == manager.id

    updated = await person_repo.update_reports_to(subordinate.id, None)
    assert updated.reports_to_person_id is None


@pytest.mark.asyncio(loop_scope="session")
async def test_person_update_reports_to_not_found(
    person_repo: PersonRepository,
) -> None:
    """update_reports_to() raises ValueError for a non-existent person."""
    with pytest.raises(ValueError, match="Person not found"):
        await person_repo.update_reports_to(uuid4(), uuid4())


# ═════════════════════════════════════════════════════════════════
# RelationshipRepository
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_relationship_create(
    db_session: AsyncSession,
    person_repo: PersonRepository,
    relationship_repo: RelationshipRepository,
) -> None:
    """create() inserts a relationship and returns it."""
    company = await _make_company(db_session)
    manager = await person_repo.create(
        company_id=company.id, name="Kim Manager"
    )
    subordinate = await person_repo.create(
        company_id=company.id, name="Leo Worker"
    )
    rel = await relationship_repo.create(
        company_id=company.id,
        subordinate_person_id=subordinate.id,
        manager_person_id=manager.id,
    )
    assert rel.id is not None
    assert rel.company_id == company.id
    assert rel.subordinate_person_id == subordinate.id
    assert rel.manager_person_id == manager.id
    assert rel.inferred_fact_id is None
    assert rel.created_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_relationship_create_with_fact_id(
    db_session: AsyncSession,
    person_repo: PersonRepository,
    relationship_repo: RelationshipRepository,
    fact_repo: InferredFactRepository,
) -> None:
    """create() stores the optional inferred_fact_id."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    manager = await person_repo.create(
        company_id=company.id, name="Mia Boss"
    )
    subordinate = await person_repo.create(
        company_id=company.id, name="Nate Report"
    )
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "relationship",
            "inferred_value": "Nate Report > Mia Boss",
        },
    ])
    rel = await relationship_repo.create(
        company_id=company.id,
        subordinate_person_id=subordinate.id,
        manager_person_id=manager.id,
        inferred_fact_id=facts[0].id,
    )
    assert rel.inferred_fact_id == facts[0].id


# ═════════════════════════════════════════════════════════════════
# ActionItemRepository
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_action_item_create(
    db_session: AsyncSession,
    action_item_repo: ActionItemRepository,
) -> None:
    """create() inserts an action item and returns it."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    item = await action_item_repo.create(
        company_id=company.id,
        description="Follow up on contract",
        source_id=source.id,
    )
    assert item.id is not None
    assert item.company_id == company.id
    assert item.description == "Follow up on contract"
    assert item.source_id == source.id
    assert item.status == "open"
    assert item.person_id is None
    assert item.functional_area_id is None
    assert item.inferred_fact_id is None
    assert item.created_at is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_action_item_create_with_all_optional(
    db_session: AsyncSession,
    action_item_repo: ActionItemRepository,
    person_repo: PersonRepository,
    area_repo: FunctionalAreaRepository,
    fact_repo: InferredFactRepository,
) -> None:
    """create() with all optional foreign keys populated."""
    company = await _make_company(db_session)
    source = await _make_source(db_session, company.id)
    person = await person_repo.create(
        company_id=company.id, name="Oscar Action"
    )
    area = await area_repo.create(company_id=company.id, name="Operations")
    facts = await fact_repo.create_many([
        {
            "source_id": source.id,
            "company_id": company.id,
            "category": "action-item",
            "inferred_value": "Review proposal",
        },
    ])
    item = await action_item_repo.create(
        company_id=company.id,
        description="Review proposal",
        source_id=source.id,
        inferred_fact_id=facts[0].id,
        person_id=person.id,
        functional_area_id=area.id,
    )
    assert item.source_id == source.id
    assert item.inferred_fact_id == facts[0].id
    assert item.person_id == person.id
    assert item.functional_area_id == area.id


@pytest.mark.asyncio(loop_scope="session")
async def test_action_item_create_minimal(
    db_session: AsyncSession,
    action_item_repo: ActionItemRepository,
) -> None:
    """create() with only required fields."""
    company = await _make_company(db_session)
    item = await action_item_repo.create(
        company_id=company.id,
        description="Minimal action",
    )
    assert item.source_id is None
    assert item.inferred_fact_id is None
    assert item.person_id is None
    assert item.functional_area_id is None


@pytest.mark.asyncio(loop_scope="session")
async def test_action_item_get_by_id(
    db_session: AsyncSession,
    action_item_repo: ActionItemRepository,
) -> None:
    """get_by_id() returns the action item when it exists."""
    company = await _make_company(db_session)
    created = await action_item_repo.create(
        company_id=company.id,
        description="Find by ID test",
    )
    fetched = await action_item_repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.description == "Find by ID test"


@pytest.mark.asyncio(loop_scope="session")
async def test_action_item_get_by_id_not_found(
    action_item_repo: ActionItemRepository,
) -> None:
    """get_by_id() returns None for a non-existent ID."""
    result = await action_item_repo.get_by_id(uuid4())
    assert result is None
