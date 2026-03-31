"""Route handlers for /auth/* endpoints."""

from fastapi import APIRouter, Depends, Response

from app.dependencies import get_auth_service, get_current_session
from app.schemas.auth import LoginRequest, OkResponse, PasswordChangeRequest, PasswordSetRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/password/set", response_model=OkResponse)
async def password_set(
    body: PasswordSetRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> OkResponse:
    """Set password on first access. No session required."""
    await auth_service.set_password(body.username, body.password)
    return OkResponse()


@router.post("/login", response_model=OkResponse)
async def login(
    body: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> OkResponse:
    """Authenticate and return a session cookie."""
    token = await auth_service.login(body.username, body.password)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return OkResponse()


@router.post("/logout", response_model=OkResponse)
async def logout(
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    session_token: str = Depends(get_current_session),
) -> OkResponse:
    """Invalidate the current session."""
    await auth_service.logout(session_token)
    response.delete_cookie(key="session")
    return OkResponse()


@router.get("/me", response_model=OkResponse)
async def me(
    _session_token: str = Depends(get_current_session),
) -> OkResponse:
    """Lightweight session check. Returns 200 if authenticated, 401 otherwise."""
    return OkResponse()


@router.post("/password/change", response_model=OkResponse)
async def password_change(
    body: PasswordChangeRequest,
    auth_service: AuthService = Depends(get_auth_service),
    session_token: str = Depends(get_current_session),
) -> OkResponse:
    """Change password. Requires valid session and current password."""
    await auth_service.change_password(session_token, body.current_password, body.new_password)
    return OkResponse()
