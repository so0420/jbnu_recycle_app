"""data/*.csv → MariaDB (regions, zones, places). 여러 번 실행해도 결과가 같다.

사용: python -m scripts.import_data [--data ../data]
"""
import argparse
import asyncio
import csv
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import delete, select  # noqa: E402

from app.database.session import AsyncSessionLocal  # noqa: E402
from app.models import Place, Region, Zone  # noqa: E402


def dump_weekdays(schedule_md: Path) -> dict[str, str]:
    """dump_schedule.md 표에서 code → '0,2' 같은 요일 문자열."""
    out: dict[str, str] = {}
    for line in schedule_md.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(\d{10})\s*\|[^|]*\|[^|]*\|[^|]*\|\s*([0-6](?:,[0-6])*)?\s*\|", line)
        if m:
            out[m.group(1)] = m.group(2) or ""
    return out


async def main(data_dir: Path) -> None:
    dongs = list(csv.DictReader(open(data_dir / "jeonju_dongs.csv", encoding="utf-8")))
    zones = list(csv.DictReader(open(data_dir / "zones.csv", encoding="utf-8")))
    places = list(csv.DictReader(open(data_dir / "jeonju_places.csv", encoding="utf-8")))
    weekdays = dump_weekdays(data_dir / "dump_schedule.md")
    zone_of = {n: int(z["zone_id"]) for z in zones for n in z["dong_names"].split(";")}

    async with AsyncSessionLocal() as db:
        for z in zones:
            row = await db.get(Zone, int(z["zone_id"]))
            if row is None:
                db.add(Zone(id=int(z["zone_id"]), name=z["zone_name"]))
            else:
                row.name = z["zone_name"]
        await db.flush()
        for d in dongs:
            row = await db.get(Region, d["code"])
            vals = dict(name=d["name"], gu=d["gu"], population=int(d["population"]) if d["population"] else None,
                        center_lat=float(d["center_lat"]), center_lng=float(d["center_lng"]),
                        neighbors=d["neighbors"], zone_id=zone_of.get(d["name"]),
                        dump_weekdays=weekdays.get(d["code"], ""))
            if row is None:
                db.add(Region(code=d["code"], **vals))
            else:
                for k, v in vals.items():
                    setattr(row, k, v)
        await db.flush()

        existing = {(p.source, p.source_id): p for p in (await db.execute(select(Place))).scalars()}
        seen = set()
        for r in places:
            key = (r["source"], r["source_id"])
            seen.add(key)
            vals = dict(kind=r["kind"], name=r["name"][:120], address=r["address"][:200], detail=r["detail"][:200],
                        lat=float(r["lat"]), lng=float(r["lng"]), hours=r["hours"][:80], items=r["items"][:200],
                        region_code=r["dong_code"] or None, is_active=r["is_active"] == "1")
            if key in existing:
                for k, v in vals.items():
                    setattr(existing[key], k, v)
            else:
                db.add(Place(source=r["source"], source_id=r["source_id"], **vals))
        gone = [p.id for k, p in existing.items() if k not in seen]
        if gone:
            await db.execute(delete(Place).where(Place.id.in_(gone)))
        await db.commit()
    print(f"zones {len(zones)}, regions {len(dongs)}, places {len(places)} (삭제 {len(gone)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parents[2] / "data"))
    asyncio.run(main(Path(ap.parse_args().data)))
