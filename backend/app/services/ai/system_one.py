"""1차 판정: Ollama System One(clef-flash). 선택지별 확률만 돌려받는다."""
import asyncio

import httpx

from app.core.config import settings
from app.utils.log import logger

# 로컬 모델은 한 번에 하나씩만 처리 (메모리·속도 안정)
_sem = asyncio.Semaphore(1)
_waiting = 0
MAX_QUEUE = 4


class SystemOneBusy(Exception):
    pass


class SystemOneError(Exception):
    pass


async def ask(state: str, images_b64: list[str], questions: dict) -> dict:
    """questions 예: {"category": {"type": "choice", "instructions": ..., "criteria": {...}},
    "dirty": {"type": "noul", "instructions": ...}}
    반환: answers dict (key → {"choice","probabilities",...} 또는 {"noul": p})"""
    global _waiting
    if _waiting >= MAX_QUEUE:
        raise SystemOneBusy()
    _waiting += 1
    try:
        async with _sem:
            payload = {"model": settings.SYSTEM_ONE_MODEL, "state": state, "images": images_b64,
                       "questions": questions}
            try:
                async with httpx.AsyncClient(timeout=settings.SYSTEM_ONE_TIMEOUT) as client:
                    r = await client.post(settings.SYSTEM_ONE_URL, json=payload)
                    r.raise_for_status()
                    return r.json()["answers"]
            except (httpx.HTTPError, KeyError, ValueError) as e:
                logger.warning(f"System One 호출 실패: {e!r}")
                raise SystemOneError(str(e)) from e
    finally:
        _waiting -= 1


def top2(answer: dict) -> tuple[str, float, str | None, float]:
    probs = sorted(answer["probabilities"].items(), key=lambda kv: -kv[1])
    k1, p1 = probs[0]
    k2, p2 = probs[1] if len(probs) > 1 else (None, 0.0)
    return k1, p1, k2, p2
