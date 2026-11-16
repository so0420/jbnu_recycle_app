import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.core.config import settings
from app.core.security import limiter
from app.database import get_db
from app.models import Region, User
from app.services.clock import now

router = APIRouter()

ID_RE = re.compile(r"^[a-z0-9_]{4,20}$")


class SignupIn(BaseModel):
    login_id: str = Field(min_length=4, max_length=20)
    password: str = Field(min_length=8, max_length=72)
    nickname: str = Field(min_length=2, max_length=12)
    region_code: str | None = None
    agree_terms: bool
    agree_privacy: bool


class LoginIn(BaseModel):
    login_id: str
    password: str


@router.post("/signup")
@limiter.limit("10/hour")
async def signup(request: Request, body: SignupIn, response: Response, db: AsyncSession = Depends(get_db)):
    lid = body.login_id.strip().lower()
    if not ID_RE.match(lid):
        raise HTTPException(400, "아이디는 영문 소문자·숫자·밑줄 4~20자로 만들어 주세요")
    if not (body.agree_terms and body.agree_privacy):
        raise HTTPException(400, "이용약관과 개인정보 처리방침에 동의해 주세요")
    if not (re.search(r"[A-Za-z]", body.password) and re.search(r"\d", body.password)):
        raise HTTPException(400, "비밀번호는 영문과 숫자를 섞어 8자 이상으로 만들어 주세요")
    nick = body.nickname.strip()
    if (await db.execute(select(User.id).where(User.login_id == lid))).first():
        raise HTTPException(409, "이미 쓰고 있는 아이디예요")
    if (await db.execute(select(User.id).where(User.nickname == nick))).first():
        raise HTTPException(409, "이미 쓰고 있는 닉네임이에요")
    region = None
    if body.region_code:
        region = await db.get(Region, body.region_code)
        if region is None:
            raise HTTPException(400, "동네를 다시 골라 주세요")
    user = User(login_id=lid, password_hash=auth.hash_password(body.password), nickname=nick,
                role="admin" if lid in settings.ADMIN_LOGIN_IDS else "user", agreed_terms_at=now(),
                region_code=region.code if region else None, xp=0, level=1, coins=0, tickets=0, crystals=0,
                bag_capacity=6, pity=0, starter_done=False)
    db.add(user)
    await db.commit()
    auth.issue(response, user.id)
    return {"ok": True}


@router.post("/login")
@limiter.limit("20/minute")
async def login(request: Request, body: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.login_id == body.login_id.strip().lower()))).scalars().first()
    if user is None or user.deleted_at is not None or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "아이디 또는 비밀번호가 맞지 않아요")
    if user.login_id in settings.ADMIN_LOGIN_IDS and user.role != "admin":
        user.role = "admin"
        await db.commit()
    auth.issue(response, user.id)
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    auth.clear(response)
    return {"ok": True}
