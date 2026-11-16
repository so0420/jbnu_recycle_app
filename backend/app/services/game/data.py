"""game_data/*.yaml 로더. 숫자는 코드에 넣지 않고 여기서 읽는다."""
from functools import lru_cache
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parents[2] / "game_data"


def _load(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def species() -> dict:
    return _load("species.yaml")


@lru_cache
def bosses() -> dict:
    return _load("bosses.yaml")


@lru_cache
def economy() -> dict:
    return _load("economy.yaml")


@lru_cache
def guides() -> dict:
    return _load("guides.yaml")


def reload_all() -> None:
    for fn in (species, bosses, economy, guides):
        fn.cache_clear()


def line(line_id: str) -> dict:
    return species()["lines"][line_id]


def category_type(category: str) -> str:
    return guides()["categories"][category]["type"]


def items_by_label() -> dict[str, dict]:
    return {it["label"]: it for it in guides()["items"]}


MATERIALS = ["plastic", "paper", "metal", "glass", "vinyl", "volt", "fabric"]
BASE_TYPES = ["plastic", "paper", "metal", "glass", "vinyl"]
