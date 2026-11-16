"""
일러스트 생성 + 'AI 티 지우기' 후처리 스크립트

캐릭터(리몬·보스·정원)는 SVG 코드로 만든다(remon-style.html). 이 스크립트는 그 외의
큰 일러스트(온보딩, 보스 예고 배너, 시즌 종료 화면, 발표 표지)에만 쓴다.

준비
  pip install openai pillow
  set OPENAI_API_KEY=...            (PowerShell: $env:OPENAI_API_KEY="...")
  set OPENAI_IMAGE_MODEL=gpt-image-2  ← OpenAI 문서에서 쓰려는 모델 id를 확인해서 넣는다
                                       (예: gpt-image-2.6 이 실제로 있으면 그 이름)

사용
  python gen_image.py list                         프롬프트 목록
  python gen_image.py gen onboarding_1 --ref refs/petring.png --n 3
  python gen_image.py post out/onboarding_1_0.png  후처리만 다시 하기

출력: out/<이름>_<번호>.png (원본), out/<이름>_<번호>_final.png (후처리본)
사람이 후처리본 중 하나를 고르고, 아래 CHECKLIST 를 통과한 것만 쓴다.
"""
import argparse
import base64
import os
import random
import sys
from pathlib import Path

from PIL import Image, ImageFilter

HERE = Path(__file__).parent
OUT = HERE / "out"

# ── 게임 팔레트 (remon-style.html 과 같은 색). 후처리에서 이 색들로만 다시 칠한다 ──
PALETTE = [
    "#2A2622", "#FFFFFF", "#E9ECE6",              # 선, 흰색, 배경
    "#CFE8F4", "#9AC6DE", "#2C6BCB",              # 플라스틱
    "#C99A62", "#A97A45", "#EBDBBB",              # 종이
    "#C8CDD5", "#99A1AD", "#D8402F",              # 금속
    "#8DCAA1", "#5FA67A", "#E8B748",              # 유리
    "#F2EFF6", "#D3CBE2", "#6FB5E6",              # 비닐
    "#8B87A1", "#68637E", "#EFC83E", "#F3A0A6",   # 보스, 볼터치
]

# ── 공통 스타일 문장: 구체적인 '실제 매체'를 지정하고 AI 특유의 표현을 금지한다 ──
STYLE = (
    "Flat sticker-style illustration for a Korean mobile game about recycling. "
    "Thick, slightly uneven hand-inked black outlines of varying weight. "
    "Only flat color fills from a small limited palette, with at most one flat shadow tone per shape. "
    "Simple shapes, generous empty space, plain light background. "
    "Match the character designs in the reference images exactly: same proportions, same faces, same colors. "
    "Do NOT use: gradients, glossy or 3D rendering, soft airbrushed shading, glow, bloom, rim light, "
    "lens blur, bokeh, cinematic lighting, hyper-detailed textures, photorealism, sparkle overload, "
    "any letters, words, numbers, logos or watermarks."
)

PROMPTS = {
    "onboarding_1": "A small PET bottle character with a red label stands on a kitchen counter next to a sink, "
                    "looking up hopefully as a hand rinses it under the tap. Cozy apartment kitchen, very simple background.",
    "onboarding_2": "Five small characters (a PET bottle, a cardboard box bear, a can, a green glass bird, "
                    "a plastic bag ghost) line up in front of a Korean apartment recycling collection point "
                    "with separate colored bins, at early evening.",
    "onboarding_3": "The five recycling characters stand together on a small hill facing a large grey monster "
                    "made of bottles wrapped in yellow labels, in a Korean neighborhood with low apartment buildings.",
    "boss_banner_label_golem": "Wide banner: a large grey-violet golem made of stacked bottles and cans, "
                               "wrapped in yellow label strips like bandages, angry red eyes, standing in an empty "
                               "street at dusk. Leave the left third empty for text added later.",
    "season_end": "The five recycling characters celebrate on top of a clean recycling bin, confetti made of "
                  "small paper scraps, bright daytime.",
    "cover": "Presentation cover: a PET bottle character holding a small flag, standing on a simplified map "
             "of a Korean city drawn as soft colored blocks. Leave the top third empty for a title.",
}

