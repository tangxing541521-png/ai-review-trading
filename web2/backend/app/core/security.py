from datetime import datetime, timedelta

import jwt
from app.core.config import settings
from app.services.auth_service import get_user_by_username
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer = HTTPBearer()


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
        username = payload.get("sub")
        if not username:
            raise ValueError("missing subject")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效或已过期")

    user = get_user_by_username(username)
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在或已停用")
    return user
