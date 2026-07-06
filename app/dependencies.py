import logging
from typing import Generator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)

_VALID_PERMISSIONS = frozenset(
    {"approval:read", "approval:create", "approval:decide", "approval:cancel"}
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AuthContext:
    def __init__(self, user_id: str, permissions: frozenset[str]) -> None:
        self.user_id = user_id
        self.permissions = permissions

    def require(self, action: str) -> None:
        if action not in self.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {action}",
            )


def get_auth(
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_permissions: str = Header(..., alias="X-Permissions"),
) -> AuthContext:
    user_id = x_user_id.strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-Id is required")
    perms = frozenset(p.strip() for p in x_permissions.split(",") if p.strip())
    unknown = perms - _VALID_PERMISSIONS
    if unknown:
        logger.warning("Request from %s includes unknown permissions: %s", user_id, unknown)
    return AuthContext(user_id=user_id, permissions=perms)
