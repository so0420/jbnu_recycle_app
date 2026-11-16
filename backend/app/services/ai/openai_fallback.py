"""2차 판정: OpenAI. 1차가 애매할 때만 호출하고, 하루 토큰 한도를 넘지 않게 막는다."""
import json

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import AiUsage
from app.services.clock import today
from app.utils.log import logger

PROVIDER = "openai"


class OpenAIUnavailable(Exception):
    pass


async def tokens_used_today(db: AsyncSession) -> int:
    row = await db.get(AiUsage, (today(), PROVIDER))
    return row.tokens if row else 0


async def tokens_used_today_fresh(db: AsyncSession | None = None) -> int:
    """호출한 쪽 트랜잭션과 따로 읽는다 (OpenAI 를 기다리는 동안 연결을 잡고 있지 않게)."""
    from app.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as s:
        row = await s.get(AiUsage, (today(), PROVIDER))
        return row.tokens if row else 0


async def _record(tokens: int) -> None:
    """토큰 사용량은 요청 트랜잭션과 따로, 원자적으로 더한다 (요청이 실패해도 남는다)."""
    from app.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as s:
        stmt = mysql_insert(AiUsage).values(day=today(), provider=PROVIDER, tokens=tokens, calls=1)
        await s.execute(stmt.on_duplicate_key_update(tokens=AiUsage.tokens + stmt.inserted.tokens,
                                                     calls=AiUsage.calls + 1))
        await s.commit()


_client = None


def client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT, max_retries=1)
    return _client


async def ask_json(db: AsyncSession, prompt: str, image_b64: str | None, schema: dict, name: str) -> dict:
    """구조화된 JSON 답을 받는다. 키가 없거나 한도를 넘으면 OpenAIUnavailable."""
    if not settings.OPENAI_API_KEY:
        raise OpenAIUnavailable("OPENAI_API_KEY 없음")
    if await tokens_used_today_fresh(db) >= settings.OPENAI_DAILY_TOKEN_LIMIT:
        raise OpenAIUnavailable("오늘 OpenAI 토큰 한도 도달")
    content: list[dict] = [{"type": "input_text", "text": prompt}]
    if image_b64:
        content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"})
    try:
        resp = await client().responses.create(
            model=settings.OPENAI_MODEL,
            store=False,                       # OpenAI 쪽에 대화 저장하지 않음
            input=[{"role": "user", "content": content}],
            text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
        )
    except Exception as e:  # 네트워크·모델 오류 모두 2차 실패로 처리
        logger.warning(f"OpenAI 호출 실패: {e!r}")
        raise OpenAIUnavailable(str(e)) from e
    usage = getattr(resp, "usage", None)
    await _record(int(getattr(usage, "total_tokens", 0) or 0))
    try:
        return json.loads(resp.output_text)
    except (ValueError, AttributeError) as e:
        raise OpenAIUnavailable("JSON 응답 해석 실패") from e
