"""API tests for fact editing endpoint (UC 17).

PUT /companies/{id}/facts/{fact_id} — edit corrected_value on accepted/corrected fact
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
    name = name or f"FactTestCo-{uuid4().hex[:8]}"
    response = await client.post("/api/v1/companies", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["company_id"])


async def _seed_facts(
    db: AsyncSession, company_id: str, facts: list[dict]
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
# PUT /companies/{id}/facts/{fact_id}
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_update_fact_value_accepted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT on accepted fact sets corrected_value, status stays 'accepted'."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "OriginalTech"},
    ])

    # Accept first
    accept_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/accept"
    )
    assert accept_resp.status_code == 200

    # Now update the value
    response = await client.put(
        f"/api/v1/companies/{company_id}/facts/{fact_ids[0]}",
        json={"corrected_value": "UpdatedTech"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fact_id"] == str(fact_ids[0])
    assert data["status"] == "accepted"
    assert data["corrected_value"] == "UpdatedTech"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_fact_value_corrected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT on corrected fact overwrites corrected_value, status stays 'corrected'."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "WrongTech"},
    ])

    # Correct first
    correct_resp = await client.post(
        f"/api/v1/companies/{company_id}/pending/{fact_ids[0]}/correct",
        json={"corrected_value": "FirstCorrection"},
    )
    assert correct_resp.status_code == 200

    # Now update the corrected value
    response = await client.put(
        f"/api/v1/companies/{company_id}/facts/{fact_ids[0]}",
        json={"corrected_value": "SecondCorrection"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fact_id"] == str(fact_ids[0])
    assert data["status"] == "corrected"
    assert data["corrected_value"] == "SecondCorrection"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_fact_value_pending_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT on pending fact returns 409 fact_not_editable."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    fact_ids = await _seed_facts(db_session, company_id, [
        {"category": "technology", "value": "PendingTech"},
    ])

    response = await client.put(
        f"/api/v1/companies/{company_id}/facts/{fact_ids[0]}",
        json={"corrected_value": "Nope"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "fact_not_editable"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_fact_value_unauthenticated(client: AsyncClient) -> None:
    """PUT /companies/{id}/facts/{fact_id} without session returns 401."""
    client.cookies.clear()
    try:
        response = await client.put(
            f"/api/v1/companies/{uuid4()}/facts/{uuid4()}",
            json={"corrected_value": "Something"},
        )
        assert response.status_code == 401
    finally:
        await _ensure_authenticated(client)
