// 리몬 37칸. artKey = `<line>_<stage>` (예: petring_2, reverse_1)
// 희귀 계열은 일반 계열과 같은 몸 + 다른 팔레트 + 소품 하나.

import {
  Ctx, Pal, Mood, RemonType, ctx, face, mouth, moodMouth, stars, scaleFrom, mirror, rot, tube, poly,
  fluff, spiky, leaf, stickerSvg, n,
} from './core';

type Stage = 1 | 2 | 3;
type Draw = (c: Ctx, st: Stage, rare: boolean) => string;

interface LineDef {
  type: RemonType;
  pal: Pal;
  shiny: Pal;
  draw: Draw;
  rare?: boolean;
  stages?: number;
  float?: (st: Stage) => boolean;
  groundRx?: (st: Stage) => number;
  sparkles?: number[][];
}

export interface RemonOpts {
  shiny?: boolean;
  mood?: Mood;
}

const STAGE_SCALE = [1, 1, 1.05, 1.08];
const DEFAULT_SPARKS = [[40, 52, 9], [160, 64, 7], [150, 30, 5]];

const feet = (c: Ctx, x1: number, x2: number, role = 'acc2', y = 181): string =>
  `<ellipse cx="${x1}" cy="${y}" rx="12" ry="7" ${c.s(role)}/><ellipse cx="${x2}" cy="${y}" rx="12" ry="7" ${c.s(role)}/>`;

// ───────────── 플라스틱: 페트링 / 콜라 페트링 ─────────────
const pet: Draw = (c, st, rare) => {
  const s = c.s;
  let b = '';
  if (st === 3) {
    const wing =
      `<path d="M64 104 C34 76 10 90 15 122 C27 113 36 119 38 130 C46 119 56 123 62 134 Z" ${s('body')}/>` +
      `<path d="M58 110 L28 101 M58 118 L30 119 M59 126 L42 129" ${s('line', 2.6)}/>`;
    b += wing + mirror(wing);
  }
  if (st === 2) {
    b += `<path d="M62 120 Q44 124 40 106" ${s('line', 4)}/><circle cx="40" cy="100" r="8" ${s('acc2')}/>`;
    b += `<path d="M138 120 Q158 114 162 96" ${s('line', 4)}/><circle cx="162" cy="90" r="8" ${s('acc2')}/>`;
  }
  b += feet(c, 80, 120);
  if (rare) b += tube(st === 3 ? 'M108 50 L120 40 Q123 37 129 38 L141 41' : 'M106 44 L118 31 Q121 27 127 28 L139 30', 12, c.p.acc, 8);
  b += `<path d="M86 56 C86 72 60 74 60 98 L60 160 Q60 177 77 177 L123 177 Q140 177 140 160 L140 98 C140 74 114 72 114 56 Z" ${s('body')}/>`;
  b += `<path d="M126 96 C132 104 133 112 133 122 L133 158 Q133 170 121 170 L117 170 Q126 165 126 154 Z" ${s('dark')}/>`;
  b += `<rect x="81" y="44" width="38" height="13" rx="4" ${s('acc2')}/>`;
  if (st === 3) b += `<path d="M84 46 L84 26 L92 35 L100 22 L108 35 L116 26 L116 46 Z" ${s('acc2')}/>`;
  else b += `<rect x="85" y="28" width="30" height="18" rx="5" ${s('acc2')}/>`;
  b += `<rect x="68" y="98" width="7" height="24" rx="3.5" ${s('light')}/>`;
  if (st === 1) b += `<rect x="60" y="130" width="80" height="24" ${s('acc')}/>`;
  if (st === 2) {
    b += `<path d="M60 130 L116 130 L116 154 L60 154 Z" ${s('acc')}/>`;
    b += `<path d="M116 130 L150 119 L147 147 L116 154 Z" ${s('acc')}/>`;
  }
  if (st === 3) b += `<rect x="70" y="132" width="5" height="30" rx="2.5" ${s('light')}/><path d="M84 160 Q100 168 116 160" ${s('lightline')}/>`;
  b += face(c, 100, 108, st === 1 ? {} : st === 2 ? { brow: true, mouth: 'open' } : { eye: 'cool', mouth: 'smirk' });
  return b;
};

