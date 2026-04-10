"""Tests for IngestionService — routing, upload, process, retry, sanitization."""

import os
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.exceptions import (
    InferenceApiError,
    InferenceValidationError,
    RoutingError,
    SourceNotFailedError,
    SourceNotFoundError,
)
from app.repositories.company_repository import CompanyRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.source_repository import SourceRepository
from app.services.ingestion_service import IngestionService, sanitize_filename


# ── Fixtures ─────────────────────────────────────────────────────


@pytest_asyncio.fixture(loop_scope="session")
async def source_repo(db_session: AsyncSession) -> SourceRepository:
    return SourceRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def company_repo(db_session: AsyncSession) -> CompanyRepository:
    return CompanyRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def inferred_fact_repo(db_session: AsyncSession) -> InferredFactRepository:
    return InferredFactRepository(db_session)


@pytest_asyncio.fixture(loop_scope="session")
async def test_settings(tmp_path_factory) -> Settings:
    """Settings with a temporary data_dir for file writes."""
    tmp = tmp_path_factory.mktemp("blackbook_data")
    return Settings(database_url="unused", data_dir=str(tmp))


@pytest_asyncio.fixture(loop_scope="session")
async def mock_inference() -> AsyncMock:
    return AsyncMock()


@pytest_asyncio.fixture(loop_scope="session")
async def mock_review() -> AsyncMock:
    return AsyncMock()


@pytest_asyncio.fixture(loop_scope="session")
async def mock_queue() -> AsyncMock:
    return AsyncMock()


@pytest_asyncio.fixture(loop_scope="session")
async def ingestion_service(
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    mock_inference: AsyncMock,
    mock_review: AsyncMock,
    mock_queue: AsyncMock,
    test_settings: Settings,
) -> IngestionService:
    return IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inference,
        review_service=mock_review,
        ingestion_queue=mock_queue,
        settings=test_settings,
    )


# ═════════════════════════════════════════════════════════════════
# sanitize_filename
# ═════════════════════════════════════════════════════════════════


def test_sanitize_filename_basic() -> None:
    """Strips invalid characters and keeps valid ones."""
    assert sanitize_filename("hello world.txt") == "helloworld.txt"


def test_sanitize_filename_special_chars() -> None:
    """Strips special characters."""
    assert sanitize_filename("my file (1).txt") == "myfile1.txt"


def test_sanitize_filename_preserves_dash_dot_underscore() -> None:
    """Preserves dashes, dots, and underscores."""
    assert sanitize_filename("my-file_v2.0.txt") == "my-file_v2.0.txt"


def test_sanitize_filename_truncates() -> None:
    """Truncates to 100 characters."""
    long_name = "a" * 150 + ".txt"
    result = sanitize_filename(long_name)
    assert len(result) == 100


def test_sanitize_filename_empty() -> None:
    """Empty input returns empty string."""
    assert sanitize_filename("") == ""


def test_sanitize_filename_all_invalid() -> None:
    """All invalid characters returns empty string."""
    assert sanitize_filename("!@#$%^&*()") == ""


# ═════════════════════════════════════════════════════════════════
# Routing — nc: (new company)
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_nc_creates_company(
    ingestion_service: IngestionService,
    company_repo: CompanyRepository,
) -> None:
    """nc: with a new name creates the company and returns a source_id."""
    name = f"NCTest-{uuid4().hex[:8]}"
    content = f"nc: {name}\np: Alice, CEO"
    source_id = await ingestion_service.ingest_upload(content, "notes.txt")
    assert source_id is not None

    # Verify company was created
    company = await company_repo.get_by_name_iexact(name)
    assert company is not None


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_nc_existing_name_fails(
    ingestion_service: IngestionService,
    company_repo: CompanyRepository,
) -> None:
    """nc: with an already-existing name raises RoutingError."""
    name = f"NCExist-{uuid4().hex[:8]}"
    await company_repo.create(name)
    content = f"nc: {name}\np: Bob"
    with pytest.raises(RoutingError, match="company name already exists"):
        await ingestion_service.ingest_upload(content, "notes.txt")


