"""1차 판정: 로컬 멀티모달 LLM (Ollama /api/chat).

질문마다 선택지를 글자(A, B, …)나 yes/no 로 답하게 하고, 답 토큰의 logprobs 로 선택지별 확률을 만든다.
(모델이 스스로 적는 '확신도'는 늘 0.9 근처라 믿기 어렵다.) 반환 형식은 예전 System One 과 같다:
choice → {"choice", "probabilities"}, noul → {"noul": P(yes)}
"""
import asyncio
import json
import math
import re
import string

import httpx

from app.core.config import settings
from app.utils.log import logger

# 로컬 모델은 한 번에 하나씩만 처리 (메모리·속도 안정)
_sem = asyncio.Semaphore(1)
_waiting = 0
MAX_QUEUE = 4
QUEUE_WAIT = 25.0
LETTERS = string.ascii_uppercase


class SystemOneBusy(Exception):
    pass


class SystemOneError(Exception):
    pass


def base_url() -> str:
    """설정값이 예전 형식(…/v1/systemone)이어도 Ollama 주소만 쓴다."""
    return settings.SYSTEM_ONE_URL.split("/v1/")[0].split("/api/")[0].rstrip("/")


def _prompt(state: str, questions: dict) -> tuple[str, dict]:
    """질문 목록 → (프롬프트, JSON 스키마)."""
    lines = [state, "", "Look at the image carefully, then answer every question.",
             "First write in \"seen\" what the main object is (material, shape, any label), in under 15 words.", ""]
    props: dict = {"seen": {"type": "string"}}
    for key, q in questions.items():
        if q["type"] == "choice":
            opts = list(q["criteria"].items())
            lines.append(f'"{key}": {q["instructions"]} Answer with one letter.')
            for i, (_, desc) in enumerate(opts):
                lines.append(f"  {LETTERS[i]} = {desc}")
            props[key] = {"type": "string", "enum": [LETTERS[i] for i in range(len(opts))]}
        else:
            lines.append(f'"{key}": {q["instructions"]} Answer yes or no.')
            props[key] = {"type": "string", "enum": ["yes", "no"]}
        lines.append("")
    schema = {"type": "object", "properties": props, "required": list(props)}
    return "\n".join(lines), schema


def _answer_dists(content: str, logprobs: list[dict] | None, keys: list[str]) -> dict[str, dict[str, float]]:
    """답 값의 첫 토큰 위치에서 대안 토큰들의 확률을 모은다. 실패하면 그 키는 빠진다."""
    if not logprobs:
        return {}
    spans, pos = [], 0
    for t in logprobs:
        tok = t.get("token", "")
        spans.append((pos, pos + len(tok), t))
        pos += len(tok)
    text = "".join(t.get("token", "") for t in logprobs)
    if text != content:          # 토큰을 이어 붙인 결과가 본문과 다르면 위치를 믿을 수 없다
        return {}
    out: dict[str, dict[str, float]] = {}
    for key in keys:
        m = re.search(r'"' + re.escape(key) + r'"\s*:\s*"', content)
        if not m:
            continue
        at = m.end()                                   # 값의 첫 글자 위치
        for s, e, t in spans:
            if s <= at < e:
                prefix = content[s:at]                 # 같은 토큰에 붙어 있는 따옴표 등
                dist: dict[str, float] = {}
                for alt in t.get("top_logprobs") or [{"token": t["token"], "logprob": t.get("logprob", 0.0)}]:
                    a = alt.get("token", "")
                    if not a.startswith(prefix):
                        continue
                    v = a[len(prefix):].strip().strip('"').lower()
                    if v:
                        dist[v] = dist.get(v, 0.0) + math.exp(alt.get("logprob", -99.0))
                out[key] = dist
                break
    return out


def _to_answers(questions: dict, parsed: dict, dists: dict) -> dict:
    answers: dict = {}
    for key, q in questions.items():
        val = parsed.get(key)
        d = dists.get(key, {})
        if q["type"] == "choice":
            keys = list(q["criteria"])
            letters = {LETTERS[i].lower(): k for i, k in enumerate(keys)}
            if not isinstance(val, str) or val.lower() not in letters:
                raise SystemOneError(f"choice 형식 오류: {key}")
            mass = {letters[v]: p for v, p in d.items() if v in letters}
            total = sum(mass.values())
            if total > 0:
                probs = {k: mass.get(k, 0.0) / total for k in keys}
            else:                                      # logprobs 를 못 받으면 애매한 것으로 보고 2차에 넘긴다
                probs = {k: (0.55 if k == letters[val.lower()] else 0.45 / max(1, len(keys) - 1)) for k in keys}
            choice = max(probs, key=probs.get)
            answers[key] = {"choice": choice, "probabilities": probs}
        else:
            if val not in ("yes", "no"):
                raise SystemOneError(f"noul 형식 오류: {key}")
            y = sum(p for v, p in d.items() if "yes".startswith(v))
            n = sum(p for v, p in d.items() if "no".startswith(v))
            answers[key] = {"noul": y / (y + n) if y + n > 0 else (0.75 if val == "yes" else 0.25)}
    return answers


async def _chat(state: str, images_b64: list[str], questions: dict) -> dict:
    prompt, schema = _prompt(state, questions)
    payload = {
        "model": settings.SYSTEM_ONE_MODEL,
        "messages": [{"role": "user", "content": prompt, "images": images_b64}],
        "format": schema, "stream": False, "think": False,
        "logprobs": True, "top_logprobs": 10,
        "options": {"temperature": 0, "num_predict": 160},
    }
    async with httpx.AsyncClient(timeout=settings.SYSTEM_ONE_TIMEOUT) as client:
        r = await client.post(base_url() + "/api/chat", json=payload)
        r.raise_for_status()
        body = r.json()
    content = body["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise SystemOneError("답이 JSON 객체가 아님")
    dists = _answer_dists(content, body.get("logprobs"), list(questions))
    ans = _to_answers(questions, parsed, dists)
    if isinstance(parsed.get("seen"), str):
        ans["_seen"] = parsed["seen"][:200]
    return ans


async def ask(state: str, images_b64: list[str], questions: dict) -> dict:
    """questions 예: {"category": {"type": "choice", "instructions": ..., "criteria": {...}},
    "dirty": {"type": "noul", "instructions": ...}}
    반환: answers dict (key → {"choice","probabilities"} 또는 {"noul": p}), "_seen" 에 모델이 본 물건 설명"""
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
            return await _chat(state, images_b64, questions)
        except SystemOneError as e:
            logger.warning(f"로컬 AI 답 형식 오류: {e}")
            raise
        except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"로컬 AI 호출 실패: {e!r}")
            raise SystemOneError(str(e)) from e
        finally:
            _sem.release()
    finally:
        _waiting -= 1


async def warm_up() -> None:
    """모델을 메모리에 올린다 (빈 프롬프트 요청)."""
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(base_url() + "/api/generate", json={"model": settings.SYSTEM_ONE_MODEL, "keep_alive": -1})
        r.raise_for_status()


def top2(answer: dict) -> tuple[str, float, str | None, float]:
    probs = sorted(answer["probabilities"].items(), key=lambda kv: -kv[1])
    k1, p1 = probs[0]
    k2, p2 = probs[1] if len(probs) > 1 else (None, 0.0)
    return k1, p1, k2, p2
