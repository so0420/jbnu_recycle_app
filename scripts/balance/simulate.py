"""
리사이클 앱 - 지역 대전 / 경험치 밸런스 시뮬레이터
실행: python simulate.py            (기본 시나리오 3개 출력)
     python simulate.py --seed 7    (시드 변경)

게임시스템.md 의 수치를 그대로 옮긴 것. 수치를 바꾸면 이 파일의 CONFIG 도 같이 바꾸고 다시 돌려 볼 것.
인구는 실제 전주시 행정동 인구가 아니라 '비슷한 분포의 가짜 값'이다. 실제 자료를 받으면 POPS 를 교체.
"""
import argparse
import math
import random
import statistics as st

CONFIG = dict(
    days=28,                 # 시즌 길이(일)  - 정식 4주
    c_start=600, c_min=50, c_max=1000,
    daily_decay=25,          # 매일 자정 '생활 쓰레기' 감소
    target_restore=40,       # 지역 1곳이 하루 평균 회복하도록 맞추는 값 (자동 스케일 기준)
    atk_mult=1.5,            # 공격/정화 1회 = 인증 회복량의 1.5배
    w_min=0.5, w_max=3.0,    # 인구 보정 가중치 범위
    underdog=1.2,            # 순위가 더 높은 지역을 공격하면 x1.2
    fatigue_after=80,        # 하루에 받은 피해가 이 값을 넘으면
    fatigue_mult=0.5,        # 이후 피해 x0.5
    crisis_below=200,        # 청결도 200 미만 = 위기 지역
    crisis_restore=1.5,      # 위기 지역 회복 x1.5
    crisis_damage=0.5,       # 위기 지역이 받는 피해 x0.5
    top_target_prob=0.35,    # (사용자 행동 가정) 상위 5개 지역을 노리는 비율
    ticket_cap=5,
    # 경험치
    xp_verify=[30, 15, 15],  # 하루 1/2/3번째 인증 (4번째부터 0)
    xp_dayoff_bonus=10,      # 배출일 첫 인증 보너스
    xp_guide=5, guide_cap=5, # AI 촬영 안내 1회 5, 하루 5회까지
    xp_weekly=50, weekly_goal=3,
)

# 사용자 유형: (비율, 하루 인증 확률, 인증 시 하루 최대 횟수, 하루 평균 촬영안내 횟수)
USER_TYPES = {
    "casual":  (0.55, 0.30, 1, 0.5),
    "regular": (0.35, 0.55, 2, 1.5),
    "heavy":   (0.10, 0.90, 3, 4.0),
}


def need_xp(level):            # level -> level+1 에 필요한 경험치
    return 40 + 20 * level


def level_of(xp):
    lv = 1
    while xp >= need_xp(lv):
        xp -= need_xp(lv)
        lv += 1
    return lv


def spearman(a, b):
    def ranks(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0] * len(x)
        for k, i in enumerate(order):
            r[i] = k
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else 0.0


