"""게임 테이블: 리몬, 재료, 가방, 캡슐, 도감, 레이드, 지역 청결도, 경제 기록."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserMonster(Base):
    __tablename__ = "user_monsters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    species: Mapped[str] = mapped_column(String(30))       # 진화 계열 id (예: petring)
    stage: Mapped[int] = mapped_column(Integer, default=1)
    level: Mapped[int] = mapped_column(Integer, default=1)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    is_shiny: Mapped[bool] = mapped_column(Boolean, default=False)
    slot: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 파티 자리 0=앞줄, 1·2=뒷줄
    skill_timing: Mapped[str] = mapped_column(String(10), default="now")  # now | boss50 | ally30
    expedition_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserMaterial(Base):
    __tablename__ = "user_materials"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    material: Mapped[str] = mapped_column(String(20), primary_key=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)


class BagItem(Base):
    __tablename__ = "bag_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(30))
    item_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    type: Mapped[str] = mapped_column(String(10))
    is_clean: Mapped[bool] = mapped_column(Boolean, default=False)
    habit_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    classify_log_id: Mapped[int | None] = mapped_column(ForeignKey("classify_logs.id"), nullable=True)
    settled_verification_id: Mapped[int | None] = mapped_column(ForeignKey("verifications.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Capsule(Base):
    __tablename__ = "capsules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(20))
    bonus_rare: Mapped[float] = mapped_column(Float, default=0.0)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_monster_id: Mapped[int | None] = mapped_column(ForeignKey("user_monsters.id"), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HabitProgress(Base):
    __tablename__ = "habit_progress"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    type: Mapped[str] = mapped_column(String(10), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class DexEntry(Base):
    __tablename__ = "dex_entries"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)    # monster | item | stamp
    ref: Mapped[str] = mapped_column(String(40), primary_key=True)
    is_shiny: Mapped[bool] = mapped_column(Boolean, default=False)
    first_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserDaily(Base):
    __tablename__ = "user_daily"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    verify_count: Mapped[int] = mapped_column(Integer, default=0)
    guide_xp_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)
    free_raid_used: Mapped[bool] = mapped_column(Boolean, default=False)
    dumpday_ticket: Mapped[bool] = mapped_column(Boolean, default=False)
    raid_count: Mapped[int] = mapped_column(Integer, default=0)
    levelup_count: Mapped[int] = mapped_column(Integer, default=0)
    expedition_sent: Mapped[int] = mapped_column(Integer, default=0)
    scan_count: Mapped[int] = mapped_column(Integer, default=0)
    missions_claimed: Mapped[list | None] = mapped_column(JSON, nullable=True)


class UserWeekly(Base):
    __tablename__ = "user_weekly"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    verify_count: Mapped[int] = mapped_column(Integer, default=0)
    types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    habit_count: Mapped[int] = mapped_column(Integer, default=0)
    claimed: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Raid(Base):
    __tablename__ = "raids"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit: Mapped[str] = mapped_column(String(12), index=True)      # 행정동 코드 또는 'Z<권역id>'
    boss: Mapped[str] = mapped_column(String(20))
    week_start: Mapped[date] = mapped_column(Date)
    max_hp: Mapped[int] = mapped_column(Integer)
    hp: Mapped[int] = mapped_column(Integer)
    killed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (Index("ux_raid_unit_week", "unit", "week_start", unique=True),)


class RaidAttempt(Base):
    __tablename__ = "raid_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raid_id: Mapped[int] = mapped_column(ForeignKey("raids.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    damage: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    log_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RegionState(Base):
    """주간 시즌별 지역(단위) 청결도."""
    __tablename__ = "region_states"
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    unit: Mapped[str] = mapped_column(String(12), primary_key=True)
    cleanliness: Mapped[float] = mapped_column(Float, default=600.0)
    verifs: Mapped[int] = mapped_column(Integer, default=0)


class RegionEvent(Base):
    __tablename__ = "region_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit: Mapped[str] = mapped_column(String(12), index=True)
    type: Mapped[str] = mapped_column(String(20))       # restore | raid_kill | decay | raid_hit | attack
    amount: Mapped[float] = mapped_column(Float)
    src_unit: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)   # attack: 공격한 쪽 지역
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class EconomyEvent(Base):
    __tablename__ = "economy_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    resource: Mapped[str] = mapped_column(String(20))
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(30))
    ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
