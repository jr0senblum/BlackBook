"""API tests for /companies/* endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

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


# ── POST /companies ─────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_create_company(client: AsyncClient) -> None:
    """POST /companies creates a company and returns 201."""
    await _ensure_authenticated(client)
    response = await client.post(
        "/api/v1/companies",
        json={"name": "API Test Corp", "mission": "Test mission"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API Test Corp"
    assert "company_id" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_create_company_duplicate_name(client: AsyncClient) -> None:
    """POST /companies with duplicate name returns 409."""
    await _ensure_authenticated(client)
    await client.post(
        "/api/v1/companies",
        json={"name": "Duplicate API Corp"},
    )
    response = await client.post(
        "/api/v1/companies",
        json={"name": "duplicate api corp"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "name_conflict"


@pytest.mark.asyncio(loop_scope="session")
async def test_create_company_unauthenticated(client: AsyncClient) -> None:
    """POST /companies without session returns 401."""
    client.cookies.clear()
    response = await client.post(
        "/api/v1/companies",
        json={"name": "Unauth Corp"},
    )
    assert response.status_code == 401


# ── GET /companies ───────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_list_companies(client: AsyncClient) -> None:
    """GET /companies returns paginated list."""
    await _ensure_authenticated(client)
    # Create a company first
    await client.post(
        "/api/v1/companies",
        json={"name": "List API Corp"},
    )
    response = await client.get("/api/v1/companies")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert data["total"] >= 1
    names = [item["name"] for item in data["items"]]
    assert "List API Corp" in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_companies_pagination(client: AsyncClient) -> None:
    """GET /companies respects limit and offset."""
    await _ensure_authenticated(client)
    response = await client.get("/api/v1/companies?limit=1&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 1
    assert len(data["items"]) <= 1


# ── GET /companies/{id} ─────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_get_company(client: AsyncClient) -> None:
    """GET /companies/{id} returns company detail."""
    await _ensure_authenticated(client)
    create_resp = await client.post(
        "/api/v1/companies",
        json={"name": "Get API Corp", "mission": "A mission", "vision": "A vision"},
    )
    company_id = create_resp.json()["company_id"]
    response = await client.get(f"/api/v1/companies/{company_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Get API Corp"
    assert data["mission"] == "A mission"
    assert data["vision"] == "A vision"
    assert data["pending_count"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_get_company_not_found(client: AsyncClient) -> None:
    """GET /companies/{id} with non-existent id returns 404."""
    await _ensure_authenticated(client)
    fake_id = str(uuid4())
    response = await client.get(f"/api/v1/companies/{fake_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ── PUT /companies/{id} ─────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company(client: AsyncClient) -> None:
    """PUT /companies/{id} updates fields and returns detail."""
    await _ensure_authenticated(client)
    create_resp = await client.post(
        "/api/v1/companies",
        json={"name": "Update API Corp"},
    )
    company_id = create_resp.json()["company_id"]
    response = await client.put(
        f"/api/v1/companies/{company_id}",
        json={"name": "Updated API Corp", "mission": "New mission"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated API Corp"
    assert data["mission"] == "New mission"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company_not_found(client: AsyncClient) -> None:
    """PUT /companies/{id} with non-existent id returns 404."""
    await _ensure_authenticated(client)
    fake_id = str(uuid4())
    response = await client.put(
        f"/api/v1/companies/{fake_id}",
        json={"name": "X"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company_null_name_rejected(client: AsyncClient) -> None:
    """PUT /companies/{id} with name: null returns 422."""
    await _ensure_authenticated(client)
    create_resp = await client.post(
        "/api/v1/companies",
        json={"name": "Null Name Corp"},
    )
    company_id = create_resp.json()["company_id"]
    response = await client.put(
        f"/api/v1/companies/{company_id}",
        json={"name": None},
    )
    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company_nullify_mission(client: AsyncClient) -> None:
    """PUT /companies/{id} with mission: null clears the field."""
    await _ensure_authenticated(client)
    create_resp = await client.post(
        "/api/v1/companies",
        json={"name": "Nullify API Corp", "mission": "Old mission"},
    )
    company_id = create_resp.json()["company_id"]
    response = await client.put(
        f"/api/v1/companies/{company_id}",
        json={"mission": None},
    )
    assert response.status_code == 200
    assert response.json()["mission"] is None
    # Name should be unchanged.
    assert response.json()["name"] == "Nullify API Corp"


# ── DELETE /companies/{id} ───────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_company(client: AsyncClient) -> None:
    """DELETE /companies/{id} removes the company (204)."""
    await _ensure_authenticated(client)
    create_resp = await client.post(
        "/api/v1/companies",
        json={"name": "Delete API Corp"},
    )
    company_id = create_resp.json()["company_id"]
    response = await client.delete(f"/api/v1/companies/{company_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_resp = await client.get(f"/api/v1/companies/{company_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_company_not_found(client: AsyncClient) -> None:
    """DELETE /companies/{id} with non-existent id returns 404."""
    await _ensure_authenticated(client)
    fake_id = str(uuid4())
    response = await client.delete(f"/api/v1/companies/{fake_id}")
    assert response.status_code == 404
