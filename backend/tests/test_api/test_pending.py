"""API tests for pending review endpoints.

GET  /companies/{id}/pending
POST /companies/{id}/pending/{fact_id}/accept
POST /companies/{id}/pending/{fact_id}/dismiss
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import InferredFact, Source

USERNAME = "investigator"
PASSWORD = "testpassword123"


async def _ensure_authenticated(client: AsyncClient) -> None:
    """Helper: set password (idempotent) + login so session cookie is set."""
    await client.post(
        "/api/v1/auth/password/set",
        json={"username": USERNAME, "password": PASSWORD},
    )
    await client.post(
        "/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )


async def _create_company(client: AsyncClient, name: str | None = None) -> str:
    """Helper: create a company and return its ID."""
    name = name or f"PendTestCo-{uuid4().hex[:8]}"
    response = await client.post("/api/v1/companies", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["company_id"])


async def _seed_facts(
    db: AsyncSession,
    company_id: str,
    facts: list[dict],
) -> list[UUID]:
    """Helper: insert a source and inferred facts directly, return fact IDs."""
    source = Source(
        company_id=UUID(company_id),
        type="upload",
        filename_or_subject="seed.txt",
        raw_content="seeded test data",
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)

    fact_ids = []
    for f in facts:
        fact = InferredFact(
            source_id=source.id,
            company_id=UUID(company_id),
            category=f["category"],
            inferred_value=f["value"],
        )
        db.add(fact)
        await db.flush()
        await db.refresh(fact)
        fact_ids.append(fact.id)

    return fact_ids


# ═════════════════════════════════════════════════════════════════
# GET /companies/{id}/pending
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /companies/{id}/pending returns pending facts."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "person", "value": "Alice, CTO"},
        {"category": "technology", "value": "Kubernetes"},
    ])

    response = await client.get(f"/api/v1/companies/{company_id}/pending")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    for item in data["items"]:
        assert item["status"] == "pending"
        assert "fact_id" in item
        assert "category" in item
        assert "inferred_value" in item
        assert "source_excerpt" in item
        assert "candidates" in item


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_category_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /companies/{id}/pending?category=person filters by category."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    await _seed_facts(db_session, company_id, [
        {"category": "person", "value": "Bob, VP"},
        {"category": "technology", "value": "Docker"},
        {"category": "process", "value": "Scrum"},
    ])

    response = await client.get(
        f"/api/v1/companies/{company_id}/pending?category=person"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["category"] == "person"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_status_accepted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /companies/{id}/pending?status=accepted returns accepted facts only."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "React"},
        {"category": "technology", "value": "Vue"},
    ])

    # Accept the first fact
    accept_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert accept_resp.status_code == 200

    # Query accepted
    response = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=accepted"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["inferred_value"] == "React"
    assert data["items"][0]["status"] == "accepted"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_status_and_category_combined(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET ...?status=accepted&category=person returns accepted person facts."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "person", "value": "Carol, Director"},
        {"category": "technology", "value": "GraphQL"},
    ])

    # Accept both
    await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[1]}/accept"
    )

    # Query accepted persons only
    response = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=accepted&category=person"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["category"] == "person"
    assert data["items"][0]["inferred_value"] == "Carol, Director"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_pagination(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /companies/{id}/pending respects limit and offset."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": f"Tech{i}"}
        for i in range(5)
    ])

    resp1 = await client.get(
        f"/api/v1/companies/{company_id}/pending?limit=2&offset=0"
    )
    assert resp1.status_code == 200
    d1 = resp1.json()
    assert d1["total"] == 5
    assert len(d1["items"]) == 2

    resp2 = await client.get(
        f"/api/v1/companies/{company_id}/pending?limit=2&offset=2"
    )
    d2 = resp2.json()
    assert len(d2["items"]) == 2
    # No overlap
    ids1 = {i["fact_id"] for i in d1["items"]}
    ids2 = {i["fact_id"] for i in d2["items"]}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_invalid_status_returns_422(
    client: AsyncClient,
) -> None:
    """GET /companies/{id}/pending?status=garbage returns 422."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=garbage"
    )
    assert response.status_code == 422