def run(pops, rates, cfg, rng, clamp=True, label=""):
    n = len(pops)
    p_ref = st.mean(pops)
    if clamp:
        w = [min(cfg["w_max"], max(cfg["w_min"], p_ref / p)) for p in pops]
    else:
        w = [p_ref / p for p in pops]

    # 배출일: 지역마다 주 3일
    dump_days = [set(rng.sample(range(7), 3)) for _ in range(n)]

    users = []
    for r in range(n):
        cnt = max(0, round(pops[r] * rates[r]))
        for _ in range(cnt):
            t = rng.choices(list(USER_TYPES), [v[0] for v in USER_TYPES.values()])[0]
            users.append(dict(region=r, type=t, xp=0, tickets=0, week_cnt=0, weekly_done=False))

    C = [float(cfg["c_start"])] * n
    hist_verifs = []
    floor_hits = ceil_hits = 0

    for day in range(cfg["days"]):
        wd = day % 7
        if wd == 0:
            for u in users:
                u["week_cnt"], u["weekly_done"] = 0, False
        recent = hist_verifs[-7:]
        avg_v = st.mean(recent) if recent else max(1, len(users) * 0.4)
        r_base = cfg["target_restore"] * n / max(avg_v, n)
        d_base = cfg["atk_mult"] * r_base

        ranking = sorted(range(n), key=lambda i: -C[i])
        rank_of = {reg: k for k, reg in enumerate(ranking)}
        dmg_today = [0.0] * n
        verifs = 0
        rng.shuffle(users)

        for u in users:
            _, p_verify, max_v, guide_mean = USER_TYPES[u["type"]]
            reg = u["region"]
            # 촬영 안내
            g = min(cfg["guide_cap"], int(rng.expovariate(1 / guide_mean)) if guide_mean else 0)
            u["xp"] += g * cfg["xp_guide"]
            # 배출 인증
            if rng.random() < p_verify:
                k = rng.randint(1, max_v)
                for i in range(min(k, 3)):
                    u["xp"] += cfg["xp_verify"][i]
                    boost = cfg["crisis_restore"] if C[reg] < cfg["crisis_below"] else 1.0
                    C[reg] += r_base * w[reg] * boost
                    verifs += 1
                if wd in dump_days[reg]:
                    u["xp"] += cfg["xp_dayoff_bonus"]
                    u["tickets"] = min(cfg["ticket_cap"], u["tickets"] + 1)
                u["week_cnt"] += 1
                if not u["weekly_done"] and u["week_cnt"] >= cfg["weekly_goal"]:
                    u["weekly_done"] = True
                    u["xp"] += cfg["xp_weekly"]
                    u["tickets"] = min(cfg["ticket_cap"], u["tickets"] + 1)
            # 공격권 사용 (보유분 중 1장, 70% 확률로 당일 사용)
            if u["tickets"] and rng.random() < 0.7:
                u["tickets"] -= 1
                median_c = sorted(C)[n // 2]
                defend = C[reg] < median_c and rng.random() < 0.4
                if defend:
                    boost = cfg["crisis_restore"] if C[reg] < cfg["crisis_below"] else 1.0
                    C[reg] += d_base * w[reg] * boost
                else:
                    others = [i for i in range(n) if i != reg]
                    top = [i for i in ranking[:5] if i != reg]
                    tgt = rng.choice(top) if (top and rng.random() < cfg["top_target_prob"]) else rng.choice(others)
                    dmg = d_base * w[reg]
                    if rank_of[tgt] < rank_of[reg]:
                        dmg *= cfg["underdog"]
                    if dmg_today[tgt] > cfg["fatigue_after"]:
                        dmg *= cfg["fatigue_mult"]
                    if C[tgt] < cfg["crisis_below"]:
                        dmg *= cfg["crisis_damage"]
                    dmg_today[tgt] += dmg
                    C[tgt] -= dmg
            for i in (reg,):
                C[i] = min(cfg["c_max"], C[i])
        # 자정 처리
        for i in range(n):
            C[i] -= cfg["daily_decay"]
            if C[i] <= cfg["c_min"]:
                floor_hits += 1
            if C[i] >= cfg["c_max"]:
                ceil_hits += 1
            C[i] = max(cfg["c_min"], min(cfg["c_max"], C[i]))
        hist_verifs.append(verifs)

    # 결과
    real_rate = []
    for r in range(n):
        cnt = sum(1 for u in users if u["region"] == r)
        real_rate.append(cnt / pops[r])
    print(f"\n=== {label} ===")
    print(f"지역 {n}개, 사용자 {len(users)}명, 하루 평균 인증 {st.mean(hist_verifs):.0f}건")
    print(f"최종 청결도: 최저 {min(C):.0f} / 중앙 {st.median(C):.0f} / 최고 {max(C):.0f}")
    print(f"하한(50) 도달 지역-일 {floor_hits}, 상한(1000) 도달 지역-일 {ceil_hits}")
    print(f"순위 상관(스피어만)  참여율↔청결도 {spearman(real_rate, C):+.2f}   인구↔청결도 {spearman(pops, C):+.2f}")
    cs = sorted(C)
    print("청결도 분포(낮은→높은):", " ".join(f"{c:.0f}" for c in cs))
    for t in USER_TYPES:
        xs = [u["xp"] for u in users if u["type"] == t]
        if xs:
            lv = [level_of(x) for x in xs]
            print(f"  {t:8s} {len(xs):5d}명  XP 중앙 {st.median(xs):5.0f}  레벨 중앙 Lv{st.median(lv):.0f} (최고 Lv{max(lv)})")
    return C


def jeonju_like_pops(rng, n=35):
    # 전주시 인구 약 64만, 행정동 평균 1.8만, 4천~4.5만 범위의 가짜 분포
    pops = [int(min(45000, max(4000, rng.lognormvariate(math.log(16000), 0.55)))) for _ in range(n)]
    return pops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    cfg = CONFIG

    pops = jeonju_like_pops(rng)
    rates = [rng.uniform(0.002, 0.02) for _ in pops]   # 참여율 0.2% ~ 2%

    run(pops, rates, cfg, random.Random(a.seed), clamp=True, label="A. 정식 운영 가정 - 행정동 35개, 인구보정 0.5~3.0")
    run(pops, rates, cfg, random.Random(a.seed), clamp=False, label="B. 비교 - 인구보정 상한 없음 (1/인구 그대로)")

    # C. 수업 시연: 권역 6개, 테스터 30명
    demo_pops = [sum(pops[i::6]) for i in range(6)]
    demo_rates = [rng.randint(3, 7) / p for p in demo_pops]   # 권역당 3~7명
    demo_cfg = dict(cfg, days=7)
    run(demo_pops, demo_rates, demo_cfg, random.Random(a.seed), clamp=True, label="C. 수업 시연 - 권역 6개, 테스터 약 30명, 1주 시즌")


if __name__ == "__main__":
    main()