// ───────────── 종이: 박스곰 / 택배곰 ─────────────
const box: Draw = (c, st, rare) => {
  const s = c.s;
  let b = '';
  if (st >= 2) {
    // 팔
    const arm = rot(st === 2 ? -30 : -12, 52, 118, `<rect x="22" y="108" width="36" height="22" rx="11" ${s('body')}/><circle cx="28" cy="119" r="8" ${s('acc2')}/>`);
    b += arm + mirror(arm);
  }
  if (st === 2) {
    // 활짝 열린 날개 뚜껑
    const flap = `<path d="M56 70 L24 46 L52 30 L92 66 Z" ${s('body')}/><path d="M56 62 L40 48" ${s('line', 2.4)}/>`;
    b += flap + mirror(flap);
    b += `<path d="M68 66 L74 42 L126 42 L132 66 Z" ${s('dark')}/><path d="M68 66 L74 42 L126 42 L132 66" ${s('line', 3)}/>`;
  }
  b += feet(c, 78, 122);
  const ear = `<g transform="rotate(-14 66 62)"><rect x="50" y="46" width="32" height="28" rx="7" ${s('body')}/><rect x="58" y="53" width="16" height="14" rx="4" ${s('acc2')}/></g>`;
  b += ear + mirror(ear);
  b += `<rect x="50" y="64" width="100" height="112" rx="9" ${s('body')}/>`;
  b += `<rect x="132" y="70" width="11" height="100" rx="5" ${s('dark')}/>`;
  if (st === 3) {
    // 골판지 주름 이음선
    let d = 'M50 86';
    for (let i = 0; i < 8; i++) d += ` q6.25 ${i % 2 ? 5 : -5} 12.5 0`;
    b += `<path d="${d}" ${s('line', 3)}/>`;
  } else b += `<path d="M50 86 L150 86" ${s('line', 3)}/>`;
  if (st === 1) b += `<rect x="90" y="64" width="20" height="22" ${s('acc')}/>`;
  if (st === 2) {
    // 테이프가 반쯤 떨어짐
    b += `<rect x="90" y="64" width="20" height="9" ${s('acc')}/>`;
    b += `<path d="M110 66 Q130 48 146 58 L140 66 Q126 60 110 73 Z" ${s('acc')}/>`;
  }
  if (st === 3) {
    // 접은 종이 갑옷: 어깨받이 + 가슴판 + 왕관
    const pad = `<path d="M50 70 L26 84 L32 108 L62 98 L62 70 Z" ${s('acc')}/><path d="M30 94 L60 84" ${s('line', 2.4)}/>`;
    b += pad + mirror(pad);
    b += `<path d="M62 150 L104 150 L104 172 L62 172 Z" ${s('acc')}/><path d="M62 150 L83 162 L104 150" ${s('line', 2.4)}/>`;
    b += `<path d="M76 66 L74 40 L87 52 L100 34 L113 52 L126 40 L124 66 Z" ${s('acc')}/><path d="M80 58 L120 58" ${s('line', 2.4)}/>`;
  }
  if (rare) {
    // 송장 스티커
    b += rot(-6, 127, 159,
      `<rect x="112" y="148" width="30" height="22" rx="2" fill="#FFFFFF" stroke="#2A2622" stroke-width="3.4" stroke-linejoin="round"/>` +
      `<rect x="114" y="150" width="26" height="5" fill="#E5553C"/>` +
      `<path d="M117 159 L117 167 M120 159 L120 167 M124 159 L124 167 M126 159 L126 167 M130 159 L130 167 M134 159 L134 167 M137 159 L137 167" stroke="#2A2622" stroke-width="1.6"/>`);
  } else if (st < 3) b += `<path d="M64 162 L72 149 L80 162 Z" ${s('line', 2.6)}/>`;
  b += `<ellipse cx="100" cy="132" rx="21" ry="15" ${s('acc')}/>`;
  b += `<ellipse cx="100" cy="126" rx="6.5" ry="4.8" ${s('eye')}/>`;
  b += mouth(c, 100, 134, 1.15, moodMouth(c, st === 1 ? 'smile' : st === 2 ? 'open' : 'smirk'));
  b += face(c, 100, 106, { gap: 24, mouth: false, brow: st === 2, eye: st === 3 ? 'cool' : undefined });
  return b;
};

// ───────────── 금속: 캔돌이 / 참치캔돌이 ─────────────
/** 생선 모양 꼭지 (cx,cy 중심, ang 기울기) */
const fishTab = (c: Ctx, cx: number, cy: number, k: number, ang: number): string =>
  rot(ang, cx, cy,
    `<path d="${poly([[12, 0], [24, -9], [22, 0], [24, 9]], cx, cy, k)}" ${c.s('fish')}/>` +
    `<ellipse cx="${cx}" cy="${cy}" rx="${n(15 * k)}" ry="${n(9 * k)}" ${c.s('fish')}/>` +
    `<circle cx="${n(cx - 8 * k)}" cy="${n(cy - 2 * k)}" r="${n(2.2 * k)}" ${c.s('eye')}/>` +
    `<path d="M${n(cx - 1 * k)} ${n(cy - 6 * k)} Q${n(cx + 3 * k)} ${cy} ${n(cx - 1 * k)} ${n(cy + 6 * k)}" ${c.s('line', 2.2)}/>`);

