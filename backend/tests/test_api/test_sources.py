"""API tests for source endpoints."""

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.source_repository import SourceRepository

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
    name = name or f"SrcTestCo-{uuid4().hex[:8]}"
    response = await client.post("/api/v1/companies", json={"name": name})
    assert response.status_code == 201
    return str(response.json()["company_id"])


# ═════════════════════════════════════════════════════════════════
# POST /sources/upload
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_with_company_id(client: AsyncClient) -> None:
    """POST /sources/upload with file and company_id returns 200."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    content = "p: Alice, CEO\ntech: Python"
    response = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("notes.txt", content.encode(), "text/plain")},
        data={"company_id": company_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert "source_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_with_nc_prefix(client: AsyncClient) -> None:
    """POST /sources/upload without company_id, file contains nc: → 200."""
    await _ensure_authenticated(client)
    name = f"NCUpload-{uuid4().hex[:8]}"
    content = f"nc: {name}\np: Bob, VP"
    response = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("notes.txt", content.encode(), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "source_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_tagless_with_company_id_param(client: AsyncClient) -> None:
    """POST /sources/upload with a completely tagless file succeeds when
    company_id form param is provided (§17 requirement)."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    # File has no prefixes at all — entirely unstructured text
    content = "Alice is the CEO and founded the company in 2019\nThey use Python and Kubernetes"
    response = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("notes.txt", content.encode(), "text/plain")},
        data={"company_id": company_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert "source_id" in data
    assert data["status"] == "pending"

    # Verify the source is routed to the correct company
    source_id = data["source_id"]
    detail = await client.get(f"/api/v1/sources/{source_id}")
    assert detail.status_code == 200
    assert detail.json()["company_id"] == company_id
    assert detail.json()["raw_content"] == content


@pytest.mark.asyncio(loop_scope="session")
async def test_upload_without_routing_fails(client: AsyncClient) -> None:
    """POST /sources/upload without any routing → 422."""
    await _ensure_authenticated(client)
    content = "p: Carol\ntech: Docker"
    response = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("notes.txt", content.encode(), "text/plain")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "routing_error"


# ═════════════════════════════════════════════════════════════════
# GET /companies/{id}/sources
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_list_sources(client: AsyncClient) -> None:
    """GET /companies/{id}/sources returns a paginated list."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    # Upload two sources
    for i in range(2):
        await client.post(
            "/api/v1/sources/upload",
            files={
                "file": (f"file{i}.txt", f"p: Person{i}".encode(), "text/plain")
            },
            data={"company_id": company_id},
        )

    response = await client.get(f"/api/v1/companies/{company_id}/sources")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert "source_id" in data["items"][0]
    assert "status" in data["items"][0]
    assert "received_at" in data["items"][0]


# ═════════════════════════════════════════════════════════════════
# GET /sources/{id} and GET /sources/{id}/status
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_get_source_detail(client: AsyncClient) -> None:
    """GET /sources/{id} returns full source detail."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    upload = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("detail.txt", b"p: Dave, CTO", "text/plain")},
        data={"company_id": company_id},
    )
    source_id = upload.json()["source_id"]

    response = await client.get(f"/api/v1/sources/{source_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["source_id"] == source_id
    assert data["raw_content"] == "p: Dave, CTO"
    assert data["status"] == "pending"
    assert data["company_id"] == company_id


@pytest.mark.asyncio(loop_scope="session")
async def test_get_source_not_found(client: AsyncClient) -> None:
    """GET /sources/{id} for a non-existent ID returns 404."""
    await _ensure_authenticated(client)
    response = await client.get(f"/api/v1/sources/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_get_source_status(client: AsyncClient) -> None:
    """GET /sources/{id}/status returns status only."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    upload = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("status.txt", b"tech: React", "text/plain")},
        data={"company_id": company_id},
    )
    source_id = upload.json()["source_id"]

    response = await client.get(f"/api/v1/sources/{source_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["source_id"] == source_id
    assert data["status"] == "pending"


# ═════════════════════════════════════════════════════════════════
# POST /sources/{id}/retry
# ═════════════════════════════════════════════════════════════════


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_non_failed_source_returns_409(
    client: AsyncClient,
) -> None:
    """POST /sources/{id}/retry on a non-failed source returns 409."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    upload = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("retry.txt", b"p: Eve", "text/plain")},
        data={"company_id": company_id},
    )
    source_id = upload.json()["source_id"]

    response = await client.post(f"/api/v1/sources/{source_id}/retry")
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "state_conflict"


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_failed_source_returns_200(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /sources/{id}/retry on a failed source resets to pending and returns 200."""
    await _ensure_authenticated(client)
    company_id = await _create_company(client)
    upload = await client.post(
        "/api/v1/sources/upload",
        files={"file": ("retry_ok.txt", b"p: Fiona", "text/plain")},
        data={"company_id": company_id},
    )
    source_id = upload.json()["source_id"]

    # Set source to failed via the repository (no API to do this directly)
    source_repo = SourceRepository(db_session)
    await source_repo.update_status(
        UUID(source_id), status="failed", error="simulated failure"
    )

    response = await client.post(f"/api/v1/sources/{source_id}/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["source_id"] == source_id
    assert data["status"] == "pending"

    # Verify the source is actually reset
    status_resp = await client.get(f"/api/v1/sources/{source_id}/status")
    assert status_resp.json()["status"] == "pending"
