"""전주시 수거장소·행정동 데이터 생성 스크립트.

입력(모두 CLI 인자로 경로 지정):
  --tonghap     통합본.csv (분리의정석 전국 + 전주시 생활지리정보 병합본)
  --jeonju      전주시_생활지리정보_원본.csv (재활용품 분리배출장소 원본, 좌표 보정용)
  --geojson     vuski/admdongkor HangJeongDong_verYYYYMMDD.geojson (전국 행정동 경계)
  --population  행정안전부 주민등록 인구 및 세대현황 CSV (선택, 전주시 '현재화면' 다운로드)
  --out         출력 폴더 (예: data/)

출력:
  jeonju_places.csv, jeonju_dongs.geojson, jeonju_dongs.csv

인구 CSV 받는 법 (jumin.mois.go.kr, 2026-11-16 기준 동작 확인):
  curl -c cj.txt https://jumin.mois.go.kr/statMonth.do -o /dev/null
  curl -b cj.txt -X POST -o pop.csv \
    "https://jumin.mois.go.kr/downloadCsv.do?searchYearMonth=month&xlsStats=1" \
    --data "sltOrgType=2&sltOrgLvl1=5200000000&sltOrgLvl2=5211000000&gender=gender&genderPer=genderPer&generation=generation&sltUndefType=&searchYearStart=2026&searchMonthStart=10&searchYearEnd=2026&searchMonthEnd=10&sltOrderType=1&sltOrderValue=ASC&category=month&state=1"
  (CP949 인코딩, 행정구역 열이 '전북특별자치도 전주시 완산구 중앙동 (5211151000)' 형태)

사용 예:
  python scripts/build_data.py --tonghap 통합본.csv --jeonju 전주시_생활지리정보_원본.csv \
      --geojson HangJeongDong_ver20261001.geojson --population pop.csv --out data
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from shapely import STRtree
from shapely.geometry import Point, mapping, shape

# 전주시 시군구 코드: 전북특별자치도(2024~) 52111/52113, 이전 전라북도 45111/45113
JEONJU_SGG = {"52111": "완산구", "52113": "덕진구", "45111": "완산구", "45113": "덕진구"}

KIND_BY_GUBUN = {
    "재활용품 분리배출장소": "recycle_point",
    "의류 수거함": "clothes_bin",
    "종량제봉투 판매소": "bag_shop",
    "무인회수기": "reverse_vending",
    # 분리의정석 '폐가전 수거함'(중소형 수거함)의 배출품목은 전부 '건전지,소형전자제품'
    "폐가전 수거함": "battery_bin",
    "폐건전지 수거함": "battery_bin",
    "폐형광등 수거함": "battery_bin",
}
INACTIVE_RE = re.compile(r"미사용|사용\s*안\s*함|사용중지|폐쇄|철거")
# 전주시 경계(대략) 밖 좌표는 오류로 본다
LAT_RANGE = (35.70, 35.95)
LNG_RANGE = (126.95, 127.25)

PLACE_COLS = ["source", "source_id", "kind", "name", "address", "detail", "lat", "lng",
              "hours", "items", "dong_code", "dong_name", "gu", "is_active", "note"]


def read_csv_any(path: str, **kw) -> pd.DataFrame:
    """UTF-8(BOM 포함) 우선, 실패하면 CP949로 읽는다."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc, low_memory=False, **kw)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"인코딩을 알 수 없음: {path}")


