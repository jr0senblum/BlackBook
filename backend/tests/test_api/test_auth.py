"""API tests for /auth/* endpoints."""

import pytest
from httpx import AsyncClient

USERNAME = "investigator"
PASSWORD = "testpassword123"


async def _set_password(client: AsyncClient) -> None:
    """Helper: ensure a credential exists (idempotent)."""
    await client.post(
        "/api/v1/auth/password/set",
        json={"username": USERNAME, "password": PASSWORD},
    )


async def _login(client: AsyncClient) -> None:
    """Helper: set password + login. Client stores the session cookie."""
    await _set_password(client)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )
    assert resp.status_code == 200


# ── password/set ─────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_password_set(client: AsyncClient) -> None:
    """POST /auth/password/set succeeds on first call."""
    response = await client.post(
        "/api/v1/auth/password/set",
        json={"username": USERNAME, "password": PASSWORD},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio(loop_scope="session")
async def test_password_set_idempotency(client: AsyncClient) -> None:
    """POST /auth/password/set returns 409 on second call."""
    # Ensure credential exists first.
    await _set_password(client)
    response = await client.post(
        "/api/v1/auth/password/set",
        json={"username": USERNAME, "password": "anotherpassword"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_set"


# ── login ────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_login_success(client: AsyncClient) -> None:
    """POST /auth/login with valid credentials returns 200 and sets session cookie."""
    await _set_password(client)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "session" in response.cookies


@pytest.mark.asyncio(loop_scope="session")
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    """POST /auth/login with wrong password returns 401."""
    await _set_password(client)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": USERNAME, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio(loop_scope="session")
async def test_login_invalid_username(client: AsyncClient) -> None:
    """POST /auth/login with wrong username returns 401."""
    await _set_password(client)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


# ── logout ───────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_logout(client: AsyncClient) -> None:
    """POST /auth/logout invalidates session; subsequent requests are rejected."""
    await _login(client)
    logout_resp = await client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json() == {"ok": True}
    # Verify session is actually invalid — a protected endpoint should 401.
    protected_resp = await client.get("/api/v1/companies")
    assert protected_resp.status_code == 401


# ── password/change ──────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_password_change_success(client: AsyncClient) -> None:
    """POST /auth/password/change succeeds; old password fails, new works."""
    await _login(client)
    response = await client.post(
        "/api/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": "newpassword456"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    # Verify old password no longer works.
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
    )
    assert old_login.status_code == 401

    # Verify new password works.
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"username": USERNAME, "password": "newpassword456"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_password_change_wrong_current(client: AsyncClient) -> None:
    """POST /auth/password/change with wrong current password returns 401."""
    await _login(client)
    response = await client.post(
        "/api/v1/auth/password/change",
        json={"current_password": "wrongpassword", "new_password": "newpassword456"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_current_password"


# ── unauthenticated ──────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_protected_endpoint_without_session(client: AsyncClient) -> None:
    """Protected endpoint without session cookie returns 401."""
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