const can: Draw = (c, st, rare) => {
  const s = c.s;
  let b = '';
  const top = st === 1 ? 50 : st === 2 ? 52 : 62;
  const x0 = st === 1 ? 62 : 56;
  const x1 = 200 - x0;
  const hw = (x1 - x0) / 2;
  if (st === 2) {
    const arm = tube('M62 118 Q40 118 34 100', 15, c.p.body) + `<circle cx="34" cy="92" r="12" ${s('acc')}/><path d="M28 88 Q34 84 40 88" ${s('lightline', 3)}/>`;
    b += arm + mirror(arm);
  }
  if (st === 3) {
    // 오른손 검
    b += tube('M140 122 Q160 122 162 112', 15, c.p.body);
    b += `<path d="M157 100 L157 52 L162 42 L167 52 L167 100 Z" ${s('blade')}/><path d="M162 52 L162 94" ${s('line', 2)}/>`;
    b += `<rect x="148" y="98" width="28" height="8" rx="3" ${s('acc2')}/><circle cx="162" cy="112" r="10" ${s('acc2')}/>`;
  }
  b += feet(c, 80, 120);
  // 꼭지 / 깃털 장식
  if (st === 3) {
    if (rare) b += fishTab(c, 108, top - 14, 1.15, -28);
    else b += `<path d="M100 ${top - 4} C94 ${top - 26} 112 ${top - 36} 138 ${top - 32} C126 ${top - 26} 124 ${top - 20} 128 ${top - 12} C118 ${top - 14} 110 ${top - 10} 106 ${top - 2} Z" ${s('acc')}/>`;
  } else if (!rare) b += `<ellipse cx="111" cy="${top - 12}" rx="10" ry="6" ${s('line', 3.6)}/><path d="M105 ${top - 6} L100 ${top}" ${s('line', 3.6)}/>`;
  b += `<rect x="${x0}" y="${top}" width="${x1 - x0}" height="${176 - top}" rx="12" ${s('body')}/>`;
  b += `<rect x="${x1 - 17}" y="${top + 12}" width="10" height="${170 - top - 12}" rx="5" ${s('dark')}/>`;
  b += `<ellipse cx="100" cy="${top + 2}" rx="${hw}" ry="10" ${s('acc2')}/><ellipse cx="100" cy="${top + 2}" rx="${hw - 11}" ry="6" ${s('dark')}/>`;
  if (rare && st < 3) b += fishTab(c, 98, top - 3, 0.85, -10);
  b += `<rect x="${x0}" y="124" width="${x1 - x0}" height="32" ${s('acc')}/>`;
  if (rare) b += `<path d="${poly([[-14, 0], [-4, -8], [10, -6], [16, 0], [10, 6], [-4, 8]], 96, 140)}" ${s('~fish')}/><path d="M112 140 L120 133 L120 147 Z" ${s('~fish')}/>`;
  b += `<rect x="${x0 + 8}" y="${st === 3 ? top + 28 : top + 14}" width="8" height="${st === 3 ? 30 : 48}" rx="4" ${s('light')}/>`;
  if (st === 2) b += `<path d="M86 134 L100 146 L114 134" ${s('lightline', 4)}/>`;
  if (st === 3) {
    b += `<rect x="${x0}" y="${top + 12}" width="${x1 - x0}" height="11" ${s('acc2')}/>`;
    b += [x0 + 10, 100, x1 - 10].map((x) => `<circle cx="${x}" cy="${top + 17.5}" r="2.4" ${s('hi')}/>`).join('');
  }
  b += `<path d="M${x1 + 1} 88 L${x1 - 7} 95 L${x1 + 1} 102" ${s('line', 3)}/>`;
  b += face(c, 100, top + 46, st === 1 ? { gap: 17 } : st === 2 ? { gap: 18, brow: true, mouth: 'open' } : { gap: 18, eye: 'cool', mouth: 'smirk' });
  if (st === 3) {
    // 찌그러진 뚜껑 방패
    b += `<circle cx="56" cy="142" r="30" ${s('acc2')}/><circle cx="56" cy="142" r="20" ${s('line', 2.6)}/>`;
    b += `<path d="M44 128 L50 134 L46 140 M64 150 L70 156 M62 128 L66 136" ${s('line', 2.4)}/>`;
    b += `<path d="M38 132 Q42 122 52 118" ${s('lightline', 4)}/><circle cx="56" cy="142" r="4" ${s('body', 2.4)}/>`;
  }
  return b;
};

// ───────────── 유리: 유리새 / 호박유리새 ─────────────
const glass: Draw = (c, st, rare) => {
  const s = c.s;
  let b = '';
  if (st === 3) {
    const wing =
      `<path d="M70 112 L30 66 L40 94 L18 92 L36 114 L20 128 L46 134 L34 150 L66 144 Z" ${s('body')}/>` +
      `<path d="M64 118 L40 94 M62 128 L36 114 M62 136 L46 134" ${s('line', 2.4)}/>`;
    b += wing + mirror(wing, 204);
    b += `<path d="M62 140 L18 150 L40 158 L14 172 L64 162 Z" ${s('acc2')}/>`;
  }
  b += `<path d="M92 174 L92 186 M112 174 L112 186 M85 186 L99 186 M105 186 L119 186" ${s('line', 3.4)}/>`;
  if (st === 1) b += `<path d="M60 128 L24 106 L30 148 Z" ${s('body')}/>`;
  if (st === 2) {
    b += `<path d="M62 122 L22 98 L42 122 Z" ${s('body')}/><path d="M60 132 L14 128 L40 142 Z" ${s('body')}/><path d="M62 142 L26 162 L50 140 Z" ${s('body')}/>`;
  }
  if (st >= 2) {
    // 수정 볏
    const cr = st === 3 ? 'acc2' : 'body';
    b += `<path d="M116 64 L142 30 L126 70 Z" ${s(cr)}/><path d="M114 58 L128 22 L120 62 Z" ${s(cr)}/>`;
  }
  const neckTop = st === 3 ? 40 : 46;
  b += `<rect x="88" y="${neckTop}" width="32" height="${96 - neckTop}" rx="12" ${s('body')}/>`;
  if (st === 3) {
    // 뚜껑을 뗀 병 주둥이
    b += `<rect x="85" y="34" width="38" height="12" rx="5" ${s('body')}/><ellipse cx="104" cy="37" rx="11" ry="3" ${s('dark')}/>`;
  } else if (rare) {
    b += `<path d="M88 36 Q88 30 94 30 L114 30 Q120 30 120 36 L120 50 L116 55 L112 50 L108 55 L104 50 L100 55 L96 50 L92 55 L88 50 Z" ${s('acc')}/>`;
    b += `<path d="M93 36 L115 36" ${s('lightline', 3)}/>`;
  } else b += `<rect x="90" y="30" width="28" height="20" rx="5" ${s('acc')}/>`;
  b += `<circle cx="104" cy="130" r="50" ${s('body')}/>`;
  b += `<ellipse cx="139" cy="134" rx="8" ry="28" ${s('dark')}/>`;
  if (st >= 2) b += `<path d="M118 172 L128 156 L148 156 M84 176 L94 164 L108 168" ${s('line', 2.4)}/>`;
  if (st === 1) {
    b += `<path d="M66 126 Q56 152 82 164 Q92 146 85 128 Z" ${s('body')}/>`;
    b += `<path d="M70 140 Q76 146 82 146 M72 151 Q78 156 84 155" ${s('line', 2.4)}/>`;
  } else {
    b += `<path d="M68 124 L50 160 L64 154 L68 170 L88 148 L84 126 Z" ${s('body')}/><path d="M70 136 L64 154 M78 140 L76 158" ${s('line', 2.4)}/>`;
  }
  b += `<path d="M76 104 Q66 124 74 146" ${s('lightline')}/>`;
  b += `<rect x="94" y="${neckTop + 8}" width="5" height="24" rx="2.5" ${s('light')}/>`;
  b += face(c, 108, 114, st === 3 ? { gap: 17, mouth: false, eye: 'cool' } : { gap: 17, mouth: false, brow: st === 2 });
  b += `<path d="M101 128 L115 128 L108 138 Z" ${s('acc2')}/>`;
  if (c.mood !== 'normal') b += mouth(c, 108, 141, 0.7, moodMouth(c, 'smile'));
  return b;
};

