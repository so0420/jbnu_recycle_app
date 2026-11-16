"""2차 판정: OpenAI. 1차가 애매할 때만 호출하고, 하루 토큰 한도를 넘지 않게 막는다."""
import json

from sqlalchemy import select
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


async def _record(db: AsyncSession, tokens: int) -> None:
    row = await db.get(AiUsage, (today(), PROVIDER))
    if row is None:
        row = AiUsage(day=today(), provider=PROVIDER, tokens=0, calls=0)
        db.add(row)
    row.tokens += tokens
    row.calls += 1
    await db.flush()


async def ask_json(db: AsyncSession, prompt: str, image_b64: str | None, schema: dict, name: str) -> dict:
    """구조화된 JSON 답을 받는다. 키가 없거나 한도를 넘으면 OpenAIUnavailable."""
    if not settings.OPENAI_API_KEY:
        raise OpenAIUnavailable("OPENAI_API_KEY 없음")
    if await tokens_used_today(db) >= settings.OPENAI_DAILY_TOKEN_LIMIT:
        raise OpenAIUnavailable("오늘 OpenAI 토큰 한도 도달")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT)
    content: list[dict] = [{"type": "input_text", "text": prompt}]
    if image_b64:
        content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"})
    try:
        resp = await client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[{"role": "user", "content": content}],
            text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
        )
    except Exception as e:  # 네트워크·모델 오류 모두 2차 실패로 처리
        logger.warning(f"OpenAI 호출 실패: {e!r}")
        raise OpenAIUnavailable(str(e)) from e
    usage = getattr(resp, "usage", None)
    await _record(db, int(getattr(usage, "total_tokens", 0) or 0))
    try:
        return json.loads(resp.output_text)
    except (ValueError, AttributeError) as e:
        raise OpenAIUnavailable("JSON 응답 해석 실패") from e