# ═════════════════════════════════════════════════════════════════
# Routing — c: (existing company by name)
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_c_existing_name(
    ingestion_service: IngestionService,
    company_repo: CompanyRepository,
    source_repo: SourceRepository,
) -> None:
    """c: with a matching name routes to that company."""
    name = f"CRoute-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    content = f"c: {name}\np: Carol"
    source_id = await ingestion_service.ingest_upload(content, "notes.txt")

    # Verify source was created under the right company
    source = await source_repo.get_by_id(UUID(source_id))
    assert source is not None
    assert source.company_id == company.id


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_c_no_match_fails(
    ingestion_service: IngestionService,
) -> None:
    """c: with no matching company name raises RoutingError."""
    bogus_name = f"NoSuchCompany-{uuid4().hex[:8]}"
    content = f"c: {bogus_name}\np: Dave"
    with pytest.raises(RoutingError, match="no company found with name"):
        await ingestion_service.ingest_upload(content, "notes.txt")


# ═════════════════════════════════════════════════════════════════
# Routing — cid: (existing company by ID)
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_cid_valid(
    ingestion_service: IngestionService,
    company_repo: CompanyRepository,
    source_repo: SourceRepository,
) -> None:
    """cid: with a valid UUID routes to that company."""
    name = f"CIDRoute-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    content = f"cid: {company.id}\np: Eve"
    source_id = await ingestion_service.ingest_upload(content, "notes.txt")
    source = await source_repo.get_by_id(UUID(source_id))
    assert source is not None
    assert source.company_id == company.id


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_cid_invalid_uuid_fails(
    ingestion_service: IngestionService,
) -> None:
    """cid: with an invalid UUID raises RoutingError."""
    content = "cid: not-a-uuid\np: Frank"
    with pytest.raises(RoutingError, match="no company found with id"):
        await ingestion_service.ingest_upload(content, "notes.txt")


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_cid_nonexistent_fails(
    ingestion_service: IngestionService,
) -> None:
    """cid: with a valid UUID that doesn't exist raises RoutingError."""
    content = f"cid: {uuid4()}\np: Grace"
    with pytest.raises(RoutingError, match="no company found with id"):
        await ingestion_service.ingest_upload(content, "notes.txt")