// ───────────── 비닐: 비닐리 / 뽁뽁이 ─────────────
const bubbles = (c: Ctx, pts: number[][]): string =>
  pts.map((p) => `<circle cx="${p[0]}" cy="${p[1]}" r="4.6" fill="#FFFFFF" fill-opacity=".6" stroke="${c.p.acc}" stroke-width="2.2"/><circle cx="${p[0] - 1.4}" cy="${p[1] - 1.4}" r="1.3" fill="#FFFFFF"/>`).join('');

const vinyl: Draw = (c, st, rare) => {
  const s = c.s;
  const B = c.p.body;
  let b = '';
  if (st === 1) {
    b += tube('M72 66 C70 30 94 30 92 66', 15, B) + tube('M108 66 C106 30 130 30 128 66', 15, B);
    b += `<path d="M58 62 L142 62 L150 158 Q140 172 128 162 Q116 176 100 164 Q84 176 72 162 Q60 172 50 158 Z" ${s('body')}/>`;
    b += `<path d="M134 84 L141 150 Q136 156 131 152 L126 86 Z" ${s('dark')}/>`;
    b += `<path d="M58 62 L142 62 L143 77 L57 77 Z" ${s('acc')}/>`;
    b += `<path d="M68 136 L77 125 M121 94 L127 107 M84 152 L91 145" ${s('line', 2.4)}/>`;
    if (rare) b += bubbles(c, [[70, 90], [86, 90], [102, 90], [118, 90], [132, 92], [72, 146], [104, 146], [120, 146], [136, 142]]);
    b += face(c, 100, 112, { gap: 18 });
    return b;
  }
  const big = st === 3;
  if (big) {
    // 랩 필름 날개
    const wing =
      `<path d="M80 110 C58 70 24 60 12 82 C26 84 30 94 24 106 C38 102 46 112 42 126 C54 120 64 126 66 136 Z" ${s('body')}/>` +
      `<path d="M76 112 L28 84 M72 120 L36 110 M70 128 L48 126" ${s('line', 2.4)}/>`;
    b += wing + mirror(wing);
    b += tube('M150 172 C178 172 184 152 172 140', 14, B);
    b += `<path d="M166 142 L174 120 L184 144 Z" ${s('acc')}/>`;
  } else b += tube('M146 168 C170 172 178 160 170 150', 12, B);
  // 똬리: 겹친 고리 두 개 + 위로 솟은 목
  const coil = (cy: number, rx: number, ry: number, w: number): string =>
    `<ellipse cx="100" cy="${cy}" rx="${rx}" ry="${ry}" ${s('~dark')}/>` +
    tube(`M${100 - rx} ${cy} A${rx} ${ry} 0 1 0 ${100 + rx} ${cy} A${rx} ${ry} 0 1 0 ${100 - rx} ${cy} Z`, w, B);
  const c1 = big ? [164, 56, 12, 24] : [164, 50, 11, 22];
  const c2 = big ? [142, 40, 10, 22] : [144, 36, 9, 20];
  b += coil(c1[0], c1[1], c1[2], c1[3]) + coil(c2[0], c2[1], c2[2], c2[3]);
  b += tube(big ? 'M114 136 C142 112 78 114 100 94' : 'M112 138 C138 116 80 118 98 98', big ? 36 : 34, B);
  b += `<path d="M108 128 Q118 122 120 114" ${s('lightline', 4)}/>`;
  b += `<path d="M58 170 L66 176 M134 176 L142 170 M72 152 L78 156" ${s('line', 2.2)}/>`;
  if (rare) {
    const arc = (cy: number, rx: number, ry: number): number[][] =>
      [25, 50, 75, 100, 125, 150].map((a) => [n(100 + rx * Math.cos((a * Math.PI) / 180)), n(cy + ry * Math.sin((a * Math.PI) / 180))]);
    b += bubbles(c, arc(c1[0], c1[1], c1[2]).concat(arc(c2[0], c2[1], c2[2]), [[104, 116]], big ? [[40, 92], [52, 110], [160, 92], [148, 110]] : []));
  }
  // 머리: 손잡이가 귀/뿔이 된다
  if (big) b += tube('M76 62 C68 34 84 28 90 60', 13, B) + tube('M110 60 C116 28 132 34 124 62', 13, B);
  else b += tube('M76 66 C74 44 90 44 90 66', 12, B) + tube('M110 66 C110 44 126 44 124 66', 12, B);
  const hy = big ? 60 : 64, hx0 = big ? 62 : 66;
  b += `<path d="M${hx0} ${hy} L${200 - hx0} ${hy} L${204 - hx0} ${hy + 36} Q${202 - hx0} 116 100 116 Q${hx0 - 2} 116 ${hx0 - 4} ${hy + 36} Z" ${s('body')}/>`;
  b += `<path d="M${190 - hx0} ${hy + 10} L${196 - hx0} ${hy + 40} Q${194 - hx0} 110 ${188 - hx0} 110 Z" ${s('dark')}/>`;
  b += `<path d="M${hx0} ${hy} L${200 - hx0} ${hy} L${201 - hx0} ${hy + 10} L${hx0 - 1} ${hy + 10} Z" ${s('acc')}/>`;
  b += face(c, 100, big ? 88 : 90, big ? { k: 0.9, gap: 18, eye: 'cool', mouth: 'smirk' } : { k: 0.85, gap: 18, brow: true });
  return b;
};