SIZES = {"boss_banner_label_golem": "1536x1024", "cover": "1536x1024"}

CHECKLIST = """
사람이 확인할 것 (하나라도 걸리면 버림)
 [ ] 캐릭터 모양·색이 SVG 원본과 같은가 (눈 개수, 라벨 색, 비율)
 [ ] 손·발·팔 개수가 이상하지 않은가
 [ ] 글자처럼 보이는 낙서가 없는가 (간판, 라벨 위 글씨)
 [ ] 그라데이션·광택이 후처리 뒤에도 남아 있지 않은가
 [ ] 배경이 지나치게 정밀하지 않은가 (캐릭터보다 배경이 눈에 띄면 탈락)
 [ ] 한국 분리수거장이 실제와 다르게 그려지지 않았는가 (분리수거함 색, 배치)
"""


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def palette_image():
    pal = Image.new("P", (1, 1))
    flat = []
    for c in PALETTE:
        flat.extend(hex_rgb(c))
    flat.extend([0, 0, 0] * (256 - len(PALETTE)))
    pal.putpalette(flat)
    return pal


def postprocess(src: Path) -> Path:
    """AI 티 지우기: 팔레트 고정 → 그라데이션 제거, 살짝 거친 종이 질감, 미세한 해상도 손실."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    # 1) 살짝 줄였다 키워서 지나치게 매끈한 디테일을 뭉갬
    small = img.resize((int(w * 0.6), int(h * 0.6)), Image.LANCZOS)
    small = small.filter(ImageFilter.MedianFilter(3))
    # 2) 게임 팔레트로만 다시 칠함 (디더링 없음 → 면이 납작해짐)
    q = small.quantize(palette=palette_image(), dither=Image.Dither.NONE).convert("RGB")
    q = q.resize((w, h), Image.NEAREST).filter(ImageFilter.SMOOTH)
    # 3) 종이 질감 (아주 약한 노이즈)
    rnd = random.Random(7)
    px = q.load()
    for _ in range(w * h // 6):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r, g, b = px[x, y]
        d = rnd.randint(-10, 6)
        px[x, y] = (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)))
    dst = src.with_name(src.stem + "_final.png")
    q.save(dst)
    return dst


def generate(name, refs, n):
    from openai import OpenAI  # 설치 안 된 환경에서도 list/post 는 되도록 여기서 import

    model = os.environ.get("OPENAI_IMAGE_MODEL")
    if not model:
        sys.exit("OPENAI_IMAGE_MODEL 환경변수를 설정하세요 (OpenAI 문서에서 모델 id 확인).")
    client = OpenAI()
    prompt = PROMPTS[name] + "\n\n" + STYLE
    size = SIZES.get(name, "1024x1024")
    OUT.mkdir(exist_ok=True)
    if refs:
        files = [open(r, "rb") for r in refs]
        try:
            res = client.images.edit(model=model, image=files, prompt=prompt, size=size, n=n)
        finally:
            for f in files:
                f.close()
    else:
        res = client.images.generate(model=model, prompt=prompt, size=size, n=n)
    for i, d in enumerate(res.data):
        raw = OUT / f"{name}_{i}.png"
        raw.write_bytes(base64.b64decode(d.b64_json))
        print("생성:", raw, "→ 후처리:", postprocess(raw))
    print(CHECKLIST)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    g = sub.add_parser("gen")
    g.add_argument("name", choices=list(PROMPTS))
    g.add_argument("--ref", action="append", default=[], help="참고 이미지(SVG에서 뽑은 PNG). 여러 번 지정 가능")
    g.add_argument("--n", type=int, default=3)
    p = sub.add_parser("post")
    p.add_argument("file")
    a = ap.parse_args()
    if a.cmd == "list":
        for k, v in PROMPTS.items():
            print(f"{k:26s} {SIZES.get(k, '1024x1024'):10s} {v[:60]}...")
    elif a.cmd == "gen":
        generate(a.name, a.ref, a.n)
    else:
        print(postprocess(Path(a.file)))


if __name__ == "__main__":
    main()
