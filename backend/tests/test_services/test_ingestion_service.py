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
