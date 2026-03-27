"""End-to-end integration test for the Phase 2 ingestion pipeline.

Upload → process (with mocked LLM) → verify facts → accept/dismiss → verify entities.

The background worker is not used — process_source is called directly with a
mock InferenceService that returns canned LLMInferredFact objects. This verifies
the full pipeline wiring: prefix parsing → LLM extraction → fact persistence →
accept/dismiss → entity creation.
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.config import Settings
from app.repositories.company_repository import CompanyRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.inferred_fact import LLMInferredFact
from app.services.ingestion_service import IngestionService
from app.services.review_service import ReviewService
from app.repositories.person_repository import PersonRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.relationship_repository import RelationshipRepository

USERNAME = "investigator"
PASSWORD = "testpassword123"

# Canned LLM response — one fact per category that creates an entity,
# plus a technology fact (no entity) and a dismiss candidate.
CANNED_FACTS = [
    LLMInferredFact(category="person", value="Alice Smith, CTO"),
    LLMInferredFact(category="functional-area", value="Engineering"),
    LLMInferredFact(category="action-item", value="Review quarterly plan"),
    LLMInferredFact(
        category="relationship",
        value="reports-to",
        subordinate="Bob Jones",
        manager="Alice Smith",
    ),
    LLMInferredFact(category="technology", value="Kubernetes"),
    LLMInferredFact(category="process", value="Agile sprints"),
    LLMInferredFact(category="cgkra-kp", value="Talent retention"),
]

# The source file content with prefix tags.
SOURCE_CONTENT = """\
p: Alice Smith, CTO
fn: Engineering
a: Review quarterly plan
rel: Bob Jones > Alice Smith
t: Kubernetes
proc: Agile sprints
kp: Talent retention
"""


async def _ensure_authenticated(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/password/set",
        json={"username": USERNAME, "password": PASSWORD},
    )
    await client.post(
        "/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )


async def _create_company(client: AsyncClient) -> str:
    name = f"E2ECo-{uuid4().hex[:8]}"
    resp = await client.post("/api/v1/companies", json={"name": name})
    assert resp.status_code == 201
    return str(resp.json()["company_id"])


def _build_ingestion_service(
    db: AsyncSession,
    mock_inference: AsyncMock,
) -> IngestionService:
    """Build an IngestionService with a mocked InferenceService."""
    review_service = ReviewService(
        inferred_fact_repo=InferredFactRepository(db),
        source_repo=SourceRepository(db),
        person_repo=PersonRepository(db),
        functional_area_repo=FunctionalAreaRepository(db),
        action_item_repo=ActionItemRepository(db),
        relationship_repo=RelationshipRepository(db),
    )
    mock_queue = AsyncMock()
    return IngestionService(
        source_repo=SourceRepository(db),
        inferred_fact_repo=InferredFactRepository(db),
        company_repo=CompanyRepository(db),
        inference_service=mock_inference,
        review_service=review_service,
        ingestion_queue=mock_queue,
        settings=Settings(
            database_url="unused",
            data_dir="/tmp/blackbook_test_e2e",
        ),
    )


# ═════════════════════════════════════════════════════════════════
# Full pipeline e2e test
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_full_ingestion_pipeline(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Upload → process → verify facts → accept each category → dismiss one → verify entities."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    # ── Step 1: Upload via HTTP API ──────────────────────────────

    upload_resp = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("notes.txt", SOURCE_CONTENT.encode(), "text/plain")},
        data={"company_id": company_id},
    )
    assert upload_resp.status_code == 200
    source_id = upload_resp.json()["source_id"]
    assert upload_resp.json()["status"] == "pending"

    # Verify source status via API.
    status_resp = await client.get(f"/api/v1/sources/{source_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "pending"

    # ── Step 2: Process source (simulating worker) ───────────────

    mock_inference = AsyncMock()
    mock_inference.extract_facts = AsyncMock(return_value=CANNED_FACTS)

    svc = _build_ingestion_service(db_session, mock_inference)
    await svc.process_source(source_id)

    # Verify source transitioned to processed.
    status_resp = await client.get(f"/api/v1/sources/{source_id}/status")
    assert status_resp.json()["status"] == "processed"

    # Verify InferenceService was called with parsed lines.
    mock_inference.extract_facts.assert_called_once()
    lines = mock_inference.extract_facts.call_args[0][0]
    assert len(lines) == 7  # 7 content lines in SOURCE_CONTENT

    # ── Step 3: Verify pending facts via API ─────────────────────

    pending_resp = await client.get(
        f"/api/v1/companies/{company_id}/pending?limit=50"
    )
    assert pending_resp.status_code == 200
    pending_data = pending_resp.json()
    assert pending_data["total"] == 7  # all 7 canned facts

    facts = pending_data["items"]
    fact_by_cat: dict[str, dict] = {}
    for f in facts:
        # Some categories may have multiple facts; take the first of each.
        if f["category"] not in fact_by_cat:
            fact_by_cat[f["category"]] = f

    assert set(fact_by_cat.keys()) == {
        "person",
        "functional-area",
        "action-item",
        "relationship",
        "technology",
        "process",
        "cgkra-kp",
    }

    # ── Step 4: Verify initial pending_count on company ──────────

    company_resp = await client.get(f"/api/v1/companies/{company_id}")
    assert company_resp.json()["pending_count"] == 7

    # ── Step 5: Accept person → verify entity_id returned ────────

    person_fact = fact_by_cat["person"]
    accept_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{person_fact['fact_id']}/accept"
    )
    assert accept_resp.status_code == 200
    accept_data = accept_resp.json()
    assert accept_data["status"] == "accepted"
    person_entity_id = accept_data["entity_id"]
    assert person_entity_id is not None

    # Verify person was created in the database.
    person_repo = PersonRepository(db_session)
    person = await person_repo.get_by_id(UUID(person_entity_id))
    assert person is not None
    assert "Alice Smith" in person.name

    # ── Step 6: Accept functional-area → verify entity ───────────

    fa_fact = fact_by_cat["functional-area"]
    accept_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fa_fact['fact_id']}/accept"
    )
    assert accept_resp.status_code == 200
    fa_entity_id = accept_resp.json()["entity_id"]
    assert fa_entity_id is not None

    fa_repo = FunctionalAreaRepository(db_session)
    fa = await fa_repo.get_by_id(UUID(fa_entity_id))
    assert fa is not None
    assert fa.name == "Engineering"

    # ── Step 7: Accept action-item → verify entity ───────────────

    ai_fact = fact_by_cat["action-item"]
    accept_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{ai_fact['fact_id']}/accept"
    )
    assert accept_resp.status_code == 200
    ai_entity_id = accept_resp.json()["entity_id"]
    assert ai_entity_id is not None

    ai_repo = ActionItemRepository(db_session)
    action_item = await ai_repo.get_by_id(UUID(ai_entity_id))
    assert action_item is not None
    assert action_item.description == "Review quarterly plan"

    # ── Step 8: Accept relationship → verify relationship + reports_to ─

    rel_fact = fact_by_cat["relationship"]
    accept_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{rel_fact['fact_id']}/accept"
    )
    assert accept_resp.status_code == 200
    rel_entity_id = accept_resp.json()["entity_id"]
    assert rel_entity_id is not None  # relationship row was created

    # Verify Bob Jones was created as a stub person and reports_to was set.
    bob_matches = await person_repo.get_by_name_iexact(
        UUID(company_id), "Bob Jones"
    )
    assert len(bob_matches) >= 1
    bob = bob_matches[0]
    assert bob.reports_to_person_id is not None  # linked to Alice

    # ── Step 9: Accept technology → no entity (null entity_id) ───

    tech_fact = fact_by_cat["technology"]
    accept_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{tech_fact['fact_id']}/accept"
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["entity_id"] is None

    # Verify it appears in accepted list.
    accepted_resp = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=accepted&category=technology"
    )
    assert accepted_resp.status_code == 200
    accepted_tech = accepted_resp.json()["items"]
    assert any(t["inferred_value"] == "Kubernetes" for t in accepted_tech)

    # ── Step 10: Dismiss a fact → verify status ──────────────────

    # Dismiss the process fact.
    proc_fact = fact_by_cat["process"]
    dismiss_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{proc_fact['fact_id']}/dismiss"
    )
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["status"] == "dismissed"

    # Verify it no longer appears in pending.
    pending_resp = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=pending"
    )
    pending_ids = [f["fact_id"] for f in pending_resp.json()["items"]]
    assert proc_fact["fact_id"] not in pending_ids

    # ── Step 11: Verify pending_count decremented ────────────────

    # We accepted 5 facts and dismissed 1 = 6 reviewed. 1 remains (cgkra-kp).
    company_resp = await client.get(f"/api/v1/companies/{company_id}")
    assert company_resp.json()["pending_count"] == 1

    # ── Step 12: Accept the last pending fact (cgkra-kp) ─────────

    kp_fact = fact_by_cat["cgkra-kp"]
    accept_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{kp_fact['fact_id']}/accept"
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["entity_id"] is None  # no entity for cgkra

    # Verify pending_count is now 0.
    company_resp = await client.get(f"/api/v1/companies/{company_id}")
    assert company_resp.json()["pending_count"] == 0


# ═════════════════════════════════════════════════════════════════
# Source list reflects processed status
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_source_list_shows_processed_status(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """After processing, the source list shows 'processed' status."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    upload_resp = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("list_test.txt", b"p: Zara, VP", "text/plain")},
        data={"company_id": company_id},
    )
    source_id = upload_resp.json()["source_id"]

    # Process with a single canned fact.
    mock_inference = AsyncMock()
    mock_inference.extract_facts = AsyncMock(
        return_value=[LLMInferredFact(category="person", value="Zara, VP")]
    )
    svc = _build_ingestion_service(db_session, mock_inference)
    await svc.process_source(source_id)

    # Verify via source list.
    list_resp = await client.get(f"/api/v1/companies/{company_id}/sources")
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "processed"


