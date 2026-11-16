"""아이디/비밀번호 로그인. 비밀번호는 scrypt 해시, 세션은 httpOnly 쿠키의 JWT."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db
from app.models import User

COOKIE = "rc_session"
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_b64, dk_b64 = stored.split("$")
        dk = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p),
                            dklen=32)
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


PASSWORD_RULE = "비밀번호는 영문과 숫자를 섞어 8자 이상으로 만들어 주세요"


def password_ok(pw: str) -> bool:
    import re
    return 8 <= len(pw) <= 72 and bool(re.search(r"[A-Za-z]", pw)) and bool(re.search(r"\d", pw))


def issue(response: Response, user: User) -> None:
    exp = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRE_DAYS)
    token = jwt.encode({"sub": str(user.id), "v": user.token_version or 0, "exp": exp}, settings.JWT_SECRET,
                       algorithm="HS256")
    response.set_cookie(COOKIE, token, max_age=settings.JWT_EXPIRE_DAYS * 86400, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite="lax", path="/")


def clear(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


async def current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요합니다")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        uid = int(payload["sub"])
        ver = int(payload.get("v", 0))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "다시 로그인해 주세요")
    user = await db.get(User, uid)
    if user is None or user.deleted_at is not None or (user.token_version or 0) != ver:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "다시 로그인해 주세요")
    return user


async def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "관리자만 사용할 수 있습니다")
    return user
