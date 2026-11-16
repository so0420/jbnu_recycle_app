"""사용자·지역·수거장·AI 기록 등 기본 테이블."""
from datetime import date, datetime

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.mixins import TimestampMixin


class Zone(Base):
    """시연용 권역 (행정동 묶음)."""
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40))


class Region(Base):
    """전주시 행정동."""
    __tablename__ = "regions"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    gu: Mapped[str] = mapped_column(String(20))
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)
    neighbors: Mapped[str] = mapped_column(Text, default="")  # ';' 구분 코드
    # 재활용 수거 요일 (0=일 … 6=토, ',' 구분). 비어 있으면 매일 배출일로 본다
    dump_weekdays: Mapped[str] = mapped_column(String(20), default="")
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), nullable=True)


class Place(Base):
    __tablename__ = "places"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str] = mapped_column(String(40), default="")
    kind: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    address: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[str] = mapped_column(String(200), default="")
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    hours: Mapped[str] = mapped_column(String(80), default="")
    items: Mapped[str] = mapped_column(String(200), default="")
    region_code: Mapped[str | None] = mapped_column(ForeignKey("regions.code"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("ix_places_latlng", "lat", "lng"),)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login_id: Mapped[str] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    nickname: Mapped[str] = mapped_column(String(30))
    role: Mapped[str] = mapped_column(String(10), default="user")
    agreed_terms_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    region_code: Mapped[str | None] = mapped_column(ForeignKey("regions.code"), nullable=True)
    region_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    region_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 캐시 값 (원본은 economy_events)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    tickets: Mapped[int] = mapped_column(Integer, default=0)
    crystals: Mapped[int] = mapped_column(Integer, default=0)
    bag_capacity: Mapped[int] = mapped_column(Integer, default=6)
    pity: Mapped[int] = mapped_column(Integer, default=0)
    starter_done: Mapped[bool] = mapped_column(Boolean, default=False)
    last_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ClassifyLog(Base):
    __tablename__ = "classify_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    photo_path: Mapped[str] = mapped_column(String(200))
    phash: Mapped[str] = mapped_column(String(16), index=True)
    s1_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    s2_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    item_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    judged_by: Mapped[str] = mapped_column(String(20), default="none")
    clean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    habit_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Verification(Base):
    __tablename__ = "verifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"), nullable=True, index=True)
    photo_path: Mapped[str] = mapped_column(String(200), default="")
    phash: Mapped[str] = mapped_column(String(16), default="", index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[str] = mapped_column(String(10))  # success | fail
    fail_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    judged_by: Mapped[str] = mapped_column(String(20), default="none")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    reward_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class AiUsage(Base):
    __tablename__ = "ai_usage"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    calls: Mapped[int] = mapped_column(Integer, default=0)


class JobLog(Base):
    __tablename__ = "job_log"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    done_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


__all__ = ["Zone", "Region", "Place", "User", "ClassifyLog", "Verification", "AiUsage", "JobLog",
           "UniqueConstraint"]
