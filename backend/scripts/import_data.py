"""data/ → MariaDB (regions, zones, places). 여러 번 실행해도 결과가 같다.

- 전국 행정동: data/kr_dongs.csv (없으면 data/jeonju_dongs.csv)
- 전주 추가 정보: jeonju_dongs.csv 의 인접 동, dump_schedule.md 의 배출 요일, zones.csv 의 시연 권역
- 수거장: data/kr_places.csv.gz (없으면 data/jeonju_places.csv)
- 데이터 파일이 바뀌지 않았으면 건너뛴다 (--force 로 강제)

사용: python -m scripts.import_data [--data ../data] [--force]
"""
import argparse
import asyncio
import csv
import gzip
import hashlib
import io
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.dialects.mysql import insert as mysql_insert  # noqa: E402

from app.database.session import AsyncSessionLocal  # noqa: E402
from app.models import JobLog, Place, Region, Zone  # noqa: E402

CHUNK = 2000


def dump_weekdays(schedule_md: Path) -> dict[str, str]:
    """dump_schedule.md 표에서 code → '0,2' 같은 요일 문자열."""
    out: dict[str, str] = {}
    if not schedule_md.exists():
        return out
    for line in schedule_md.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(\d{10})\s*\|[^|]*\|[^|]*\|[^|]*\|\s*([0-6](?:,[0-6])*)?\s*\|", line)
        if m:
            out[m.group(1)] = m.group(2) or ""
    return out


def read_csv(path: Path) -> list[dict]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def files_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        if p.exists():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:20]


async def main(data_dir: Path, force: bool) -> None:
    kr_dongs = data_dir / "kr_dongs.csv"
    jj_dongs = data_dir / "jeonju_dongs.csv"
    kr_places = data_dir / "kr_places.csv.gz"
    jj_places = data_dir / "jeonju_places.csv"
    zones_csv = data_dir / "zones.csv"
    sched = data_dir / "dump_schedule.md"
    dongs_file = kr_dongs if kr_dongs.exists() else jj_dongs
    places_file = kr_places if kr_places.exists() else jj_places
    key = files_hash([dongs_file, jj_dongs, places_file, zones_csv, sched])

    async with AsyncSessionLocal() as db:
        if not force and await db.get(JobLog, ("import_data", key)):
            print(f"데이터 변경 없음 (hash {key}), 건너뜀")
            return

    dongs = read_csv(dongs_file)
    jj = {r["code"]: r for r in read_csv(jj_dongs)} if jj_dongs.exists() else {}
    zones = read_csv(zones_csv) if zones_csv.exists() else []
    weekdays = dump_weekdays(sched)
    zone_of = {n: int(z["zone_id"]) for z in zones for n in z["dong_names"].split(";")}

    def region_row(d: dict) -> dict:
        code = d["code"]
        extra = jj.get(code, {})
        is_jj = code in jj
        sido = d.get("sido") or ("전북특별자치도" if is_jj else "")
        gu = d.get("sigungu") or d.get("gu") or ""
        if is_jj and not gu.startswith("전주시"):
            gu = f"전주시 {gu}"
        return dict(code=code, name=d["name"], gu=gu, sido=sido,
                    sigungu_code=d.get("sigungu_code") or code[:5],
                    population=int(d["population"]) if d.get("population") else None,
                    center_lat=float(d["center_lat"]), center_lng=float(d["center_lng"]),
                    neighbors=extra.get("neighbors", d.get("neighbors", "")) or "",
                    zone_id=zone_of.get(d["name"]) if is_jj else None,
                    dump_weekdays=weekdays.get(code, ""))

    async with AsyncSessionLocal() as db:
        for z in zones:
            stmt = mysql_insert(Zone).values(id=int(z["zone_id"]), name=z["zone_name"])
            await db.execute(stmt.on_duplicate_key_update(name=stmt.inserted.name))
        rows = [region_row(d) for d in dongs]
        for i in range(0, len(rows), CHUNK):
            stmt = mysql_insert(Region).values(rows[i:i + CHUNK])
            await db.execute(stmt.on_duplicate_key_update(
                {c: stmt.inserted[c] for c in rows[0] if c != "code"}))
        await db.commit()
        print(f"zones {len(zones)}, regions {len(rows)}")

        valid_codes = {r["code"] for r in rows}
        places = read_csv(places_file)
        seen: set[tuple[str, str]] = set()
        batch: list[dict] = []
        n = 0
        for r in places:
            k = (r["source"], r["source_id"])
            if k in seen:
                continue
            seen.add(k)
            batch.append(dict(source=r["source"][:20], source_id=r["source_id"][:40], kind=r["kind"][:20],
                              name=(r["name"] or "")[:120], address=(r["address"] or "")[:200],
                              detail=(r["detail"] or "")[:200], lat=float(r["lat"]), lng=float(r["lng"]),
                              hours=(r["hours"] or "")[:80], items=(r["items"] or "")[:200],
                              region_code=r["dong_code"] if r.get("dong_code") in valid_codes else None,
                              is_active=r["is_active"] == "1"))
            if len(batch) >= CHUNK:
                n += await _upsert_places(db, batch)
                batch = []
        if batch:
            n += await _upsert_places(db, batch)
        # 원본에서 사라진 수거장은 지우지 않고 비활성 (인증 기록이 참조할 수 있음)
        existing = (await db.execute(select(Place.id, Place.source, Place.source_id))).all()
        gone = [pid for pid, s, sid in existing if (s, sid) not in seen]
        for i in range(0, len(gone), CHUNK):
            await db.execute(update(Place).where(Place.id.in_(gone[i:i + CHUNK])).values(is_active=False))
        await db.execute(mysql_insert(JobLog).values(name="import_data", key=key).prefix_with("IGNORE"))
        await db.commit()
    print(f"places {n} (원본에서 사라져 비활성 {len(gone)})")


async def _upsert_places(db, batch: list[dict]) -> int:
    stmt = mysql_insert(Place).values(batch)
    cols = [c for c in batch[0] if c not in ("source", "source_id")]
    # stmt.inserted.items 는 메서드라서 열 이름은 [] 로 꺼낸다
    await db.execute(stmt.on_duplicate_key_update({c: stmt.inserted[c] for c in cols}))
    return len(batch)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[2] / "data"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(Path(a.data), a.force))
    _ = io