// ───────────── 전지(에픽): 볼트쥐 → 볼트여우 → 볼트라이온 ─────────────
const BOLT = [[0, 0], [18, -10], [12, -16], [32, -34], [24, -14], [30, -10], [6, 10]];
const battery = (c: Ctx, x0: number, y0: number, y1: number, band: number): string => {
  const s = c.s;
  const x1 = 200 - x0;
  return (
    `<path d="M${x0} ${y0 + 14} Q${x0} ${y0} ${x0 + 14} ${y0} L${x1 - 14} ${y0} Q${x1} ${y0} ${x1} ${y0 + 14} L${x1} ${y1 - 12} Q${x1} ${y1} ${x1 - 14} ${y1} L${x0 + 14} ${y1} Q${x0} ${y1} ${x0} ${y1 - 12} Z" ${s('body')}/>` +
    `<rect x="${x1 - 14}" y="${y0 + 8}" width="8" height="${band - y0 - 14}" rx="4" ${s('dark')}/>` +
    `<path d="M${x0} ${band} L${x1} ${band} L${x1} ${y1 - 12} Q${x1} ${y1} ${x1 - 14} ${y1} L${x0 + 14} ${y1} Q${x0} ${y1} ${x0} ${y1 - 12} Z" ${s('acc')}/>` +
    `<path d="${poly([[-3, -8], [5, -8], [1, -1], [6, -1], [-4, 9], [-1, 1], [-6, 1]], 100, (band + y1) / 2)}" ${s('body', 2.2)}/>`
  );
};

const volt: Draw = (c, st) => {
  const s = c.s;
  let b = '';
  if (st === 1) {
    const ear = `<circle cx="70" cy="68" r="18" ${s('body')}/><circle cx="70" cy="68" r="9" ${s('~ear')}/>`;
    b += ear + mirror(ear);
    b += `<path d="${poly(BOLT, 132, 160, 1.2)}" ${s('body')}/>`;
    b += feet(c, 82, 118, 'acc');
    b += `<rect x="88" y="52" width="24" height="16" rx="4" ${s('acc2')}/>`;
    b += battery(c, 66, 64, 176, 146);
    b += `<rect x="74" y="74" width="6" height="40" rx="3" ${s('light')}/>`;
    const wh = `<path d="M62 114 L46 110 M62 121 L46 123" ${s('line', 2.4)}/>`;
    b += wh + mirror(wh);
    b += face(c, 100, 104, { gap: 16 });
    b += `<ellipse cx="100" cy="112" rx="3.4" ry="2.6" ${s('eye')}/>`;
    return b;
  }
  if (st === 2) {
    const ear = `<path d="M70 80 L62 28 L98 66 Z" ${s('body')}/><path d="M70 70 L66 44 L84 62 Z" ${s('~ear')}/>`;
    b += ear + mirror(ear);
    b += `<path d="${poly(BOLT, 128, 164, 1.8)}" ${s('body')}/><path d="${poly([[24, -14], [32, -34], [18, -22]], 128, 164, 1.8)}" ${s('muz', 3)}/>`;
    b += feet(c, 82, 118, 'acc');
    b += `<rect x="88" y="50" width="24" height="16" rx="4" ${s('acc2')}/>`;
    b += battery(c, 64, 62, 176, 148);
    const tuft = `<path d="M66 108 L48 118 L56 122 L50 130 L66 130 Z" ${s('muz')}/>`;
    b += tuft + mirror(tuft);
    b += `<rect x="72" y="74" width="6" height="40" rx="3" ${s('light')}/>`;
    b += face(c, 100, 100, { gap: 17, brow: true, mouth: 'open' });
    b += `<ellipse cx="100" cy="108" rx="3.4" ry="2.6" ${s('eye')}/>`;
    return b;
  }
  // 3단계 라이온
  b += tube('M134 166 C162 170 170 150 162 134', 11, c.p.body);
  b += `<path d="${poly(BOLT, 150, 138, 0.8)}" ${s('acc', 3.4)}/>`;
  b += battery(c, 66, 124, 178, 154);
  b += `<ellipse cx="82" cy="180" rx="13" ry="8" ${s('body')}/><ellipse cx="118" cy="180" rx="13" ry="8" ${s('body')}/>`;
  b += `<path d="${spiky(100, 84, 60, 46, 12)}" ${s('acc')}/>`;
  b += `<path d="${spiky(100, 84, 49, 40, 12, -Math.PI / 2 + Math.PI / 12)}" ${s('dark', 0)} stroke="#2A2622" stroke-width="3" stroke-linejoin="round"/>`;
  b += `<circle cx="72" cy="54" r="10" ${s('body')}/><circle cx="128" cy="54" r="10" ${s('body')}/>`;
  b += `<rect x="89" y="36" width="22" height="16" rx="4" ${s('acc2')}/>`;
  b += `<circle cx="100" cy="86" r="38" ${s('body')}/>`;
  b += `<path d="M124 60 Q140 84 124 112 Q132 86 124 60 Z" ${s('dark')}/>`;
  b += `<ellipse cx="100" cy="106" rx="17" ry="11" ${s('muz')}/>`;
  b += face(c, 100, 82, { gap: 15, eye: 'cool', mouth: false });
  b += `<path d="M95 99 L105 99 L100 105 Z" ${s('eye')}/>`;
  b += mouth(c, 100, 106, 0.9, moodMouth(c, 'smirk'));
  b += `<circle cx="90" cy="108" r="1.4" ${s('eye')}/><circle cx="110" cy="108" r="1.4" ${s('eye')}/>`;
  return b;
};

