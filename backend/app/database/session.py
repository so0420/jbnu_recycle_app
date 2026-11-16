from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.DB_ECHO,
    hide_parameters=settings.ENVIRONMENT == "production",   # 오류 기록에 좌표 같은 값이 남지 않게
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    # 같은 사용자의 요청은 users 행 잠금으로 줄 세운다. 잠금을 기다린 뒤에는 최신 값을 읽어야 하므로 READ COMMITTED
    isolation_level="READ COMMITTED",
    connect_args={"init_command": "SET time_zone='+09:00'"},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성: 요청 단위 AsyncSession 제공."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