# ═════════════════════════════════════════════════════════════════
# Failed source shows error and can be retried
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_failed_source_retry_flow(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Upload → fail → verify error → retry → re-process → success."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    upload_resp = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("fail_test.txt", b"p: Quinn", "text/plain")},
        data={"company_id": company_id},
    )
    source_id = upload_resp.json()["source_id"]

    # First processing: simulate LLM API failure.
    from app.exceptions import InferenceApiError

    mock_inference_fail = AsyncMock()
    mock_inference_fail.extract_facts = AsyncMock(
        side_effect=InferenceApiError("LLM unavailable after 3 attempts")
    )
    svc_fail = _build_ingestion_service(db_session, mock_inference_fail)
    await svc_fail.process_source(source_id)

    # Source should be failed.
    status_resp = await client.get(f"/api/v1/sources/{source_id}/status")
    assert status_resp.json()["status"] == "failed"

    # Source detail shows error.
    detail_resp = await client.get(f"/api/v1/sources/{source_id}")
    assert "LLM unavailable" in detail_resp.json()["error"]

    # Retry via API.
    retry_resp = await client.post(f"/api/v1/sources/{source_id}/retry")
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "pending"

    # Now re-process with success.
    mock_inference_ok = AsyncMock()
    mock_inference_ok.extract_facts = AsyncMock(
        return_value=[LLMInferredFact(category="person", value="Quinn")]
    )
    svc_ok = _build_ingestion_service(db_session, mock_inference_ok)
    await svc_ok.process_source(source_id)

    # Should be processed now.
    status_resp = await client.get(f"/api/v1/sources/{source_id}/status")
    assert status_resp.json()["status"] == "processed"

    # Facts should exist.
    pending_resp = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=pending"
    )
    assert pending_resp.json()["total"] >= 1
    assert any(
        f["inferred_value"] == "Quinn" for f in pending_resp.json()["items"]
    )