// ───────────── 섬유(에픽): 솜뭉치 → 털실양 → 패브릭골렘 ─────────────
const stitchRect = (x: number, y: number, w: number, h: number): string =>
  `<rect x="${x + 4}" y="${y + 4}" width="${w - 8}" height="${h - 8}" rx="3" fill="none" stroke="#2A2622" stroke-width="1.8" stroke-dasharray="4 4" stroke-linecap="round"/>`;
const button = (c: Ctx, x: number, y: number, r: number, role: string): string =>
  `<circle cx="${x}" cy="${y}" r="${r}" ${c.s(role, 3)}/>` +
  [[-1, -1], [1, -1], [-1, 1], [1, 1]].map((d) => `<circle cx="${n(x + d[0] * r * 0.32)}" cy="${n(y + d[1] * r * 0.32)}" r="${n(r * 0.16)}" ${c.s('eye')}/>`).join('');

const fabric: Draw = (c, st) => {
  const s = c.s;
  let b = '';
  if (st === 1) {
    b += feet(c, 82, 118, 'acc');
    b += tube('M144 152 C166 158 172 136 158 134 C150 133 151 144 160 146', 9, c.p.acc, 5);
    b += leaf(s, 100, 82, 22, -140, 'leaf') + leaf(s, 100, 82, 22, -40, 'leaf');
    b += `<path d="${fluff(100, 130, 48, 44, 11, 6, 0.3)}" ${s('body')}/>`;
    b += `<path d="M136 112 Q146 132 134 156 Q140 132 136 112 Z" ${s('dark')}/>`;
    b += `<path d="M70 108 Q72 100 80 98" ${s('lightline', 4)}/>`;
    b += face(c, 100, 126, { gap: 17 });
    return b;
  }
  if (st === 2) {
    [70, 88, 118, 136].forEach((x) => { b += `<rect x="${x - 6}" y="156" width="12" height="28" rx="6" ${s('leg')}/>`; });
    b += tube('M146 142 C170 146 174 124 162 120 C154 118 154 128 162 130', 9, c.p.acc, 5);
    b += `<circle cx="110" cy="126" r="44" ${s('acc')}/>`;
    b += `<path d="M78 100 Q112 90 148 116 M70 122 Q106 112 152 138 M76 148 Q110 136 142 160 M100 84 Q84 118 98 168 M128 88 Q118 120 132 162" ${s('line', 2.2)}/>`;
    b += `<path d="M84 96 Q90 88 100 86" ${s('lightline', 4)}/>`;
    b += rot(-24, 46, 100, `<ellipse cx="46" cy="100" rx="13" ry="7" ${s('skin')}/>`);
    b += rot(24, 92, 98, `<ellipse cx="92" cy="98" rx="13" ry="7" ${s('skin')}/>`);
    b += `<ellipse cx="68" cy="112" rx="24" ry="27" ${s('skin')}/>`;
    b += `<path d="${fluff(68, 86, 19, 10, 7, 4)}" ${s('body')}/>`;
    b += face(c, 68, 114, { k: 0.8, gap: 13 });
    return b;
  }
  // 3단계 골렘
  b += `<rect x="62" y="158" width="32" height="26" rx="7" ${s('body')}/><rect x="106" y="158" width="32" height="26" rx="7" ${s('body')}/>`;
  b += `<rect x="22" y="86" width="32" height="66" rx="14" ${s('acc2')}/><rect x="146" y="86" width="32" height="66" rx="14" ${s('acc3')}/>`;
  b += `<path d="M26 120 L50 120 M150 120 L174 120" stroke="#2A2622" stroke-width="1.8" stroke-dasharray="4 4"/>`;
  b += `<rect x="46" y="70" width="108" height="98" rx="16" ${s('body')}/>`;
  b += `<rect x="134" y="80" width="12" height="78" rx="6" ${s('dark')}/>`;
  b += rot(-4, 72, 92, `<rect x="50" y="74" width="44" height="38" rx="4" ${s('acc')}/>${stitchRect(50, 74, 44, 38)}`);
  b += rot(5, 130, 146, `<rect x="110" y="128" width="40" height="36" rx="4" ${s('acc2')}/>${stitchRect(110, 128, 40, 36)}`);
  b += rot(-6, 72, 148, `<rect x="56" y="132" width="32" height="32" rx="4" ${s('acc3')}/>${stitchRect(56, 132, 32, 32)}`);
  b += button(c, 116, 92, 8, 'acc2') + button(c, 136, 106, 6, 'acc');
  // 머리 + 바늘 + 털실 방울
  b += `<path d="M122 30 L150 22" stroke="#2A2622" stroke-width="8" stroke-linecap="round"/><path d="M122 30 L150 22" stroke="#E6E9EE" stroke-width="3.6" stroke-linecap="round"/><ellipse cx="146" cy="23" rx="2.6" ry="1.4" fill="#2A2622" transform="rotate(-16 146 23)"/>`;
  b += `<rect x="64" y="26" width="72" height="50" rx="13" ${s('body')}/>`;
  b += `<rect x="120" y="32" width="9" height="38" rx="4.5" ${s('dark')}/>`;
  b += `<path d="M64 40 L64 26 L84 26 Z" ${s('acc2', 3.4)}/><path d="M68 66 L132 66" stroke="#2A2622" stroke-width="1.8" stroke-dasharray="4 4"/>`;
  b += `<path d="${fluff(100, 22, 9, 7, 6, 2.4)}" ${s('acc')}/>`;
  b += face(c, 100, 48, { k: 0.85, gap: 15, eye: 'cool', mouth: 'smirk' });
  return b;
};