# ═════════════════════════════════════════════════════════════════
# Routing — edge cases
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_no_prefix_no_param_fails(
    ingestion_service: IngestionService,
) -> None:
    """No routing prefix and no company_id param raises RoutingError."""
    content = "p: Hank, VP\ntech: Python"
    with pytest.raises(RoutingError, match="no company routing prefix"):
        await ingestion_service.ingest_upload(content, "notes.txt")


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_multiple_prefixes_fails(
    ingestion_service: IngestionService,
    company_repo: CompanyRepository,
) -> None:
    """Multiple routing prefixes raises RoutingError."""
    name = f"Multi-{uuid4().hex[:8]}"
    await company_repo.create(name)
    content = f"nc: NewOne\nc: {name}\np: Ivy"
    with pytest.raises(RoutingError, match="multiple routing prefixes"):
        await ingestion_service.ingest_upload(content, "notes.txt")


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_company_id_param_takes_precedence(
    ingestion_service: IngestionService,
    company_repo: CompanyRepository,
    source_repo: SourceRepository,
) -> None:
    """company_id param takes precedence over in-file routing prefix."""
    name = f"ParamPrecedence-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    # File says nc: (new company), but param overrides with cid
    content = "nc: ShouldBeIgnored\np: Jack"
    source_id = await ingestion_service.ingest_upload(
        content, "notes.txt", company_id=str(company.id)
    )
    source = await source_repo.get_by_id(UUID(source_id))
    assert source is not None
    assert source.company_id == company.id


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_company_id_param_invalid_uuid(
    ingestion_service: IngestionService,
) -> None:
    """company_id param with an invalid UUID raises RoutingError."""
    content = "p: Nobody"
    with pytest.raises(RoutingError, match="no company found with id"):
        await ingestion_service.ingest_upload(
            content, "notes.txt", company_id="not-a-uuid"
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_routing_company_id_param_nonexistent(
    ingestion_service: IngestionService,
) -> None:
    """company_id param with a valid but non-existent UUID raises RoutingError."""
    content = "p: Nobody"
    with pytest.raises(RoutingError, match="no company found with id"):
        await ingestion_service.ingest_upload(
            content, "notes.txt", company_id=str(uuid4())
        )


# ═════════════════════════════════════════════════════════════════
# ingest_upload — Source creation and metadata
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_creates_source_with_metadata(
    ingestion_service: IngestionService,
    source_repo: SourceRepository,
) -> None:
    """ingest_upload populates who, interaction_date, src from parsed metadata."""
    name = f"Meta-{uuid4().hex[:8]}"
    content = f"nc: {name}\nwho: Jim\ndate: 2025-03-15\nsrc: meeting\np: Kate"
    source_id = await ingestion_service.ingest_upload(content, "meeting.txt")
    source = await source_repo.get_by_id(UUID(source_id))
    assert source is not None
    assert source.who == "Jim"
    assert source.interaction_date == "2025-03-15"
    assert source.src == "meeting"
    assert source.type == "upload"
    assert source.filename_or_subject == "meeting.txt"
    assert source.status == "pending"
    # file_path is set after Source creation (relative to data_dir)
    assert source.file_path is not None
    assert source.file_path.startswith("sources/")
    assert source.file_path.endswith("_meeting.txt")
    assert source_id in source.file_path


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_saves_file_to_disk(
    ingestion_service: IngestionService,
    test_settings: Settings,
) -> None:
    """ingest_upload saves the file to the data directory."""
    name = f"FileSave-{uuid4().hex[:8]}"
    content = f"nc: {name}\np: Leo"
    source_id = await ingestion_service.ingest_upload(content, "notes.txt")

    # Check file exists on disk
    source_dir = os.path.join(test_settings.data_dir, "sources")
    assert os.path.isdir(source_dir)
    # Find the company directory (we don't know the ID, but there should be at least one)
    company_dirs = os.listdir(source_dir)
    assert len(company_dirs) >= 1
    # Verify file with source_id prefix exists
    found = False
    for d in company_dirs:
        dir_path = os.path.join(source_dir, d)
        for f in os.listdir(dir_path):
            if f.startswith(source_id):
                found = True
                break
    assert found, f"Expected file with prefix {source_id} in sources dir"


# ═════════════════════════════════════════════════════════════════
# process_source
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_success(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """process_source on success: status → processed, save_facts called."""
    from app.schemas.inferred_fact import LLMInferredFact

    mock_inf = AsyncMock()
    mock_inf.extract_facts.return_value = [
        LLMInferredFact(category="person", value="Alice, CEO"),
        LLMInferredFact(category="technology", value="Python"),
    ]
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"Process-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="test.txt",
        raw_content="p: Alice, CEO\ntech: Python",
    )

    await svc.process_source(str(source.id))

    # Verify status is now processed
    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "processed"

    # Verify inference and review were called
    mock_inf.extract_facts.assert_called_once()
    mock_rev.save_facts.assert_called_once()


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_inference_validation_error(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """process_source on InferenceValidationError: status → failed with error."""
    mock_inf = AsyncMock()
    mock_inf.extract_facts.side_effect = InferenceValidationError(
        "LLM returned invalid JSON", raw_response='{"bad": true}'
    )
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"ValErr-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="bad.txt",
        raw_content="p: Nobody",
    )

    await svc.process_source(str(source.id))

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error == "LLM returned invalid JSON"
    assert updated.raw_llm_response == '{"bad": true}'


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_inference_api_error(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """process_source on InferenceApiError: status → failed with error."""
    mock_inf = AsyncMock()
    mock_inf.extract_facts.side_effect = InferenceApiError(
        "LLM API unavailable after 3 attempts: HTTP 429"
    )
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"ApiErr-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="api_err.txt",
        raw_content="p: Nobody",
    )

    await svc.process_source(str(source.id))

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "failed"
    assert "HTTP 429" in (updated.error or "")
    assert updated.raw_llm_response is None


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_not_found(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """process_source with a non-existent source ID raises SourceNotFoundError."""
    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )
    with pytest.raises(SourceNotFoundError):
        await svc.process_source(str(uuid4()))


# ═════════════════════════════════════════════════════════════════
# retry_source
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_source_resets_failed(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """retry_source resets a failed source to pending and enqueues it."""
    mock_inf = AsyncMock()
    mock_rev = AsyncMock()
    mock_q = AsyncMock()
    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=mock_q,
        settings=test_settings,
    )

    name = f"Retry-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="retry.txt",
        raw_content="data",
    )
    await source_repo.update_status(
        source.id, status="failed", error="some error"
    )

    await svc.retry_source(str(source.id))

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "pending"
    assert updated.error is None
    assert updated.raw_llm_response is None
    mock_q.enqueue.assert_called_once_with(str(source.id))


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_source_non_failed_raises(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """retry_source on a non-failed source raises SourceNotFailedError."""
    mock_inf = AsyncMock()
    mock_rev = AsyncMock()
    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"RetryFail-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="retry_fail.txt",
        raw_content="data",
    )
    # Source is still in "pending" status
    with pytest.raises(SourceNotFailedError):
        await svc.retry_source(str(source.id))


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_source_not_found(
    ingestion_service: IngestionService,
) -> None:
    """retry_source with a non-existent ID raises SourceNotFoundError."""
    with pytest.raises(SourceNotFoundError):
        await ingestion_service.retry_source(str(uuid4()))


