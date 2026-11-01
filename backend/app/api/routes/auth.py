"""Authentication routes: login, refresh, logout, me."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.user import User
from app.modules.auth.service import authenticate_user, issue_tokens, refresh_tokens, to_me_response
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
    UserMeResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = authenticate_user(db, body.email, body.password)
    tokens = issue_tokens(user)
    db.add(
        AuditLog(
            actor_id=user.id,
            action="auth.login",
            resource_type="user",
            resource_id=str(user.id),
            details="User logged in",
            ip_address=_client_ip(request),
        )
    )
    db.commit()
    logger.info("User %s logged in", user.email)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return refresh_tokens(db, body.refresh_token)


@router.post("/logout", response_model=MessageResponse, status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    body: LogoutRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Stateless JWT logout — client discards tokens; event is audited.

    Refresh-token denylist is deferred; clients must drop both tokens.
    """
    _ = body
    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="auth.logout",
            resource_type="user",
            resource_id=str(current_user.id),
            details="User logged out",
            ip_address=_client_ip(request),
        )
    )
    db.commit()
    logger.info("User %s logged out", current_user.email)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserMeResponse)
def me(current_user: User = Depends(get_current_user)) -> UserMeResponse:
    return to_me_response(current_user)