# ═════════════════════════════════════════════════════════════════
# POST .../accept
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_person_fact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../accept on a person fact returns 200 with entity_id and moves to accepted."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "person", "value": "Jane Smith, VP Engineering"},
    ])

    response = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fact_id"] == str(fact_ids[0])
    assert data["status"] == "accepted"
    assert data["entity_id"] is not None
    UUID(data["entity_id"])

    # Confirm fact moved from pending to accepted via round-trip GET
    pending = await client.get(f"/api/v1/companies/{company_id}/pending")
    assert pending.json()["total"] == 0

    accepted = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=accepted&category=person"
    )
    assert accepted.status_code == 200
    items = accepted.json()["items"]
    assert len(items) == 1
    assert items[0]["fact_id"] == str(fact_ids[0])
    assert items[0]["inferred_value"] == "Jane Smith, VP Engineering"


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_action_item_fact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../accept on an action-item fact returns 200 with entity_id and moves to accepted."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "action-item", "value": "Set up monitoring"},
    ])

    response = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fact_id"] == str(fact_ids[0])
    assert data["status"] == "accepted"
    assert data["entity_id"] is not None
    UUID(data["entity_id"])

    # Confirm fact moved from pending to accepted via round-trip GET
    pending = await client.get(f"/api/v1/companies/{company_id}/pending")
    assert pending.json()["total"] == 0

    accepted = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=accepted&category=action-item"
    )
    items = accepted.json()["items"]
    assert len(items) == 1
    assert items[0]["inferred_value"] == "Set up monitoring"


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_functional_area_fact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../accept on a functional-area fact returns 200 with entity_id."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    area_name = f"Platform-{uuid4().hex[:6]}"
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "functional-area", "value": area_name},
    ])

    response = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fact_id"] == str(fact_ids[0])
    assert data["status"] == "accepted"
    assert data["entity_id"] is not None
    UUID(data["entity_id"])

    # Round-trip: fact moved to accepted
    accepted = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=accepted&category=functional-area"
    )
    items = accepted.json()["items"]
    assert len(items) == 1
    assert items[0]["inferred_value"] == area_name


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_relationship_fact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../accept on a relationship fact returns 200 with entity_id."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    sub_name = f"SubApi-{uuid4().hex[:6]}"
    mgr_name = f"MgrApi-{uuid4().hex[:6]}"
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "relationship", "value": f"{sub_name} > {mgr_name}"},
    ])

    response = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fact_id"] == str(fact_ids[0])
    assert data["status"] == "accepted"
    assert data["entity_id"] is not None
    UUID(data["entity_id"])

    # Round-trip: fact moved to accepted
    accepted = await client.get(
        f"/api/v1/companies/{company_id}/pending?status=accepted&category=relationship"
    )
    items = accepted.json()["items"]
    assert len(items) == 1
    assert items[0]["inferred_value"] == f"{sub_name} > {mgr_name}"


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_technology_fact_no_entity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../accept on a technology fact returns 200 with entity_id=null."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "Rust"},
    ])

    response = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["entity_id"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_non_pending_fact_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../accept on an already-accepted fact returns 409."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "Go"},
    ])

    # Accept once
    resp1 = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert resp1.status_code == 200

    # Accept again → 409
    resp2 = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "fact_not_pending"


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_wrong_company_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../accept with wrong company_id returns 404."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    other_company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "Elixir"},
    ])

    response = await client.post(
        f"/api/v1/companies/{other_company_id}/pending/{fact_ids[0]}/accept"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "fact_company_mismatch"


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_nonexistent_fact_returns_404(
    client: AsyncClient,
) -> None:
    """POST .../accept with a nonexistent fact_id returns 404."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.post(
        f"/api/v1/companies/{company_id}/pending/{uuid4()}/accept"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "fact_not_found"


# ═════════════════════════════════════════════════════════════════
# POST .../dismiss
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_fact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../dismiss returns 200 and marks the fact dismissed."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "COBOL"},
    ])

    response = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/dismiss"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fact_id"] == str(fact_ids[0])
    assert data["status"] == "dismissed"

    # Verify it no longer appears in pending list
    pending = await client.get(f"/api/v1/companies/{company_id}/pending")
    assert pending.json()["total"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_non_pending_fact_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../dismiss on an already-dismissed fact returns 409."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "Fortran"},
    ])

    # Dismiss once
    resp1 = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/dismiss"
    )
    assert resp1.status_code == 200

    # Dismiss again → 409
    resp2 = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/dismiss"
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "fact_not_pending"


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_wrong_company_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST .../dismiss with wrong company_id returns 404."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    other_company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "Haskell"},
    ])

    response = await client.post(
        f"/api/v1/companies/{other_company_id}/pending/{fact_ids[0]}/dismiss"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "fact_company_mismatch"


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_nonexistent_fact_returns_404(
    client: AsyncClient,
) -> None:
    """POST .../dismiss with nonexistent fact_id returns 404."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.post(
        f"/api/v1/companies/{company_id}/pending/{uuid4()}/dismiss"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "fact_not_found"


# ═════════════════════════════════════════════════════════════════
# Unauthenticated access
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_list_pending_unauthenticated(client: AsyncClient) -> None:
    """GET /companies/{id}/pending without session returns 401."""
    client.cookies.clear()
    try:
        response = await client.get(f"/api/v1/companies/{uuid4()}/pending")
        assert response.status_code == 401
    finally:
        await _ensure_authenticated(client)


@pytest.mark.asyncio(loop_scope="session")
async def test_accept_unauthenticated(client: AsyncClient) -> None:
    """POST .../accept without session returns 401."""
    client.cookies.clear()
    try:
        response = await client.post(
            f"/api/v1/companies/{uuid4()}/pending/{uuid4()}/accept"
        )
        assert response.status_code == 401
    finally:
        await _ensure_authenticated(client)


@pytest.mark.asyncio(loop_scope="session")
async def test_dismiss_unauthenticated(client: AsyncClient) -> None:
    """POST .../dismiss without session returns 401."""
    client.cookies.clear()
    try:
        response = await client.post(
            f"/api/v1/companies/{uuid4()}/pending/{uuid4()}/dismiss"
        )
        assert response.status_code == 401
    finally:
        await _ensure_authenticated(client)
