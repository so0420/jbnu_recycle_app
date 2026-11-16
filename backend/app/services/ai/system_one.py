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


QUEUE_WAIT = 25.0


def _validate(questions: dict, answers: dict) -> dict:
    """요청한 질문마다 기대한 형태의 답이 있는지 확인. 아니면 SystemOneError."""
    for key, q in questions.items():
        a = answers.get(key)
        if not isinstance(a, dict):
            raise SystemOneError(f"답 없음: {key}")
        if q["type"] == "choice":
            probs = a.get("probabilities")
            if not isinstance(probs, dict) or not probs or a.get("choice") not in q["criteria"]:
                raise SystemOneError(f"choice 형식 오류: {key}")
            if any(k not in q["criteria"] for k in probs):
                raise SystemOneError(f"알 수 없는 선택지: {key}")
        elif q["type"] == "noul":
            if not isinstance(a.get("noul"), (int, float)):
                raise SystemOneError(f"noul 형식 오류: {key}")
    return answers


async def ask(state: str, images_b64: list[str], questions: dict) -> dict:
    """questions 예: {"category": {"type": "choice", "instructions": ..., "criteria": {...}},
    "dirty": {"type": "noul", "instructions": ...}}
    반환: answers dict (key → {"choice","probabilities",...} 또는 {"noul": p})"""
    global _waiting
    if _waiting >= MAX_QUEUE:
        raise SystemOneBusy()
    _waiting += 1
    try:
        try:
            await asyncio.wait_for(_sem.acquire(), timeout=QUEUE_WAIT)
        except asyncio.TimeoutError as e:
            raise SystemOneBusy() from e
        try:
            payload = {"model": settings.SYSTEM_ONE_MODEL, "state": state, "images": images_b64,
                       "questions": questions}
            try:
                async with httpx.AsyncClient(timeout=settings.SYSTEM_ONE_TIMEOUT) as client:
                    r = await client.post(settings.SYSTEM_ONE_URL, json=payload)
                    r.raise_for_status()
                    return _validate(questions, r.json()["answers"])
            except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
                logger.warning(f"System One 호출 실패: {e!r}")
                raise SystemOneError(str(e)) from e
        finally:
            _sem.release()
    finally:
        _waiting -= 1


def top2(answer: dict) -> tuple[str, float, str | None, float]:
    probs = sorted(answer["probabilities"].items(), key=lambda kv: -kv[1])
    k1, p1 = probs[0]
    k2, p2 = probs[1] if len(probs) > 1 else (None, 0.0)
    return k1, p1, k2, p2
