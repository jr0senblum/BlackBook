"""API tests for /companies/{id}/people/* endpoints (§10.5).

Tests cover:
  GET  /companies/{id}/people
  POST /companies/{id}/people
  GET  /companies/{id}/people/{person_id}
  PUT  /companies/{id}/people/{person_id}
  DELETE /companies/{id}/people/{person_id}
"""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import ActionItem, FunctionalArea, InferredFact, Person, Source

USERNAME = "investigator"
PASSWORD = "testpassword123"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _ensure_authenticated(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/password/set",
        json={"username": USERNAME, "password": PASSWORD},
    )
    await client.post(
        "/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )


async def _create_company(client: AsyncClient, name: str | None = None) -> str:
    name = name or f"PeopleCo-{uuid4().hex[:8]}"
    response = await client.post("/api/v1/companies", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["company_id"])


async def _seed_person(
    db: AsyncSession,
    company_id: str,
    name: str,
    title: str | None = None,
    primary_area_id: UUID | None = None,
    reports_to_person_id: UUID | None = None,
) -> UUID:
    person = Person(
        company_id=UUID(company_id),
        name=name,
        title=title,
        primary_area_id=primary_area_id,
        reports_to_person_id=reports_to_person_id,
    )
    db.add(person)
    await db.flush()
    await db.refresh(person)
    return person.id


async def _seed_area(db: AsyncSession, company_id: str, name: str) -> UUID:
    area = FunctionalArea(company_id=UUID(company_id), name=name)
    db.add(area)
    await db.flush()
    await db.refresh(area)
    return area.id


async def _seed_accepted_fact(
    db: AsyncSession,
    company_id: str,
    category: str,
    inferred_value: str,
    functional_area_id: UUID | None = None,
    corrected_value: str | None = None,
) -> UUID:
    source = Source(
        company_id=UUID(company_id),
        type="upload",
        filename_or_subject="seed.txt",
        raw_content="test",
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)

    fact = InferredFact(
        source_id=source.id,
        company_id=UUID(company_id),
        category=category,
        inferred_value=inferred_value,
        status="accepted",
        functional_area_id=functional_area_id,
        corrected_value=corrected_value,
    )
    db.add(fact)
    await db.flush()
    await db.refresh(fact)
    return fact.id


async def _seed_action_item(
    db: AsyncSession,
    company_id: str,
    person_id: UUID,
    description: str,
) -> UUID:
    item = ActionItem(
        company_id=UUID(company_id),
        person_id=person_id,
        description=description,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item.id


# ---------------------------------------------------------------------------
# GET /companies/{id}/people
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_list_people(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Returns all people for a company."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    await _seed_person(db_session, company_id, "Alice")
    await _seed_person(db_session, company_id, "Bob")

    response = await client.get(f"/api/v1/companies/{company_id}/people")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    names = [p["name"] for p in data["items"]]
    assert "Alice" in names
    assert "Bob" in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_people_empty(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Returns empty list when no people exist."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.get(f"/api/v1/companies/{company_id}/people")
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_list_people_includes_area_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PersonListItem includes primary_area_name when area is set."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    area_id = await _seed_area(db_session, company_id, "Engineering")
    await _seed_person(db_session, company_id, "Carol", primary_area_id=area_id)

    response = await client.get(f"/api/v1/companies/{company_id}/people")
    assert response.status_code == 200
    carol = next(p for p in response.json()["items"] if p["name"] == "Carol")
    assert carol["primary_area_name"] == "Engineering"


# ---------------------------------------------------------------------------
# POST /companies/{id}/people
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST with name+title returns 201 and person data."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.post(
        f"/api/v1/companies/{company_id}/people",
        json={"name": "Dana", "title": "CTO"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Dana"
    UUID(data["person_id"])  # must be valid UUID


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person_minimal(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST with name only returns 201."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.post(
        f"/api/v1/companies/{company_id}/people",
        json={"name": "Eve"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Eve"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person_with_area_and_reports_to(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST with primary_area_id and reports_to_person_id persists FKs;
    GET detail returns area_name and reports_to_name."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    area_id = await _seed_area(db_session, company_id, "Product")
    mgr_id = await _seed_person(db_session, company_id, "Frank")

    response = await client.post(
        f"/api/v1/companies/{company_id}/people",
        json={
            "name": "Grace",
            "primary_area_id": str(area_id),
            "reports_to_person_id": str(mgr_id),
        },
    )
    assert response.status_code == 201
    person_id = response.json()["person_id"]

    # Verify FK fields appear in detail
    detail = await client.get(
        f"/api/v1/companies/{company_id}/people/{person_id}"
    )
    assert detail.status_code == 200
    d = detail.json()
    assert d["primary_area_id"] == str(area_id)
    assert d["primary_area_name"] == "Product"
    assert d["reports_to_person_id"] == str(mgr_id)
    assert d["reports_to_name"] == "Frank"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person_empty_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST with whitespace-only name returns 422."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.post(
        f"/api/v1/companies/{company_id}/people",
        json={"name": "   "},
    )
    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person_invalid_area_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST with a non-existent primary_area_id returns 422."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.post(
        f"/api/v1/companies/{company_id}/people",
        json={"name": "Henry", "primary_area_id": str(uuid4())},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /companies/{id}/people/{person_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_get_person_detail(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET returns enriched detail with area name, action items, linked facts."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    area_id = await _seed_area(db_session, company_id, "Sales")
    person_id = await _seed_person(
        db_session, company_id, "Iris", title="VP Sales",
        primary_area_id=area_id,
    )
    await _seed_action_item(db_session, company_id, person_id, "Follow up with client")
    await _seed_accepted_fact(
        db_session, company_id, "person", "Iris, VP Sales"
    )

    response = await client.get(
        f"/api/v1/companies/{company_id}/people/{person_id}"
    )
    assert response.status_code == 200
    d = response.json()
    assert d["name"] == "Iris"
    assert d["title"] == "VP Sales"
    assert d["primary_area_name"] == "Sales"
    assert len(d["action_items"]) == 1
    assert d["action_items"][0]["description"] == "Follow up with client"
    assert "created_at" in d["action_items"][0]
    # Name-matched person fact should appear
    assert any(f["category"] == "person" for f in d["inferred_facts"])


@pytest.mark.asyncio(loop_scope="session")
async def test_get_person_detail_linked_facts_by_area(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Person assigned to area: accepted facts tagged to that area appear in linked facts."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    area_id = await _seed_area(db_session, company_id, "Engineering")
    person_id = await _seed_person(
        db_session, company_id, "Jack", primary_area_id=area_id
    )
    # Seed a technology fact tagged to the area
    await _seed_accepted_fact(
        db_session, company_id, "technology", "Python",
        functional_area_id=area_id,
    )

    response = await client.get(
        f"/api/v1/companies/{company_id}/people/{person_id}"
    )
    assert response.status_code == 200
    facts = response.json()["inferred_facts"]
    assert any(f["category"] == "technology" and f["value"] == "Python" for f in facts)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_person_detail_linked_fact_effective_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """LinkedFactSummary.value uses corrected_value when set, else inferred_value."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    person_id = await _seed_person(db_session, company_id, "Kate")
    # Seed a corrected person fact whose inferred_value contains the name
    await _seed_accepted_fact(
        db_session, company_id, "person", "Kate, Manager",
        corrected_value="Kate, Senior Manager",
    )

    response = await client.get(
        f"/api/v1/companies/{company_id}/people/{person_id}"
    )
    assert response.status_code == 200
    facts = response.json()["inferred_facts"]
    kate_fact = next((f for f in facts if f["category"] == "person"), None)
    assert kate_fact is not None
    assert kate_fact["value"] == "Kate, Senior Manager"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_person_detail_no_area(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Person with no primary_area_id: primary_area_name is null, no area-linked facts."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    # Seed an area with a fact — should NOT appear because person has no area
    area_id = await _seed_area(db_session, company_id, "Finance")
    await _seed_accepted_fact(
        db_session, company_id, "technology", "Excel",
        functional_area_id=area_id,
    )
    person_id = await _seed_person(db_session, company_id, "Leo")  # no area

    response = await client.get(
        f"/api/v1/companies/{company_id}/people/{person_id}"
    )
    assert response.status_code == 200
    d = response.json()
    assert d["primary_area_name"] is None
    # No area-linked technology fact — only name-matched person facts could appear
    area_facts = [f for f in d["inferred_facts"] if f["category"] == "technology"]
    assert area_facts == []


@pytest.mark.asyncio(loop_scope="session")
async def test_get_person_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET with unknown person_id returns 404."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.get(
        f"/api/v1/companies/{company_id}/people/{uuid4()}"
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /companies/{id}/people/{person_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_update_person_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with new name returns 200 and PersonDetail with updated name."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    person_id = await _seed_person(db_session, company_id, "Mia")

    response = await client.put(
        f"/api/v1/companies/{company_id}/people/{person_id}",
        json={"name": "Mia Updated"},
    )
    assert response.status_code == 200
    d = response.json()
    assert d["name"] == "Mia Updated"
    assert d["person_id"] == str(person_id)


@pytest.mark.asyncio(loop_scope="session")
async def test_update_person_area(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with primary_area_id returns 200 with area_name populated."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    area_id = await _seed_area(db_session, company_id, "Design")
    person_id = await _seed_person(db_session, company_id, "Nina")

    response = await client.put(
        f"/api/v1/companies/{company_id}/people/{person_id}",
        json={"primary_area_id": str(area_id)},
    )
    assert response.status_code == 200
    d = response.json()
    assert d["primary_area_id"] == str(area_id)
    assert d["primary_area_name"] == "Design"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_person_reports_to(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with reports_to_person_id persists the FK."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    mgr_id = await _seed_person(db_session, company_id, "Oscar")
    person_id = await _seed_person(db_session, company_id, "Pat")

    response = await client.put(
        f"/api/v1/companies/{company_id}/people/{person_id}",
        json={"reports_to_person_id": str(mgr_id)},
    )
    assert response.status_code == 200
    d = response.json()
    assert d["reports_to_person_id"] == str(mgr_id)
    assert d["reports_to_name"] == "Oscar"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_person_clear_area(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT with primary_area_id=null clears the area assignment."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    area_id = await _seed_area(db_session, company_id, "Legal")
    person_id = await _seed_person(
        db_session, company_id, "Quinn", primary_area_id=area_id
    )

    response = await client.put(
        f"/api/v1/companies/{company_id}/people/{person_id}",
        json={"primary_area_id": None},
    )
    assert response.status_code == 200
    d = response.json()
    assert d["primary_area_id"] is None
    assert d["primary_area_name"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_update_person_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PUT on unknown person_id returns 404."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.put(
        f"/api/v1/companies/{company_id}/people/{uuid4()}",
        json={"name": "Ghost"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /companies/{id}/people/{person_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_person(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """DELETE returns 204 and person is gone."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    person_id = await _seed_person(db_session, company_id, "Ray")

    response = await client.delete(
        f"/api/v1/companies/{company_id}/people/{person_id}"
    )
    assert response.status_code == 204

    # Subsequent GET returns 404
    get_response = await client.get(
        f"/api/v1/companies/{company_id}/people/{person_id}"
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_person_cascades(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """DELETE a manager: relationship row is deleted (CASCADE) and
    subordinate's reports_to_person_id is set to null (SET NULL on persons FK)."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    from app.models.base import Relationship

    mgr_id = await _seed_person(db_session, company_id, "Sam")
    sub_id = await _seed_person(
        db_session, company_id, "Tina", reports_to_person_id=mgr_id
    )

    # Seed a relationship row
    rel = Relationship(
        company_id=UUID(company_id),
        subordinate_person_id=sub_id,
        manager_person_id=mgr_id,
    )
    db_session.add(rel)
    await db_session.flush()
    await db_session.refresh(rel)
    rel_id = rel.id

    # Delete the manager
    response = await client.delete(
        f"/api/v1/companies/{company_id}/people/{mgr_id}"
    )
    assert response.status_code == 204

    # Relationship row should be gone (ON DELETE CASCADE)
    from sqlalchemy import select
    result = await db_session.execute(
        select(Relationship).where(Relationship.id == rel_id)
    )
    assert result.scalar_one_or_none() is None

    # Subordinate's reports_to_person_id should be null (ON DELETE SET NULL)
    from app.models.base import Person as PersonModel
    await db_session.refresh(
        await db_session.get(PersonModel, sub_id)
    )
    sub = await db_session.get(PersonModel, sub_id)
    assert sub.reports_to_person_id is None


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_person_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """DELETE with unknown person_id returns 404."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)

    response = await client.delete(
        f"/api/v1/companies/{company_id}/people/{uuid4()}"
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_people_unauthenticated(client: AsyncClient) -> None:
    """All people endpoints require authentication."""
    client.cookies.clear()
    try:
        response = await client.get(
            f"/api/v1/companies/{uuid4()}/people"
        )
        assert response.status_code == 401
    finally:
        await _ensure_authenticated(client)