# ═════════════════════════════════════════════════════════════════
# get_source / get_source_status / list_sources
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_get_source_found(
    ingestion_service: IngestionService,
    source_repo: SourceRepository,
    company_repo: CompanyRepository,
) -> None:
    """get_source returns the source when it exists."""
    name = f"GetSrc-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="get.txt",
        raw_content="data",
    )
    result = await ingestion_service.get_source(str(source.id))
    assert result.id == source.id


@pytest.mark.asyncio(loop_scope="session")
async def test_get_source_not_found(
    ingestion_service: IngestionService,
) -> None:
    """get_source with a non-existent ID raises SourceNotFoundError."""
    with pytest.raises(SourceNotFoundError):
        await ingestion_service.get_source(str(uuid4()))


@pytest.mark.asyncio(loop_scope="session")
async def test_get_source_status(
    ingestion_service: IngestionService,
    source_repo: SourceRepository,
    company_repo: CompanyRepository,
) -> None:
    """get_source_status returns the current status string."""
    name = f"Status-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="status.txt",
        raw_content="data",
    )
    status = await ingestion_service.get_source_status(str(source.id))
    assert status == "pending"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_source_status_not_found(
    ingestion_service: IngestionService,
) -> None:
    """get_source_status with a non-existent ID raises SourceNotFoundError."""
    with pytest.raises(SourceNotFoundError):
        await ingestion_service.get_source_status(str(uuid4()))


@pytest.mark.asyncio(loop_scope="session")
async def test_list_sources(
    ingestion_service: IngestionService,
    source_repo: SourceRepository,
    company_repo: CompanyRepository,
) -> None:
    """list_sources delegates to SourceRepository.list_by_company."""
    name = f"ListSrc-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
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
    items, total = await ingestion_service.list_sources(str(company.id))
    assert total == 2
    assert len(items) == 2


