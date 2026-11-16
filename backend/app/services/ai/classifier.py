"""분류 파이프라인: 1차 System One → (애매하면) 2차 OpenAI → (그래도 모르면) 사용자 선택."""
import time
from dataclasses import asdict, dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.ai import openai_fallback, system_one
from app.services.game import data

STATE_ITEM = "A photo of a single household waste item, taken by a user in Korea before throwing it away."
STATE_VERIFY = "A photo taken by a user in Korea at a neighborhood recycling collection point."


@dataclass
class ClassifyResult:
    category: str | None
    item_label: str | None
    clean: bool | None
    habit_ok: bool | None
    judged_by: str                      # system_one | openai | none
    confidence: float
    candidates: list[str] = field(default_factory=list)
    s1: dict | None = None
    s2: dict | None = None
    latency_ms: int = 0

    @property
    def needs_user_choice(self) -> bool:
        return self.category is None

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("s1"); d.pop("s2")
        return d


def _category_question() -> dict:
    cats = data.guides()["categories"]
    return {"type": "choice", "instructions": "Which recycling category does the main item in the photo belong to?",
            "criteria": {k: v["en"] for k, v in cats.items()}}


def _items_of(category: str) -> list[dict]:
    return [it for it in data.guides()["items"] if it["category"] == category]


def _habit_q(type_: str) -> str | None:
    h = data.guides()["habits"].get(type_)
    return h["q"] if h else None


async def classify(db: AsyncSession, image_b64: str) -> ClassifyResult:
    t0 = time.perf_counter()
    g = data.guides()
    res = ClassifyResult(None, None, None, None, "none", 0.0)

    # ── 1차: 분류 + 오염 여부 ──
    s1: dict = {}
    try:
        s1 = await system_one.ask(STATE_ITEM, [image_b64], {
            "category": _category_question(),
            "dirty": {"type": "noul", "instructions": g["clean_question"]},
        })
        k1, p1, k2, p2 = system_one.top2(s1["category"])
        probs = sorted(s1["category"]["probabilities"].items(), key=lambda kv: -kv[1])
        res.candidates = [k for k, _ in probs[:3]]
        res.confidence = p1
        if p1 >= settings.AI_TOP1_THRESHOLD and (p1 - p2) >= settings.AI_MARGIN_THRESHOLD:
            res.category = k1
            res.judged_by = "system_one"
            res.clean = s1["dirty"]["noul"] < 0.5
    except (system_one.SystemOneBusy, system_one.SystemOneError):
        res.candidates = []
    res.s1 = s1 or None

    # ── 1차 확정이면 세부 품목 + 습관 질문 ──
    if res.category:
        type_ = data.category_type(res.category)
        qs: dict = {}
        items = _items_of(res.category)
        if len(items) > 1:
            qs["item"] = {"type": "choice", "instructions": "Which specific item is it?",
                          "criteria": {it["label"]: it["name"] for it in items}}
        hq = _habit_q(type_)
        if hq:
            qs["habit"] = {"type": "noul", "instructions": hq}
        if qs:
            try:
                s1b = await system_one.ask(STATE_ITEM, [image_b64], qs)
                if "item" in s1b:
                    res.item_label = s1b["item"]["choice"]
                if "habit" in s1b:
                    res.habit_ok = s1b["habit"]["noul"] >= 0.6
                res.s1 = {**(res.s1 or {}), **s1b}
            except (system_one.SystemOneBusy, system_one.SystemOneError):
                pass
        if res.item_label is None and len(items) == 1:
            res.item_label = items[0]["label"]

    # ── 2차: OpenAI ──
    if res.category is None:
        cats = g["categories"]
        items = data.guides()["items"]
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["category", "item_label", "is_dirty", "good_habit", "confidence"],
            "properties": {
                "category": {"type": "string", "enum": list(cats)},
                "item_label": {"type": "string", "enum": [it["label"] for it in items] + ["unknown"]},
                "is_dirty": {"type": "boolean"},
                "good_habit": {"type": "boolean"},
                "confidence": {"type": "number"},
            },
        }
        cand = ", ".join(res.candidates) if res.candidates else "none"
        prompt = (
            "You classify a household waste item photo for Korean recycling rules.\n"
            f"Categories: {', '.join(f'{k} = {v['en']}' for k, v in cats.items())}.\n"
            f"Items: {', '.join(f'{it['label']} ({it['category']})' for it in items)}.\n"
            f"A smaller model's top guesses were: {cand}.\n"
            "good_habit = the item is prepared correctly for recycling (emptied, rinsed, label/cap/tape removed as applicable).\n"
            "confidence is 0..1."
        )
        try:
            s2 = await openai_fallback.ask_json(db, prompt, image_b64, schema, "waste_classification")
            res.s2 = s2
            if s2.get("confidence", 0) >= 0.5:
                res.category = s2["category"]
                res.item_label = s2["item_label"] if s2["item_label"] != "unknown" else None
                if res.item_label and data.items_by_label().get(res.item_label, {}).get("category") != res.category:
                    res.item_label = None
                res.clean = not s2["is_dirty"]
                res.habit_ok = bool(s2["good_habit"])
                res.judged_by = "openai"
                res.confidence = float(s2["confidence"])
        except openai_fallback.OpenAIUnavailable:
            pass

    res.latency_ms = int((time.perf_counter() - t0) * 1000)
    return res


@dataclass
class VerifyJudge:
    passed: bool
    score: float | None
    judged_by: str
    uncertain: bool
    unavailable: bool = False      # 두 AI 모두 판단하지 못함 → 다시 시도하게 한다

    @classmethod
    def busy(cls) -> "VerifyJudge":
        return cls(False, None, "none", False, unavailable=True)


async def judge_disposal(db: AsyncSession, image_b64: str) -> VerifyJudge:
    """수거장에서 분리배출하는 사진인지 판정."""
    q = ("Does this photo show recyclables or sorted waste being put into, or placed at, a recycling collection "
         "point, separate collection bins, a clothing collection box or a sorting area?")
    score: float | None = None
    try:
        ans = await system_one.ask(STATE_VERIFY, [image_b64], {"ok": {"type": "noul", "instructions": q}})
        score = float(ans["ok"]["noul"])
        if score >= 0.7:
            return VerifyJudge(True, score, "system_one", False)
        if score < 0.4:
            return VerifyJudge(False, score, "system_one", False)
    except (system_one.SystemOneBusy, system_one.SystemOneError):
        pass
    schema = {"type": "object", "additionalProperties": False, "required": ["is_disposal_photo", "confidence"],
              "properties": {"is_disposal_photo": {"type": "boolean"}, "confidence": {"type": "number"}}}
    try:
        s2 = await openai_fallback.ask_json(db, q + " Answer for a photo taken in Korea. confidence is 0..1.",
                                            image_b64, schema, "disposal_check")
        conf = float(s2.get("confidence", 0))
        passed = bool(s2["is_disposal_photo"]) and conf >= 0.6
        # 1차가 애매했고 2차로 통과한 것은 관리자 검토 대상으로 표시
        return VerifyJudge(passed, score, "openai", passed and (score is not None or conf < 0.8))
    except openai_fallback.OpenAIUnavailable:
        return VerifyJudge(False, score, "none", False, unavailable=True)