// ───────────── 전설: 리버스 (재생의 정령) ─────────────
const reverse: Draw = (c) => {
  const s = c.s;
  const cx = 100, cy = 106, R = 74;
  const P = (deg: number, r = R): number[] => [cx + r * Math.cos((deg * Math.PI) / 180), cy + r * Math.sin((deg * Math.PI) / 180)];
  let ring = '';
  let heads = '';
  [0, 120, 240].forEach((a0) => {
    const st = a0 - 52, en = a0 + 44;
    const p0 = P(st), p1 = P(en);
    ring += `M${n(p0[0])} ${n(p0[1])} A${R} ${R} 0 0 1 ${n(p1[0])} ${n(p1[1])} `;
    // 화살촉
    const t = P(en + 12), l = P(en, R - 14), r = P(en, R + 14);
    heads += `<path d="M${n(l[0])} ${n(l[1])} L${n(t[0])} ${n(t[1])} L${n(r[0])} ${n(r[1])} Z" ${s('acc')}/>`;
  });
  let b = tube(ring, 20, c.p.acc, 9) + heads;
  b += `<path d="${ring}" ${s('lightline', 2.6)} stroke-dasharray="2 12"/>`;
  [[-150, 1], [-30, 1], [70, -1]].forEach((q) => {
    const a = q[0];
    const p = P(a, R + 8);
    b += leaf(s, p[0], p[1], 20, a + 60 * q[1], 'leaf');
  });
  // 정령 몸
  b += leaf(s, 64, 128, 22, 160, 'leaf') + leaf(s, 136, 128, 22, 20, 'leaf');
  b += leaf(s, 100, 54, 26, -130, 'leaf') + leaf(s, 100, 54, 26, -50, 'leaf');
  b += `<path d="M100 50 C118 70 140 88 140 116 C140 144 122 160 100 160 C78 160 60 144 60 116 C60 88 82 70 100 50 Z" ${s('body')}/>`;
  b += `<path d="M126 98 Q138 120 126 148 Q132 120 126 98 Z" ${s('dark')}/>`;
  b += `<path d="M74 104 Q72 94 80 84" ${s('lightline', 4)}/>`;
  b += face(c, 100, 116, { gap: 15, mouth: 'smile' });
  return b;
};

// ───────────── 팔레트 & 계열 표 ─────────────
const pal = (body: string, dark: string, acc: string, acc2: string, cheek: string, extra: Record<string, string> = {}): Pal =>
  ({ body, dark, acc, acc2, cheek, ...extra });

