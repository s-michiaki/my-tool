"""FastAPI dependencies."""
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Query, WebSocket, WebSocketException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import decode_token
from .database import get_db
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def _user_from_token(token: str, db: AsyncSession) -> User:
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise ValueError("missing sub")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")
    return user


async def get_current_user(
    token: Annotated[Optional[str], Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return await _user_from_token(token, db)


def require_role(*roles: str):
    async def _guard(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user
    return _guard


async def ws_authenticate(
    websocket: WebSocket,
    token: Annotated[Optional[str], Query()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """WebSocket 用の JWT 認証 (クエリ ?token=... で受け取る)。"""
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
    try:
        return await _user_from_token(token, db)
    except HTTPException as e:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=e.detail)