# ═════════════════════════════════════════════════════════════════
# _build_company_context
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_mode_none_returns_none(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """_build_company_context with llm_context_mode='none' returns None."""
    company = await company_repo.create(name=f"CtxNone-{uuid4().hex[:8]}")
    await db_session.refresh(company)
    await company_repo.update(company, llm_context_mode="none")

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_accepted_facts_with_data(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """_build_company_context with accepted_facts mode returns formatted string."""
    from datetime import datetime, timezone

    company = await company_repo.create(name=f"CtxFacts-{uuid4().hex[:8]}")
    await db_session.refresh(company)
    # Default mode is already "accepted_facts"
    assert company.llm_context_mode == "accepted_facts"

    source = await source_repo.create(
        company_id=company.id, type="upload",
        filename_or_subject="test.txt", raw_content="dummy",
    )
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)

    facts = await inferred_fact_repo.create_many([
        {"source_id": source.id, "company_id": company.id, "category": "person", "inferred_value": "Jane Doe, CTO"},
        {"source_id": source.id, "company_id": company.id, "category": "technology", "inferred_value": "Kubernetes"},
    ])
    await inferred_fact_repo.update_status(facts[0].id, status="accepted", reviewed_at=now)
    await inferred_fact_repo.update_status(facts[1].id, status="accepted", reviewed_at=now)

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is not None
    assert "Jane Doe, CTO" in result
    assert "Kubernetes" in result
    assert "Known people" in result
    assert "Known technologies" in result


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_accepted_facts_no_data_returns_none(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """_build_company_context with accepted_facts and no facts returns None."""
    company = await company_repo.create(name=f"CtxEmpty-{uuid4().hex[:8]}")
    await db_session.refresh(company)

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_full_mode_includes_facts_and_sources(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """_build_company_context with full mode returns facts and source content."""
    from datetime import datetime, timezone

    company = await company_repo.create(name=f"CtxFull-{uuid4().hex[:8]}")
    await db_session.refresh(company)
    await company_repo.update(company, llm_context_mode="full")

    # Create a processed source with content
    source = await source_repo.create(
        company_id=company.id, type="upload",
        filename_or_subject="meeting.txt", raw_content="Meeting notes about Terraform usage",
    )
    await source_repo.update_status(source.id, status="processed")

    # Create an accepted fact
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    facts = await inferred_fact_repo.create_many([
        {"source_id": source.id, "company_id": company.id, "category": "technology", "inferred_value": "Terraform"},
    ])
    await inferred_fact_repo.update_status(facts[0].id, status="accepted", reviewed_at=now)

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is not None
    assert "Terraform" in result
    assert "Meeting notes about Terraform usage" in result
    assert "meeting.txt" in result


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_respects_character_budget(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
) -> None:
    """_build_company_context stops adding facts when budget would be exceeded."""
    from datetime import datetime, timezone

    company = await company_repo.create(name=f"CtxBudget-{uuid4().hex[:8]}")
    await db_session.refresh(company)

    source = await source_repo.create(
        company_id=company.id, type="upload",
        filename_or_subject="test.txt", raw_content="dummy",
    )
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)

    # Create many facts
    fact_data = [
        {"source_id": source.id, "company_id": company.id, "category": "technology", "inferred_value": f"Tech-{i:03d}"}
        for i in range(50)
    ]
    facts = await inferred_fact_repo.create_many(fact_data)
    for f in facts:
        await inferred_fact_repo.update_status(f.id, status="accepted", reviewed_at=now)

    # Use a tiny budget
    tiny_settings = Settings(database_url="unused", data_dir="/tmp", llm_context_max_chars=100)
    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=tiny_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is not None
    # Budget is 100 chars — should not exceed
    assert len(result) <= 100
    # Should have some facts but not all 50
    assert "Tech-" in result


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_facts_ordered_newest_first(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """_build_company_context formats facts with newest first (from query order)."""
    from datetime import datetime, timezone

    company = await company_repo.create(name=f"CtxOrder-{uuid4().hex[:8]}")
    await db_session.refresh(company)

    source = await source_repo.create(
        company_id=company.id, type="upload",
        filename_or_subject="test.txt", raw_content="dummy",
    )

    t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2024, 6, 1, tzinfo=timezone.utc)

    facts = await inferred_fact_repo.create_many([
        {"source_id": source.id, "company_id": company.id, "category": "person", "inferred_value": "OlderPerson"},
        {"source_id": source.id, "company_id": company.id, "category": "person", "inferred_value": "NewerPerson"},
    ])
    facts[0].created_at = t1
    facts[1].created_at = t2
    await db_session.flush()

    await inferred_fact_repo.update_status(facts[0].id, status="accepted", reviewed_at=t1)
    await inferred_fact_repo.update_status(facts[1].id, status="accepted", reviewed_at=t2)

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is not None
    # NewerPerson should appear before OlderPerson (newest first in the values list)
    newer_idx = result.index("NewerPerson")
    older_idx = result.index("OlderPerson")
    assert newer_idx < older_idx


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_full_no_facts_no_sources_returns_none(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """_build_company_context in full mode with no facts and no sources returns None."""
    company = await company_repo.create(name=f"CtxFullEmpty-{uuid4().hex[:8]}")
    await db_session.refresh(company)
    await company_repo.update(company, llm_context_mode="full")

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_full_mode_source_budget_enforcement(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
) -> None:
    """Full mode: oversized source is skipped; budget never cut mid-source."""
    company = await company_repo.create(name=f"CtxSrcBudget-{uuid4().hex[:8]}")
    await db_session.refresh(company)
    await company_repo.update(company, llm_context_mode="full")

    # Create two processed sources: one small, one large
    small = await source_repo.create(
        company_id=company.id, type="upload",
        filename_or_subject="small.txt", raw_content="Small content",
    )
    await source_repo.update_status(small.id, status="processed")

    big_content = "X" * 500
    big = await source_repo.create(
        company_id=company.id, type="upload",
        filename_or_subject="big.txt", raw_content=big_content,
    )
    await source_repo.update_status(big.id, status="processed")

    # Budget allows small source but not big source
    tiny_settings = Settings(database_url="unused", data_dir="/tmp", llm_context_max_chars=200)
    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=tiny_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is not None
    assert "Small content" in result
    # Big source should be excluded — budget exceeded
    assert big_content not in result
    # Total output should fit within budget
    assert len(result) <= 200


@pytest.mark.asyncio(loop_scope="session")
async def test_build_context_full_mode_facts_but_no_sources(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """Full mode with accepted facts but no processed sources returns just facts."""
    from datetime import datetime, timezone

    company = await company_repo.create(name=f"CtxFullNoSrc-{uuid4().hex[:8]}")
    await db_session.refresh(company)
    await company_repo.update(company, llm_context_mode="full")

    # Create a source (not processed — still pending)
    source = await source_repo.create(
        company_id=company.id, type="upload",
        filename_or_subject="pending.txt", raw_content="Should not appear",
    )

    # Create an accepted fact
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    facts = await inferred_fact_repo.create_many([
        {"source_id": source.id, "company_id": company.id, "category": "technology", "inferred_value": "Docker"},
    ])
    await inferred_fact_repo.update_status(facts[0].id, status="accepted", reviewed_at=now)

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=AsyncMock(),
        review_service=AsyncMock(),
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    result = await svc._build_company_context(company.id)
    assert result is not None
    assert "Docker" in result
    assert "Known technologies" in result
    # No source content should appear (source is pending, not processed)
    assert "Should not appear" not in result
    assert "--- Source:" not in result


# ═════════════════════════════════════════════════════════════════
# Mode detection in process_source (Unit 4)
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_tagged_mode_calls_extract_facts_only(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """All lines have explicit tags → calls extract_facts(), not extract_facts_raw()."""
    from app.schemas.inferred_fact import LLMInferredFact

    mock_inf = AsyncMock()
    mock_inf.extract_facts.return_value = [
        LLMInferredFact(category="person", value="Alice, CEO"),
    ]
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"Tagged-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="tagged.txt",
        raw_content="p: Alice, CEO\nfn: Engineering\ntech: Python",
    )

    await svc.process_source(str(source.id))

    mock_inf.extract_facts.assert_called_once()
    mock_inf.extract_facts_raw.assert_not_called()
    mock_rev.save_facts.assert_called_once()

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "processed"


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_raw_mode_calls_extract_facts_raw_only(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """All lines are defaulted (no tags) → calls extract_facts_raw(), not extract_facts()."""
    from app.schemas.inferred_fact import LLMInferredFact

    mock_inf = AsyncMock()
    mock_inf.extract_facts_raw.return_value = [
        LLMInferredFact(category="person", value="Bob, CTO"),
    ]
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"Raw-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="raw.txt",
        # Lines with no recognized prefix → defaulted=True
        raw_content="Alice is the CEO and runs engineering\nThey use Python and Kubernetes",
    )

    await svc.process_source(str(source.id))

    mock_inf.extract_facts.assert_not_called()
    mock_inf.extract_facts_raw.assert_called_once()
    mock_rev.save_facts.assert_called_once()

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "processed"


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_hybrid_mode_calls_both(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """Mix of tagged and untagged → calls both extract_facts() and extract_facts_raw();
    combined facts passed to save_facts."""
    from app.schemas.inferred_fact import LLMInferredFact

    tagged_fact = LLMInferredFact(category="person", value="Alice, CEO")
    raw_fact = LLMInferredFact(category="technology", value="Kubernetes")

    mock_inf = AsyncMock()
    mock_inf.extract_facts.return_value = [tagged_fact]
    mock_inf.extract_facts_raw.return_value = [raw_fact]
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"Hybrid-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="hybrid.txt",
        # Mix: tagged (p:) + untagged (plain text)
        raw_content="p: Alice, CEO\nThey use Kubernetes for container orchestration",
    )

    await svc.process_source(str(source.id))

    mock_inf.extract_facts.assert_called_once()
    mock_inf.extract_facts_raw.assert_called_once()
    mock_rev.save_facts.assert_called_once()

    # Verify combined facts were passed
    call_args = mock_rev.save_facts.call_args
    facts_arg = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("facts")
    assert len(facts_arg) == 2
    assert tagged_fact in facts_arg
    assert raw_fact in facts_arg

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "processed"


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_no_content_lines_marks_processed(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """Source with only routing/metadata (no content lines) → marked processed, no LLM calls."""
    mock_inf = AsyncMock()
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"NoLines-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="metadata_only.txt",
        # Only routing + metadata — parse() puts these in fields, not lines
        raw_content=f"cid: {company.id}\nwho: Jim\ndate: 2025-01-01",
    )

    await svc.process_source(str(source.id))

    mock_inf.extract_facts.assert_not_called()
    mock_inf.extract_facts_raw.assert_not_called()
    mock_rev.save_facts.assert_not_called()

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "processed"


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_hybrid_tagged_pass_fails_source_failed(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """Hybrid mode: tagged pass fails → source marked failed (raw pass not attempted)."""
    mock_inf = AsyncMock()
    mock_inf.extract_facts.side_effect = InferenceValidationError(
        "Tagged extraction failed: LLM returned invalid JSON",
        raw_response='{"bad": true}',
    )
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"HybridTagFail-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="hybrid_tag_fail.txt",
        raw_content="p: Alice, CEO\nSome untagged text here",
    )

    await svc.process_source(str(source.id))

    # Tagged pass failed — raw pass should NOT have been attempted
    mock_inf.extract_facts.assert_called_once()
    mock_inf.extract_facts_raw.assert_not_called()
    mock_rev.save_facts.assert_not_called()

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "failed"
    assert "Tagged extraction failed" in (updated.error or "")


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_hybrid_raw_pass_fails_source_failed(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """Hybrid mode: tagged pass succeeds, raw pass fails → source marked failed,
    no facts persisted (fail-all per §9.5)."""
    from app.schemas.inferred_fact import LLMInferredFact

    mock_inf = AsyncMock()
    mock_inf.extract_facts.return_value = [
        LLMInferredFact(category="person", value="Alice, CEO"),
    ]
    mock_inf.extract_facts_raw.side_effect = InferenceApiError(
        "Raw extraction failed: LLM API unavailable"
    )
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"HybridRawFail-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="hybrid_raw_fail.txt",
        raw_content="p: Alice, CEO\nSome untagged text here",
    )

    await svc.process_source(str(source.id))

    # Both passes attempted, but raw failed
    mock_inf.extract_facts.assert_called_once()
    mock_inf.extract_facts_raw.assert_called_once()
    # No facts persisted — fail-all policy
    mock_rev.save_facts.assert_not_called()

    updated = await source_repo.get_by_id(source.id)
    assert updated is not None
    assert updated.status == "failed"
    assert "Raw extraction failed" in (updated.error or "")


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_raw_mode_context_passed_when_not_none(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """Raw mode: context is passed to extract_facts_raw() when llm_context_mode != 'none'."""
    from datetime import datetime, timezone

    from app.schemas.inferred_fact import LLMInferredFact

    # Create company with accepted_facts mode (default)
    name = f"RawCtx-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    await db_session.refresh(company)
    assert company.llm_context_mode == "accepted_facts"

    # Create a source with an accepted fact to build context from
    ctx_source = await source_repo.create(
        company_id=company.id, type="upload",
        filename_or_subject="ctx.txt", raw_content="dummy",
    )
    now = datetime(2024, 6, 1, tzinfo=timezone.utc)
    facts = await inferred_fact_repo.create_many([
        {"source_id": ctx_source.id, "company_id": company.id,
         "category": "technology", "inferred_value": "Kubernetes"},
    ])
    await inferred_fact_repo.update_status(facts[0].id, status="accepted", reviewed_at=now)

    mock_inf = AsyncMock()
    mock_inf.extract_facts_raw.return_value = [
        LLMInferredFact(category="person", value="Dave, SRE"),
    ]
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    # Create a raw-mode source (no tags)
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="raw_ctx.txt",
        raw_content="Dave is the SRE lead and handles incident response",
    )

    await svc.process_source(str(source.id))

    # Verify context was passed (not None)
    mock_inf.extract_facts_raw.assert_called_once()
    call_args = mock_inf.extract_facts_raw.call_args
    context_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("company_context")
    assert context_arg is not None
    assert "Kubernetes" in context_arg


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_raw_mode_context_none_when_mode_none(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """Raw mode: context is None when llm_context_mode == 'none'."""
    from app.schemas.inferred_fact import LLMInferredFact

    name = f"RawNoCtx-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    await db_session.refresh(company)
    await company_repo.update(company, llm_context_mode="none")

    mock_inf = AsyncMock()
    mock_inf.extract_facts_raw.return_value = [
        LLMInferredFact(category="person", value="Eve, PM"),
    ]
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="raw_no_ctx.txt",
        raw_content="Eve is the PM and she manages the roadmap",
    )

    await svc.process_source(str(source.id))

    mock_inf.extract_facts_raw.assert_called_once()
    call_args = mock_inf.extract_facts_raw.call_args
    context_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("company_context")
    assert context_arg is None


@pytest.mark.asyncio(loop_scope="session")
async def test_process_source_raw_mode_raw_text_content(
    db_session: AsyncSession,
    source_repo: SourceRepository,
    inferred_fact_repo: InferredFactRepository,
    company_repo: CompanyRepository,
    test_settings: Settings,
) -> None:
    """Raw mode: verify the exact raw_text passed to extract_facts_raw() —
    should be the joined text of defaulted lines, preserving original content."""
    from app.schemas.inferred_fact import LLMInferredFact

    mock_inf = AsyncMock()
    mock_inf.extract_facts_raw.return_value = [
        LLMInferredFact(category="other", value="something"),
    ]
    mock_rev = AsyncMock()

    svc = IngestionService(
        source_repo=source_repo,
        inferred_fact_repo=inferred_fact_repo,
        company_repo=company_repo,
        inference_service=mock_inf,
        review_service=mock_rev,
        ingestion_queue=AsyncMock(),
        settings=test_settings,
    )

    name = f"RawText-{uuid4().hex[:8]}"
    company = await company_repo.create(name)
    # Source with routing + untagged content lines
    source = await source_repo.create(
        company_id=company.id,
        type="upload",
        filename_or_subject="raw_text.txt",
        raw_content=f"cid: {company.id}\nAlice is the CEO\nBob runs engineering",
    )

    await svc.process_source(str(source.id))

    mock_inf.extract_facts_raw.assert_called_once()
    call_args = mock_inf.extract_facts_raw.call_args
    raw_text_arg = call_args[0][0] if len(call_args[0]) > 0 else call_args[1].get("raw_text")
    # Should be the joined text of the two defaulted lines (routing excluded by parse)
    assert raw_text_arg == "Alice is the CEO\nBob runs engineering"
