"""수거장소·행정동 데이터 생성 스크립트 (전주시 + 전국).

입력(모두 CLI 인자로 경로 지정):
  --tonghap        통합본.csv (분리의정석 전국 + 전주시 생활지리정보 병합본)
  --jeonju         전주시_생활지리정보_원본.csv (전주 재활용품 분리배출장소 원본, 좌표 보정용)
  --geojson        vuski/admdongkor HangJeongDong_verYYYYMMDD.geojson (전국 행정동 경계)
  --population-kr  행정안전부 주민등록 인구 및 세대현황 CSV, '전체읍면동현황' (전국)
  --population     (선택) 같은 통계의 전주시 '현재화면' CSV. 없으면 --population-kr 을 쓴다.
  --out            출력 폴더 (예: data/)
  --no-national    전국 파일(kr_*)을 만들지 않음

출력:
  전주: jeonju_places.csv, jeonju_dongs.geojson, jeonju_dongs.csv
  전국: kr_dongs.csv, kr_sigungu.csv, kr_places.csv.gz

인구 CSV 받는 법 (jumin.mois.go.kr, 2026-11-16 기준 동작 확인, 결과는 CP949):
  curl -c cj.txt https://jumin.mois.go.kr/statMonth.do -o /dev/null
  # 전국 전체읍면동 (xlsStats=3, state=3)
  curl -b cj.txt -X POST -o kr.csv \
    "https://jumin.mois.go.kr/downloadCsv.do?searchYearMonth=month&xlsStats=3" \
    --data "sltOrgType=1&sltOrgLvl1=A&sltOrgLvl2=A&gender=gender&genderPer=genderPer&generation=generation&sltUndefType=&searchYearStart=2026&searchMonthStart=10&searchYearEnd=2026&searchMonthEnd=10&sltOrderType=1&sltOrderValue=ASC&category=month&state=3"
  # 전주시만 (xlsStats=1, state=1, sltOrgType=2, sltOrgLvl1=5200000000, sltOrgLvl2=5211000000)

사용 예:
  python scripts/build_data.py --tonghap 통합본.csv --jeonju 전주시_생활지리정보_원본.csv \
      --geojson HangJeongDong_ver20261001.geojson --population jeonju.csv --population-kr kr.csv --out data
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from shapely import STRtree
from shapely.geometry import Point, mapping, shape
from shapely.ops import nearest_points, unary_union

# 전주시 시군구 코드: 전북특별자치도(2024~) 52111/52113, 이전 전라북도 45111/45113
JEONJU_SGG = {"52111", "52113", "45111", "45113"}

KIND_BY_GUBUN = {
    "재활용품 분리배출장소": "recycle_point",
    "의류 수거함": "clothes_bin",
    "종량제봉투 판매소": "bag_shop",
    "무인회수기": "reverse_vending",
    "전지 수거함": "battery_bin",
    "형광등 수거함": "battery_bin",
    "폐건전지 수거함": "battery_bin",
    "폐형광등 수거함": "battery_bin",
    # '폐가전 수거함'은 배출품목에 건전지가 있을 때만 battery_bin (kind_of 참고)
}
# 구분이 빈 행은 장소명으로 추정
KIND_BY_PLACENAME = {"의류수거함": "clothes_bin"}

INACTIVE_RE = re.compile(r"미사용|사용\s*안\s*함|사용중지|폐쇄|철거")
JEONJU_BBOX = ((35.70, 35.95), (126.95, 127.25))
KOREA_BBOX = ((33.0, 38.7), (124.5, 132.0))
NEAREST_MAX_M = 2000.0

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


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def sigungu_label(sggnm: str) -> str:
    """'전주시완산구' -> '전주시 완산구' (구가 있는 시). 나머지는 그대로."""
    m = re.match(r"^(\S+?시)(\S+구)$", sggnm)
    return f"{m.group(1)} {m.group(2)}" if m else sggnm


def center_of(geom):
    c = geom.centroid
    return c if geom.contains(c) else geom.representative_point()


# ---------------------------------------------------------------- 행정동 경계
def load_dongs(geojson_path: str, sgg_filter: set[str] | None = None):
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)
    dongs = []
    for ft in gj["features"]:
        p = ft["properties"]
        code = str(p["adm_cd2"])
        sgg = str(p.get("sgg") or code[:5])
        if sgg_filter is not None and sgg not in sgg_filter:
            continue
        geom = shape(ft["geometry"])
        if not geom.is_valid:
            geom = geom.buffer(0)
        label = sigungu_label(p.get("sggnm", ""))
        dongs.append({
            "code": code,
            "name": p["adm_nm"].split()[-1],
            "sido": p.get("sidonm", ""),
            "sido_code": str(p.get("sido") or code[:2]),
            "sigungu": label,
            "sigungu_code": sgg,
            "gu": label.split()[-1] if label else "",   # 전주 파일용: '완산구'
            "geom": geom,
        })
    if not dongs:
        raise SystemExit("geojson 에서 행정동을 찾지 못함 (sgg 필터 확인)")
    dongs.sort(key=lambda d: d["code"])
    return dongs


def simplify_geojson(dongs, tolerance: float, precision: int) -> dict:
    feats = []
    for d in dongs:
        g = d["geom"].simplify(tolerance, preserve_topology=True)  # 0 이어도 중복 꼭짓점은 정리됨
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


class DongIndex:
    """STRtree 기반 point-in-polygon, 경계 밖이면 max_m 이내 최근접 행정동."""

    def __init__(self, dongs, nearest_max_m: float | None = None):
        self.dongs = dongs
        self.tree = STRtree([d["geom"] for d in dongs])
        self.nearest_max_m = nearest_max_m

    def at(self, lat, lng):
        if pd.isna(lat) or pd.isna(lng):
            return None
        hit = self.tree.query(Point(float(lng), float(lat)), predicate="intersects")
        return self.dongs[min(hit)] if len(hit) else None

    def nearest(self, lat, lng):
        """(dong, 거리 m) 또는 (None, None)."""
        if not self.nearest_max_m:
            return None, None
        pt = Point(float(lng), float(lat))
        idx = self.tree.query_nearest(pt, max_distance=self.nearest_max_m / 80000.0)
        best = None
        for i in idx:
            q, _ = nearest_points(self.dongs[i]["geom"], pt)
            dm = haversine_m(lat, lng, q.y, q.x)
            if best is None or dm < best[1]:
                best = (self.dongs[i], dm)
        if best and best[1] <= self.nearest_max_m:
            return best
        return None, None


# ---------------------------------------------------------------- 인구
def read_mois(path: str):
    """행안부 CSV -> ([(code, name, population)], 'YYYY-MM')."""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows = list(csv.reader(io.StringIO(text)))
    m = re.match(r"(\d{4})년\s*(\d{1,2})월_총인구수", rows[0][1])
    date = f"{m.group(1)}-{int(m.group(2)):02d}" if m else ""
    out = []
    for r in rows[1:]:
        mm = re.match(r"(.*)\((\d{10})\)\s*$", r[0])
        if mm and r[1].strip():
            out.append((mm.group(2), re.sub(r"\s+", " ", mm.group(1)).strip(),
                        int(r[1].replace(",", "").strip())))
    return out, date


def load_population(path: str | None):
    """{code: population} (코드 그대로), 기준월."""
    if not path:
        return {}, ""
    rows, date = read_mois(path)
    return {c: p for c, _, p in rows}, date


def population_for_dongs(path: str | None, dongs, log: list):
    """행정동 경계 코드 기준 인구.

    행안부 읍면동 목록에는 경계가 따로 없는 '출장소'(예: 순천시 해룡면신대출장소)와
    경계 파일보다 새로 나뉜 동(예: 평택시 고덕1동·고덕2동)이 있다. 이들의 인구는
    같은 시군구 안에서 코드가 바로 앞(작거나 같은)인 경계 행정동에 더한다.
    인구 0 이고 경계도 없는 곳(철원군 근동면 등 비거주 지역)은 버린다.
    """
    if not path:
        return {}, ""
    rows, date = read_mois(path)
    geo_codes = sorted(d["code"] for d in dongs)
    geo_set = set(geo_codes)
    by_sgg = defaultdict(list)
    for c in geo_codes:
        by_sgg[c[:5]].append(c)
    name_of = {d["code"]: f"{d['sigungu']} {d['name']}" for d in dongs}
    pop = {}
    for code, name, p in rows:
        if code[5:] == "00000":           # 시도·시군구 합계 행
            continue
        if code in geo_set:
            pop[code] = pop.get(code, 0) + p
            continue
        cands = [c for c in by_sgg.get(code[:5], []) if c <= code]
        if p == 0:
            log.append(f"버림(인구 0, 경계 없음): {name} ({code})")
            continue
        if not cands:
            log.append(f"버림(상위 행정동 없음): {name} ({code}) {p:,}명")
            continue
        parent = cands[-1]
        # 이름(예: '돌산읍우두출장소' 가 '돌산'으로 시작) 또는 코드 앞 7자리가 맞을 때만 합산
        short = name.split()[-1]
        stem = re.sub(r"[0-9.·]*(읍|면|동|가)$", "", name_of[parent].split()[-1])
        if not (stem and short.startswith(stem)) and parent[:7] != code[:7]:
            log.append(f"버림(상위 행정동 불확실): {name} ({code}) {p:,}명")
            continue
        pop[parent] = pop.get(parent, 0) + p
        log.append(f"합산: {name} ({code}) {p:,}명 -> {name_of[parent]} ({parent})")
    return pop, date


# ---------------------------------------------------------------- 장소
def kind_of(gubun: str, place_name: str, items: str) -> str:
    if gubun == "폐가전 수거함":
        return "battery_bin" if "건전지" in items else "other"
    if not gubun:
        return KIND_BY_PLACENAME.get(place_name, "other")
    return KIND_BY_GUBUN.get(gubun, "other")


def build_places(df: pd.DataFrame, jj: pd.DataFrame, index: DongIndex, bbox,
                 gu_field: str, stats: Counter) -> pd.DataFrame:
    """df: 통합본 행(필터 끝난 것), jj: 전주시 원본(ID 인덱스)."""

    def jj_coord(jid: str):
        for i in clean(jid).split(","):
            i = i.strip()
            if i in jj.index:
                lat = pd.to_numeric(jj.at[i, "위도"], errors="coerce")
                lng = pd.to_numeric(jj.at[i, "경도"], errors="coerce")
                if pd.notna(lat) and pd.notna(lng):
                    return float(lat), float(lng)
        return None

    def jj_dong_name(jid: str) -> str:
        i = clean(jid).split(",")[0].strip()
        return clean(jj.at[i, "행정동"]) if i in jj.index else ""

    # 같은 종류·같은 원본 좌표 = 중복 의심 (판매소는 같은 건물 다른 가게가 많아 제외)
    has = df["위도"].notna() & (df["구분"] != "종량제봉투 판매소")
    key = df["구분"].fillna("") + "|" + df["위도"].fillna("") + "|" + df["경도"].fillna("")
    dup_groups = defaultdict(list)
    for k, i in zip(key[has], df.loc[has, "ID"]):
        dup_groups[k].append(clean(i))

    (lat_lo, lat_hi), (lng_lo, lng_hi) = bbox
    rows = []
    for r, rkey in zip(df.to_dict("records"), key.tolist()):
        gubun = clean(r["구분"])
        items = clean(r["배출품목"])
        kind = kind_of(gubun, clean(r["장소명"]), items)
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
                dj, db = index.at(*c), index.at(lat, lng)
                if label and db is not None and db["name"] == label \
                        and (dj is None or dj["name"] != label):
                    coord_src = "분리의정석(전주시좌표 행정동 불일치)"
                    stats["coord_kept_bunri"] += 1
                else:
                    lat, lng = c
                    coord_src = "전주시"
        if pd.isna(lat) or pd.isna(lng) or not (lat_lo <= lat <= lat_hi) \
                or not (lng_lo <= lng <= lng_hi):
            stats[f"dropped_no_coord:{gubun or '(구분없음)'}"] += 1
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

        etc = clean(r["기타품목"])
        if etc and etc != items:
            items = f"{items}; {etc}" if items else etc

        remark = clean(r.get("전주_특이사항"))
        is_active = 0 if INACTIVE_RE.search(remark) else 1

        if kind == "other" or (kind == "battery_bin" and gubun not in ("전지 수거함", "형광등 수거함")) \
                or not gubun:
            if gubun == "폐가전 수거함" and clean(r["장소명"]) == "중소형 수거함":
                notes.append("원본구분=폐가전 수거함(중소형)")
            else:
                notes.append(f"원본구분={gubun or '(없음)'}/{clean(r['장소명'])}")
        elif clean(r["장소명"]) == "빈용기 반환수집소":
            notes.append("원본구분=무인회수기/빈용기 반환수집소")
        if jid:
            notes.append(f"전주시ID={jid}")
        for col, lab in [("전주_수거함종류", "수거함종류"), ("전주_칸수", "칸수"),
                         ("전주_CCTV", "CCTV"), ("전주_헌옷수거함", "헌옷수거함"),
                         ("전주_영농폐기물", "영농폐기물"), ("전주_특이사항", "특이사항")]:
            v = clean(r.get(col))
            if v:
                notes.append(f"{lab}={v}")
        if jid:
            notes.append("좌표=전주시원본" if coord_src == "전주시" else f"좌표={coord_src}")
        grp = dup_groups.get(rkey, [])
        if len(grp) > 1:
            others = [g for g in grp if g != clean(r["ID"])]
            shown = ",".join(others[:5]) + (f" 외 {len(others) - 5}" if len(others) > 5 else "")
            notes.append(f"중복의심(같은좌표 source_id={shown})")
            stats["dup_suspect_rows"] += 1

        # 행정동 point-in-polygon
        d = index.at(lat, lng)
        if d is not None:
            if jid and jj_dong_name(jid) and jj_dong_name(jid) != d["name"]:
                notes.append(f"전주시표기행정동={jj_dong_name(jid)}")
                stats["jeonju_label_mismatch"] += 1
        else:
            d, dist = index.nearest(lat, lng)
            if d is not None:
                notes.append(f"행정동경계밖(최근접 {dist:.0f}m)")
                stats["outside_nearest"] += 1
            else:
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
            "dong_code": d["code"] if d else "",
            "dong_name": d["name"] if d else "",
            "gu": d[gu_field] if d else "",
            "is_active": is_active,
            "note": "; ".join(notes),
        })
    return pd.DataFrame(rows, columns=PLACE_COLS)


def write_csv(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def write_csv_gz(df: pd.DataFrame, path: Path):
    """mtime=0, 파일명 없음 -> 같은 입력이면 같은 바이트."""
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                                                 mtime=0, compresslevel=9) as gz, \
            io.TextIOWrapper(gz, encoding="utf-8", newline="\n") as t:
        df.to_csv(t, index=False, lineterminator="\n")


def print_drops(stats: Counter):
    for k, v in sorted(stats.items()):
        if k.startswith("dropped"):
            print(f"  제외 {k.split(':', 1)[1]}: {v}")


# ---------------------------------------------------------------- 실행
def build_jeonju(a, tonghap: pd.DataFrame, jj: pd.DataFrame, out: Path):
    stats = Counter()
    dongs = load_dongs(a.geojson, JEONJU_SGG)
    pop, pop_date = load_population(a.population or a.population_kr)
    nb = neighbors(dongs, a.neighbor_buffer)

    gj = simplify_geojson(dongs, a.simplify, a.precision)
    gj_path = out / "jeonju_dongs.geojson"
    with open(gj_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(gj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    dong_rows = []
    for d in dongs:
        c = center_of(d["geom"])
        p = pop.get(d["code"])
        dong_rows.append({
            "code": d["code"], "name": d["name"], "gu": d["gu"],
            "population": "" if p is None else p,
            "population_date": pop_date if p is not None else "",
            "center_lat": f"{c.y:.6f}", "center_lng": f"{c.x:.6f}",
            "neighbors": ";".join(nb[d["code"]]),
        })
    write_csv(pd.DataFrame(dong_rows), out / "jeonju_dongs.csv")

    is_jj = (tonghap["시군구"].fillna("").str.contains("전주시")
             | tonghap["주소"].fillna("").str.contains("전주시"))
    df = tonghap[is_jj]
    places = build_places(df, jj, DongIndex(dongs), JEONJU_BBOX, "gu", stats)
    write_csv(places, out / "jeonju_places.csv")

    print(f"[전주] 행정동 {len(dongs)}개, geojson {gj_path.stat().st_size/1024:.0f} KB")
    missing = [d["name"] for d in dongs if d["code"] not in pop]
    print(f"[전주] 인구 기준월 {pop_date or '-'}, 합계 {sum(pop.get(d['code'], 0) for d in dongs):,}, "
          f"누락 {missing or '없음'}")
    print(f"[전주] 통합본 전주 행 {len(df)}, 출력 {len(places)}")
    print_drops(stats)
    print("[전주] kind별:", places["kind"].value_counts().to_dict())
    print("[전주] is_active=0:", int((places["is_active"] == 0).sum()),
          "/ 경계 밖:", stats["outside_all_dongs"], "/ 중복의심 행:", stats["dup_suspect_rows"])
    print("[전주] 분리의정석 좌표 유지:", stats["coord_kept_bunri"],
          "/ PIP 행정동 != 전주시 표기:", stats["jeonju_label_mismatch"])


def build_national(a, tonghap: pd.DataFrame, jj: pd.DataFrame, out: Path):
    stats = Counter()
    dongs = load_dongs(a.geojson)
    log: list[str] = []
    pop, pop_date = population_for_dongs(a.population_kr, dongs, log)

    dong_rows = []
    for d in dongs:
        c = center_of(d["geom"])
        p = pop.get(d["code"])
        dong_rows.append({
            "code": d["code"], "name": d["name"], "sido": d["sido"], "sido_code": d["sido_code"],
            "sigungu": d["sigungu"], "sigungu_code": d["sigungu_code"],
            "population": "" if p is None else p,
            "population_date": pop_date if p is not None else "",
            "center_lat": f"{c.y:.6f}", "center_lng": f"{c.x:.6f}",
        })
    kd = pd.DataFrame(dong_rows)
    write_csv(kd, out / "kr_dongs.csv")

    by_sgg = defaultdict(list)
    for d in dongs:
        by_sgg[d["sigungu_code"]].append(d)
    sgg_rows = []
    for code in sorted(by_sgg):
        ds = by_sgg[code]
        c = center_of(unary_union([d["geom"] for d in ds]))
        pops = [pop.get(d["code"]) for d in ds]
        sgg_rows.append({
            "sigungu_code": code, "sido": ds[0]["sido"], "sigungu": ds[0]["sigungu"],
            "population": sum(p for p in pops if p is not None) if any(p is not None for p in pops) else "",
            "center_lat": f"{c.y:.6f}", "center_lng": f"{c.x:.6f}",
            "dong_count": len(ds),
        })
    write_csv(pd.DataFrame(sgg_rows), out / "kr_sigungu.csv")

    places = build_places(tonghap, jj, DongIndex(dongs, NEAREST_MAX_M), KOREA_BBOX, "sigungu", stats)
    write_csv_gz(places, out / "kr_places.csv.gz")

    missing = [f"{d['sigungu']} {d['name']}({d['code']})" for d in dongs if d["code"] not in pop]
    print(f"[전국] 행정동 {len(dongs)}개, 시군구 {len(by_sgg)}개, 인구 기준월 {pop_date or '-'}, "
          f"합계 {sum(pop.values()):,}, 인구 누락 {len(missing)}: {missing or ''}")
    for line in log:
        print("   ", line)
    print(f"[전국] 통합본 {len(tonghap)}행, 출력 {len(places)}행, "
          f"kr_places.csv.gz {(out / 'kr_places.csv.gz').stat().st_size/1024/1024:.2f} MB")
    print_drops(stats)
    print("[전국] kind별:", places["kind"].value_counts().to_dict())
    print("[전국] 경계 밖 -> 최근접(2km 이내):", stats["outside_nearest"],
          "/ 2km 넘어 행정동 없음:", stats["outside_all_dongs"],
          "/ 중복의심 행:", stats["dup_suspect_rows"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tonghap", required=True)
    ap.add_argument("--jeonju", required=True)
    ap.add_argument("--geojson", required=True)
    ap.add_argument("--population")
    ap.add_argument("--population-kr")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-national", action="store_true")
    ap.add_argument("--simplify", type=float, default=0.0,
                    help="단순화 허용오차(도). 원본이 이미 일반화돼 있어 기본 0(좌표만 소수 6자리로 반올림)")
    ap.add_argument("--precision", type=int, default=6)
    ap.add_argument("--neighbor-buffer", type=float, default=0.0001, help="인접 판정 버퍼(도), 약 10m")
    a = ap.parse_args(argv)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tonghap = read_csv_any(a.tonghap)
    jj = read_csv_any(a.jeonju).set_index("ID")

    build_jeonju(a, tonghap, jj, out)
    if not a.no_national:
        build_national(a, tonghap, jj, out)


if __name__ == "__main__":
    sys.exit(main())