const LINES: Record<string, LineDef> = {
  petring: { type: 'plastic', draw: pet, pal: pal('#CFE8F4', '#9AC6DE', '#E5553C', '#2C6BCB', '#F3A0A6'), shiny: pal('#F6E6A2', '#E1C562', '#8E62CF', '#EDAE30', '#F49DB8') },
  colapet: { type: 'plastic', draw: pet, rare: true, pal: pal('#C98C52', '#A26A36', '#D3263B', '#D3263B', '#F3A0A6'), shiny: pal('#F7D3DF', '#E8A9BE', '#7FB8E8', '#E9B03A', '#F49DB8') },
  boxbear: { type: 'paper', draw: box, pal: pal('#C99A62', '#A97A45', '#EBDBBB', '#7E5530', '#E99A86'), shiny: pal('#F6E3A1', '#E2C15F', '#FFF6DC', '#B98AD6', '#F49DB8') },
  parcelbear: { type: 'paper', draw: box, rare: true, pal: pal('#A8764A', '#87582F', '#E2C89A', '#5A3A1E', '#E99A86'), shiny: pal('#F2CDB8', '#DFA78E', '#FFF3E6', '#7FA9D9', '#F49DB8') },
  candol: { type: 'metal', draw: can, pal: pal('#C8CDD5', '#99A1AD', '#D8402F', '#7B8391', '#F0A0A0', { blade: '#EEF1F4', fish: '#5FA3D9' }), shiny: pal('#E9DDF7', '#C9B6E6', '#F2A43A', '#B49BD8', '#F49DB8', { blade: '#FFF6D8', fish: '#F2C14E' }) },
  tunacan: { type: 'metal', draw: can, rare: true, pal: pal('#E9C25A', '#C99A2E', '#3C7FC4', '#B8862A', '#F0A0A0', { blade: '#EEF1F4', fish: '#7FB8E8' }), shiny: pal('#D6EEF0', '#A8D3D8', '#F28CA6', '#7FBFC8', '#F49DB8', { blade: '#FFFFFF', fish: '#F2C14E' }) },
  glassbird: { type: 'glass', draw: glass, pal: pal('#8DCAA1', '#5FA67A', '#C8A46B', '#E8B748', '#F2A39B'), shiny: pal('#BDE6F2', '#8CC7DC', '#E9C7F0', '#F5B841', '#F49DB8') },
  amberbird: { type: 'glass', draw: glass, rare: true, pal: pal('#E0A65E', '#B97B36', '#C9302C', '#F0C04A', '#F2A39B'), shiny: pal('#F5C9D9', '#E39DB8', '#5FB8A8', '#F5B841', '#F49DB8') },
  vinylghost: { type: 'vinyl', draw: vinyl, float: (st) => st !== 2, groundRx: (st) => (st === 2 ? 58 : 40), pal: pal('#F2EFF6', '#D3CBE2', '#6FB5E6', '#6FB5E6', '#F4A7BD'), shiny: pal('#FFF1C9', '#EBD18A', '#F49DB8', '#F49DB8', '#F4A7BD') },
  bubblewrap: { type: 'vinyl', draw: vinyl, rare: true, float: (st) => st !== 2, groundRx: (st) => (st === 2 ? 58 : 40), pal: pal('#DDF0FA', '#B4D9EE', '#7DBDE6', '#7DBDE6', '#F4A7BD'), shiny: pal('#E8F7E4', '#BFE3B6', '#F09ABD', '#F09ABD', '#F4A7BD') },
  voltmouse: { type: 'volt', draw: volt, sparkles: [[36, 60, 9], [166, 52, 7], [40, 150, 5]], pal: pal('#FFD43B', '#E8B620', '#3A3632', '#C8CDD5', '#F49A8C', { ear: '#F49A8C', muz: '#FFF4CC' }), shiny: pal('#BFE9FF', '#8FCCEB', '#5B4A9E', '#E8ECF2', '#F49DB8', { ear: '#F49DB8', muz: '#FFFFFF' }) },
  fabricsheep: { type: 'fabric', draw: fabric, pal: pal('#FFF8F0', '#EBD9CF', '#C2577A', '#6FA8C8', '#F3A0A6', { acc3: '#F2C14E', leaf: '#7CC46A', skin: '#FBE3D2', leg: '#5A4E48' }), shiny: pal('#F4F0FF', '#D9CFF2', '#5FB8A8', '#F5A6C4', '#F49DB8', { acc3: '#FFE08A', leaf: '#F5A6C4', skin: '#FFF1E0', leg: '#8E7BB8' }) },
  reverse: { type: 'plastic', draw: reverse, stages: 1, float: () => true, groundRx: () => 50, sparkles: [[28, 30, 8], [176, 40, 6], [172, 172, 5]], pal: pal('#E6F6EC', '#BFE3CB', '#3FA66B', '#F2C94C', '#F3A0A6', { leaf: '#8BCB63' }), shiny: pal('#FFF6D8', '#EFD9A0', '#E9A93A', '#F2C94C', '#F49DB8', { leaf: '#F2A9C4' }) },
};

/** 계열 -> 타입 (전설 reverse 는 타입 없음: 'plastic' 은 자리채움) */
export const REMON_LINE_TYPE: Record<string, RemonType | 'legend'> = Object.fromEntries(
  Object.keys(LINES).map((k) => [k, k === 'reverse' ? 'legend' : LINES[k].type]),
);

export const REMON_ART_KEYS: string[] = Object.keys(LINES).flatMap((k) => {
  const ns = LINES[k].stages ?? 3;
  return Array.from({ length: ns }, (_, i) => `${k}_${i + 1}`);
});

export function renderRemon(artKey: string, opts: RemonOpts = {}): string {
  const m = /^([a-z]+)_([123])$/.exec(artKey);
  const def = m ? LINES[m[1]] : undefined;
  const st = (m ? Number(m[2]) : 1) as Stage;
  if (!def || st > (def.stages ?? 3)) {
    // 알 수 없는 키: 회색 실루엣
    return stickerSvg(`<path d="${fluff(100, 120, 50, 54, 9, 4)}" fill="#C9CCC6" stroke="#2A2622" stroke-width="4.5"/>`);
  }
  const c = ctx(opts.shiny ? def.shiny : def.pal, opts.mood ?? 'normal');
  let inner = def.draw(c, st, !!def.rare);
  if (opts.shiny) inner += stars(c.s, def.sparkles ?? DEFAULT_SPARKS);
  const float = def.float ? def.float(st) : false;
  return stickerSvg(scaleFrom(STAGE_SCALE[st], inner), {
    float,
    groundRx: def.groundRx ? def.groundRx(st) : 44,
    label: artKey,
  });
}
