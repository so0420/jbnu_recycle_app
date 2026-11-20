"""분류 파이프라인: OpenAI 가 판정 → (확신이 없으면) 사용자 선택."""
import time
from dataclasses import asdict, dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai import openai_api
from app.services.game import data

STATE_ITEM = "A photo of a single household waste item, taken by a user in Korea before throwing it away."
STATE_VERIFY = "A photo taken by a user in Korea at a neighborhood recycling collection point."
MIN_CONFIDENCE = 0.5


@dataclass
class ClassifyResult:
    category: str | None
    item_label: str | None
    clean: bool | None
    habit_ok: bool | None
    judged_by: str                      # openai | none
    confidence: float
    candidates: list[str] = field(default_factory=list)
    name: str | None = None             # AI 가 본 물건 이름 (한국어, 등록된 품목이 아니어도)
    raw: dict | None = None             # OpenAI 답 그대로 (None 이면 판정하지 못함)
    latency_ms: int = 0

    @property
    def needs_user_choice(self) -> bool:
        return self.category is None

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw")
        return d


def _classify_prompt() -> tuple[str, dict]:
    g = data.guides()
    cats, items, habits = g["categories"], g["items"], g["habits"]
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["name", "category", "item_label", "is_dirty", "good_habit", "confidence"],
        "properties": {
            "name": {"type": "string"},
            "category": {"type": "string", "enum": list(cats)},
            "item_label": {"type": "string", "enum": [it["label"] for it in items] + ["unknown"]},
            "is_dirty": {"type": "boolean"},
            "good_habit": {"type": "boolean"},
            "confidence": {"type": "number"},
        },
    }
    habit_lines = []
    for k, v in cats.items():
        h = habits.get(v["type"])
        habit_lines.append(f"  {k}: {h['q'] if h else 'always false (not recyclable)'}")
    prompt = "\n".join([
        STATE_ITEM,
        "Classify the main item in the photo for Korean recycling rules.",
        'name: what the main item is, as a short Korean noun phrase (e.g. "검은 우산", "무선 마우스", "생수병").',
        "Categories: " + "; ".join(f"{k} = {v['en']}" for k, v in cats.items()) + ".",
        "Items (label (category)): " + ", ".join(f"{it['label']} ({it['category']})" for it in items) + ".",
        "item_label must belong to the chosen category; use unknown if none fits.",
        f"is_dirty: {g['clean_question']}",
        "good_habit: answer yes/no to the check for the chosen category:",
        *habit_lines,
        "confidence is 0..1: how sure you are about the category.",
    ])
    return prompt, schema


async def classify(db: AsyncSession, image_b64: str) -> ClassifyResult:
    t0 = time.perf_counter()
    res = ClassifyResult(None, None, None, None, "none", 0.0)
    prompt, schema = _classify_prompt()
    try:
        ans = await openai_api.ask_json(db, prompt, image_b64, schema, "waste_classification")
    except openai_api.OpenAIUnavailable:
        ans = None
    res.raw = ans
    if ans is not None:
        cats = data.guides()["categories"]
        guess = ans.get("category")
        res.confidence = float(ans.get("confidence", 0) or 0)
        if isinstance(ans.get("name"), str) and ans["name"].strip():
            res.name = ans["name"].strip()[:40]
        if guess in cats:
            res.candidates = [guess]
        if guess in cats and res.confidence >= MIN_CONFIDENCE:
            res.category = guess
            res.judged_by = "openai"
            res.clean = not ans["is_dirty"]
            res.habit_ok = bool(ans["good_habit"])
            label = ans.get("item_label")
            item = data.items_by_label().get(label or "")
            if item and item["category"] == guess:
                res.item_label = label
            else:
                same = [it for it in data.guides()["items"] if it["category"] == guess]
                res.item_label = same[0]["label"] if len(same) == 1 else None
    res.latency_ms = int((time.perf_counter() - t0) * 1000)
    return res


@dataclass
class VerifyJudge:
    passed: bool
    score: float | None             # 분리배출 사진일 확률 (0..1)
    judged_by: str
    uncertain: bool
    unavailable: bool = False      # AI 가 판단하지 못함 → 다시 시도하게 한다

    @classmethod
    def busy(cls) -> "VerifyJudge":
        return cls(False, None, "none", False, unavailable=True)


async def judge_disposal(db: AsyncSession, image_b64: str) -> VerifyJudge:
    """수거장에서 분리배출하는 사진인지 판정."""
    q = ("Does this photo show recyclables or sorted waste being put into, or placed at, a recycling collection "
         "point, separate collection bins, a clothing collection box or a sorting area?")
    schema = {"type": "object", "additionalProperties": False, "required": ["is_disposal_photo", "confidence"],
              "properties": {"is_disposal_photo": {"type": "boolean"}, "confidence": {"type": "number"}}}
    try:
        ans = await openai_api.ask_json(db, f"{STATE_VERIFY}\n{q}\nconfidence is 0..1: how sure you are.",
                                        image_b64, schema, "disposal_check")
    except openai_api.OpenAIUnavailable:
        return VerifyJudge.busy()
    conf = min(1.0, max(0.0, float(ans.get("confidence", 0) or 0)))
    yes = bool(ans.get("is_disposal_photo"))
    passed = yes and conf >= 0.6
    # 통과했지만 확신이 낮은 것은 관리자 검토 대상으로 표시
    return VerifyJudge(passed, conf if yes else 1 - conf, "openai", passed and conf < 0.8)
