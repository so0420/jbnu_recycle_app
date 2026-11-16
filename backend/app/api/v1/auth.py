import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import auth
from app.core.security import limiter
from app.database import get_db
from app.models import Region, User
from app.services.clock import now

router = APIRouter()
POLICY_VERSION = "2026-11-16"

ID_RE = re.compile(r"^[a-z0-9_]{4,20}$")


class SignupIn(BaseModel):
    login_id: str = Field(min_length=4, max_length=20)
    password: str = Field(min_length=8, max_length=72)
    nickname: str = Field(min_length=2, max_length=12)
    region_code: str | None = None
    agree_terms: bool
    agree_privacy: bool
    agree_age: bool
    agree_location: bool


class LoginIn(BaseModel):
    login_id: str
    password: str


@router.post("/signup")
@limiter.limit("10/hour")
async def signup(request: Request, body: SignupIn, response: Response, db: AsyncSession = Depends(get_db)):
    lid = body.login_id.strip().lower()
    if not ID_RE.match(lid):
        raise HTTPException(400, "아이디는 영문 소문자·숫자·밑줄 4~20자로 만들어 주세요")
    if not (body.agree_terms and body.agree_privacy and body.agree_location):
        raise HTTPException(400, "필수 약관(이용약관, 개인정보, 위치정보)에 모두 동의해 주세요")
    if not body.agree_age:
        raise HTTPException(400, "만 14세 이상만 가입할 수 있어요")
    if not auth.password_ok(body.password):
        raise HTTPException(400, auth.PASSWORD_RULE)
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
    t = now()
    user = User(login_id=lid, password_hash=auth.hash_password(body.password), nickname=nick, role="user",
                agreed_terms_at=t, age_confirmed_at=t, agreed_location_at=t, policy_version=POLICY_VERSION,
                token_version=0,
                region_code=region.code if region else None, xp=0, level=1, coins=0, tickets=0, crystals=0,
                bag_capacity=6, pity=0, starter_done=False)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "이미 쓰고 있는 아이디 또는 닉네임이에요")
    auth.issue(response, user)
    return {"ok": True}


@router.post("/login")
@limiter.limit("20/minute")
async def login(request: Request, body: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.login_id == body.login_id.strip().lower()))).scalars().first()
    if user is None or user.deleted_at is not None or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "아이디 또는 비밀번호가 맞지 않아요")
    auth.issue(response, user)
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """로그아웃: 이 계정의 모든 기기 세션을 끊는다 (토큰 버전 증가)."""
    try:
        user = await auth.current_user(request, db)
        user.token_version = (user.token_version or 0) + 1
        await db.commit()
    except HTTPException:
        pass
    auth.clear(response)
    return {"ok": True}