def clean(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def dedup_repeat(s: str) -> str:
    """'언제나 가능언제나 가능' 처럼 같은 문자열이 두 번 붙은 값을 정리."""
    n = len(s)
    if n and n % 2 == 0 and s[: n // 2] == s[n // 2:]:
        return s[: n // 2]
    return s


# ---------------------------------------------------------------- 행정동 경계
def load_dongs(geojson_path: str):
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    dongs = []
    for ft in gj["features"]:
        p = ft["properties"]
        sgg = str(p.get("sgg", ""))
        if sgg not in JEONJU_SGG:
            continue
        geom = shape(ft["geometry"])
        if not geom.is_valid:
            geom = geom.buffer(0)
        dongs.append({
            "code": str(p["adm_cd2"]),
            "name": p["adm_nm"].split()[-1],
            "gu": JEONJU_SGG[sgg],
            "geom": geom,
        })
    if not dongs:
        raise SystemExit("geojson 에서 전주시(sgg 52111/52113/45111/45113) 행정동을 찾지 못함")
    dongs.sort(key=lambda d: d["code"])
    return dongs


def simplify_geojson(dongs, tolerance: float, precision: int) -> dict:
    feats = []
    for d in dongs:
        g = d["geom"].simplify(tolerance, preserve_topology=True)
        gm = mapping(g)
        gm = json.loads(json.dumps(gm), parse_float=lambda x: round(float(x), precision))
        feats.append({"type": "Feature",
                      "properties": {"code": d["code"], "name": d["name"], "gu": d["gu"]},
                      "geometry": gm})
    return {"type": "FeatureCollection", "features": feats}


def neighbors(dongs, buf: float):
    out = {}
    for a in dongs:
        ab = a["geom"].buffer(buf)
        out[a["code"]] = [b["code"] for b in dongs
                          if b["code"] != a["code"] and ab.intersects(b["geom"])
                          and ab.intersection(b["geom"]).area > 0]
    return out


def load_population(path: str | None):
    """행안부 CSV -> {code: population}, 기준월 문자열."""
    if not path:
        return {}, ""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    m = re.match(r"(\d{4})년\s*(\d{1,2})월_총인구수", header[1])
    date = f"{m.group(1)}-{int(m.group(2)):02d}" if m else ""
    pop = {}
    for r in rows[1:]:
        mm = re.search(r"\((\d{10})\)", r[0])
        if mm and r[1].strip():
            pop[mm.group(1)] = int(r[1].replace(",", "").strip())
    return pop, date


# ---------------------------------------------------------------- 장소
def build_places(tonghap_path: str, jeonju_path: str, dongs, stats: Counter):
    df = read_csv_any(tonghap_path)
    is_jj = (df["시군구"].fillna("").str.contains("전주시")
             | df["주소"].fillna("").str.contains("전주시"))
    df = df[is_jj].copy()
    stats["jeonju_rows_in_tonghap"] = len(df)

    jj = read_csv_any(jeonju_path).set_index("ID")

    def jj_coord(jid: str):
        for i in clean(jid).split(","):
            i = i.strip()
            if i in jj.index:
                lat = pd.to_numeric(jj.at[i, "위도"], errors="coerce")
                lng = pd.to_numeric(jj.at[i, "경도"], errors="coerce")
                if pd.notna(lat) and pd.notna(lng):
                    return float(lat), float(lng)
        return None

    # 같은 종류·같은 원본 좌표 = 중복 의심 (판매소는 같은 건물 다른 가게가 많아 제외)
    src_key = df["구분"].fillna("") + "|" + df["위도"].fillna("") + "|" + df["경도"].fillna("")
    dup_groups = {}
    for idx, key in src_key.items():
        if df.at[idx, "위도"] is not None and pd.notna(df.at[idx, "위도"]) \
                and df.at[idx, "구분"] != "종량제봉투 판매소":
            dup_groups.setdefault(key, []).append(clean(df.at[idx, "ID"]))

    tree = STRtree([d["geom"] for d in dongs])

    def dong_at(lat, lng):
        if pd.isna(lat) or pd.isna(lng):
            return None
        hit = tree.query(Point(float(lng), float(lat)), predicate="intersects")
        return dongs[hit[0]] if len(hit) else None

    def jj_dong_name(jid: str) -> str:
        i = clean(jid).split(",")[0].strip()
        return clean(jj.at[i, "행정동"]) if i in jj.index else ""

    rows = []
    for _, r in df.iterrows():
        gubun = clean(r["구분"])
        kind = KIND_BY_GUBUN.get(gubun, "other")
        notes = []
        jid = clean(r.get("전주_ID"))

        lat = pd.to_numeric(r["위도"], errors="coerce")
        lng = pd.to_numeric(r["경도"], errors="coerce")
        coord_src = "분리의정석"
        if jid:
            c = jj_coord(jid)
            if c:
                # 전주시 원본(현장 조사) 좌표 우선. 단, 전주시 좌표는 전주시가 적은 행정동 밖에
                # 떨어지고 분리의정석 좌표는 그 행정동 안이면 분리의정석 좌표를 쓴다.
                label = jj_dong_name(jid)
                dj, db = dong_at(*c), dong_at(lat, lng)
                if label and db is not None and db["name"] == label \
                        and (dj is None or dj["name"] != label):
                    coord_src = "분리의정석(전주시좌표 행정동 불일치)"
                    stats["coord_kept_bunri"] += 1
                else:
                    lat, lng = c
                    coord_src = "전주시"
        if pd.isna(lat) or pd.isna(lng) or not (LAT_RANGE[0] <= lat <= LAT_RANGE[1]) \
                or not (LNG_RANGE[0] <= lng <= LNG_RANGE[1]):
            stats[f"dropped_no_coord:{gubun}"] += 1
            continue

        # 이름/상세
        detail_raw = clean(r["상세주소"])
        if kind == "bag_shop" and detail_raw:
            name, detail = detail_raw, ""          # 판매소는 상세주소 칸이 가게 이름
        else:
            name, detail = clean(r["장소명"]) or gubun, detail_raw
        loc = clean(r.get("전주_위치설명")).strip("()")
        if loc and loc not in detail:
            detail = f"{detail} / {loc}" if detail else loc

        items = clean(r["배출품목"])
        etc = clean(r["기타품목"])
        if etc and etc != items:
            items = f"{items}; {etc}" if items else etc

        remark = clean(r.get("전주_특이사항"))
        is_active = 0 if INACTIVE_RE.search(remark) else 1

        if kind == "other":
            notes.append(f"원본구분={gubun}/{clean(r['장소명'])}")
        elif gubun == "폐가전 수거함":
            notes.append("원본구분=폐가전 수거함(중소형)")
        elif clean(r["장소명"]) == "빈용기 반환수집소":
            notes.append("원본구분=무인회수기/빈용기 반환수집소")
        if jid:
            notes.append(f"전주시ID={jid}")
        for col, label in [("전주_수거함종류", "수거함종류"), ("전주_칸수", "칸수"),
                           ("전주_CCTV", "CCTV"), ("전주_헌옷수거함", "헌옷수거함"),
                           ("전주_영농폐기물", "영농폐기물"), ("전주_특이사항", "특이사항")]:
            v = clean(r.get(col))
            if v:
                notes.append(f"{label}={v}")
        if jid:
            notes.append("좌표=전주시원본" if coord_src == "전주시" else f"좌표={coord_src}")
        key = f"{gubun}|{clean(r['위도'])}|{clean(r['경도'])}"
        grp = dup_groups.get(key, [])
        if len(grp) > 1:
            others = [g for g in grp if g != clean(r["ID"])]
            notes.append("중복의심(같은좌표 source_id=" + ",".join(others) + ")")
            stats["dup_suspect_rows"] += 1

        # 행정동 point-in-polygon
        d = dong_at(lat, lng)
        if d is not None:
            dcode, dname, gu = d["code"], d["name"], d["gu"]
            if jid and jj_dong_name(jid) and jj_dong_name(jid) != dname:
                notes.append(f"전주시표기행정동={jj_dong_name(jid)}")
                stats["jeonju_label_mismatch"] += 1
        else:
            dcode = dname = gu = ""
            notes.append("행정동경계밖")
            stats["outside_all_dongs"] += 1

        rows.append({
            "source": "bunri+jeonju" if "전주시" in clean(r["출처"]) else "bunri",
            "source_id": clean(r["ID"]),
            "kind": kind,
            "name": name,
            "address": clean(r["주소"]),
            "detail": detail,
            "lat": f"{float(lat):.7f}",
            "lng": f"{float(lng):.7f}",
            "hours": dedup_repeat(clean(r["운영시간"])),
            "items": items,
            "dong_code": dcode,
            "dong_name": dname,
            "gu": gu,
            "is_active": is_active,
            "note": "; ".join(notes),
        })
    return pd.DataFrame(rows, columns=PLACE_COLS)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tonghap", required=True)
    ap.add_argument("--jeonju", required=True)
    ap.add_argument("--geojson", required=True)
    ap.add_argument("--population")
    ap.add_argument("--out", required=True)
    ap.add_argument("--simplify", type=float, default=0.0,
                    help="단순화 허용오차(도). 원본이 이미 일반화돼 있어 기본 0(좌표만 소수 6자리로 반올림, 약 64KB)")
    ap.add_argument("--precision", type=int, default=6)
    ap.add_argument("--neighbor-buffer", type=float, default=0.0001, help="인접 판정 버퍼(도), 약 10m")
    a = ap.parse_args(argv)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stats = Counter()

    dongs = load_dongs(a.geojson)
    pop, pop_date = load_population(a.population)
    nb = neighbors(dongs, a.neighbor_buffer)

    # 1) 행정동 GeoJSON
    gj = simplify_geojson(dongs, a.simplify, a.precision)
    gj_path = out / "jeonju_dongs.geojson"
    with open(gj_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(gj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    # 2) 행정동 CSV
    dong_rows = []
    for d in dongs:
        g = d["geom"]
        c = g.centroid if g.contains(g.centroid) else g.representative_point()
        p = pop.get(d["code"])
        dong_rows.append({
            "code": d["code"], "name": d["name"], "gu": d["gu"],
            "population": "" if p is None else p,
            "population_date": pop_date if p is not None else "",
            "center_lat": f"{c.y:.6f}", "center_lng": f"{c.x:.6f}",
            "neighbors": ";".join(nb[d["code"]]),
        })
    pd.DataFrame(dong_rows).to_csv(out / "jeonju_dongs.csv", index=False, encoding="utf-8", lineterminator="\n")

    # 3) 장소 CSV
    places = build_places(a.tonghap, a.jeonju, dongs, stats)
    places.to_csv(out / "jeonju_places.csv", index=False, encoding="utf-8", lineterminator="\n")

    # 요약
    print(f"행정동 {len(dongs)}개, geojson {gj_path.stat().st_size/1024:.0f} KB")
    missing = [d["name"] for d in dongs if d["code"] not in pop]
    print(f"인구 기준월 {pop_date or '-'}, 합계 {sum(pop.get(d['code'], 0) for d in dongs):,}, 누락 {missing or '없음'}")
    print(f"통합본 전주 행 {stats['jeonju_rows_in_tonghap']}, 출력 {len(places)}")
    for k, v in sorted(stats.items()):
        if k.startswith("dropped"):
            print(f"  제외 {k.split(':', 1)[1]}: {v}")
    print("kind별:", places["kind"].value_counts().to_dict())
    print("is_active=0:", int((places["is_active"] == 0).sum()))
    print("행정동 경계 밖:", stats["outside_all_dongs"], "/ 중복의심 행:", stats["dup_suspect_rows"])
    print("전주시 좌표 대신 분리의정석 좌표 사용:", stats["coord_kept_bunri"],
          "/ PIP 행정동 != 전주시 표기 행정동:", stats["jeonju_label_mismatch"])
    empty = sorted(set(d["name"] for d in dongs) - set(places["dong_name"]))
    print("장소 0개 행정동:", empty or "없음")


if __name__ == "__main__":
    sys.exit(main())
