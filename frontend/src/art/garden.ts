// 홈 화면 정원 (계정 레벨): 1 씨앗 / 2 새싹 / 3 나무 / 4 숲. dim = 동네가 더러울 때.

import { Ctx, Pal, ctx, face, fluff, tube, leaf, poly, rot, n } from './core';

export type GardenStage = 1 | 2 | 3 | 4;
export type GardenMood = 'bright' | 'dim';

const GP: Record<GardenMood, Pal> = {
  bright: {
    body: '#6FBF5A', dark: '#4F9C45', acc: '#9A6A3E', acc2: '#A97A45', cheek: '#F3A0A6',
    sky: '#DCEFF5', far: '#BFE3A9', hill: '#9ED07C', hill2: '#8BC36B', seed: '#C99A62', seedd: '#A97A45',
    flower: '#F49DB8', flower2: '#FFD447', pine: '#4FA05A', sun: '#FFD447', cloud: '#FFFFFF', fruit: '#E5553C', stem: '#5DAF4E',
  },
  dim: {
    body: '#8E9F82', dark: '#76866C', acc: '#7E6B58', acc2: '#8C7966', cheek: '#D7A9AA',
    sky: '#D6D9D7', far: '#B9BFB2', hill: '#A6AE9A', hill2: '#979F8B', seed: '#A08B72', seedd: '#87735D',
    flower: '#C3A6AD', flower2: '#CFC491', pine: '#7D8F76', sun: '#E3DDB9', cloud: '#A4A8AB', fruit: '#B78279', stem: '#83957A',
  },
};

const BASE = 152; // 주인공 식물 바닥 높이
const CX = 180;

function mound(c: Ctx, x: number, w: number): string {
  return `<path d="M${x - w} ${BASE + 4} C${x - w * 0.7} ${BASE - 26} ${x + w * 0.7} ${BASE - 26} ${x + w} ${BASE + 4} Z" ${c.s('acc2')}/>` +
    `<path d="M${x - w * 0.5} ${BASE - 6} L${x - w * 0.36} ${BASE - 2} M${x + w * 0.3} ${BASE - 8} L${x + w * 0.44} ${BASE - 3}" ${c.s('line', 2.2)}/>`;
}

function seed(c: Ctx, x: number, y: number, k: number, dim: boolean): string {
  const s = c.s;
  return rot(-10, x, y,
    `<ellipse cx="${x}" cy="${y}" rx="${17 * k}" ry="${21 * k}" ${s('seed')}/>` +
    `<path d="M${n(x + 9 * k)} ${n(y - 12 * k)} Q${n(x + 16 * k)} ${y} ${n(x + 9 * k)} ${n(y + 14 * k)} Q${n(x + 12 * k)} ${y} ${n(x + 9 * k)} ${n(y - 12 * k)} Z" ${s('~seedd')}/>` +
    `<path d="M${n(x - 8 * k)} ${n(y - 12 * k)} Q${n(x - 10 * k)} ${n(y - 6 * k)} ${n(x - 11 * k)} ${n(y - 2 * k)}" ${s('lightline', 3)}/>`) +
    gface(c, x, y + 2 * k, 0.42 * k, dim);
}

function gface(c: Ctx, x: number, y: number, k: number, dim: boolean): string {
  return face(c, x, y, dim ? { k, gap: 16, brow: 'sad', mouth: 'frown' } : { k, gap: 16, mouth: 'smile' });
}

function roundTree(c: Ctx, x: number, base: number, h: number, r: number, faceK: number, dim: boolean): string {
  const s = c.s;
  const cy = base - h;
  let o = `<path d="M${x - r * 0.2} ${base} L${x - r * 0.1} ${cy + r * 0.4} L${x + r * 0.1} ${cy + r * 0.4} L${x + r * 0.2} ${base} Z" ${s('acc')}/>`;
  o += `<path d="${fluff(x, cy, r, r * 0.78, 9, r * 0.1, 0.2)}" ${s('body')}/>`;
  o += `<path d="M${x + r * 0.62} ${cy - r * 0.4} Q${x + r * 0.95} ${cy} ${x + r * 0.6} ${cy + r * 0.5} Q${x + r * 0.75} ${cy} ${x + r * 0.62} ${cy - r * 0.4} Z" ${s('dark')}/>`;
  o += `<path d="M${x - r * 0.62} ${cy - r * 0.1} Q${x - r * 0.6} ${cy - r * 0.45} ${x - r * 0.3} ${cy - r * 0.6}" ${s('lightline', 4)}/>`;
  if (faceK > 0) o += gface(c, x, cy + 2, faceK, dim);
  return o;
}

function pineTree(c: Ctx, x: number, base: number, h: number): string {
  const s = c.s;
  const w = h * 0.42;
  let o = `<rect x="${x - 4}" y="${base - 14}" width="8" height="14" rx="2" ${s('acc', 3.4)}/>`;
  [0, 1, 2].forEach((i) => {
    const yb = base - 10 - i * h * 0.26;
    const ww = w * (1 - i * 0.22);
    o += `<path d="M${n(x - ww)} ${n(yb)} L${x} ${n(yb - h * 0.42)} L${n(x + ww)} ${n(yb)} Z" ${s('pine', 3.6)}/>`;
  });
  return o;
}

function flower(c: Ctx, x: number, y: number, role: string): string {
  const s = c.s;
  let o = `<path d="M${x} ${y + 12} L${x} ${y}" ${s('line', 2.4)}/>`;
  [0, 72, 144, 216, 288].forEach((a) => {
    const r = (a * Math.PI) / 180;
    o += `<circle cx="${n(x + 4.6 * Math.cos(r))}" cy="${n(y + 4.6 * Math.sin(r))}" r="3.6" ${s(role, 2)}/>`;
  });
  return o + `<circle cx="${x}" cy="${y}" r="2.6" ${s('flower2', 1.6)}/>`;
}

function litter(c: Ctx): string {
  const s = c.s;
  let o = '';
  // 누운 캔
  o += rot(-12, 84, 172, `<rect x="70" y="164" width="30" height="17" rx="4" ${s('#B7BCC3', 3.2)}/><rect x="80" y="164" width="9" height="17" ${s('#B07A70', 2.6)}/>`);
  // 누운 페트병
  o += rot(8, 268, 170, `<path d="M250 164 L278 164 Q284 164 288 168 L294 168 L294 174 L288 174 Q284 178 278 178 L250 178 Q246 178 246 171 Q246 164 250 164 Z" ${s('#C6D3D8', 3.2)}/><rect x="258" y="164" width="12" height="14" ${s('#B88F86', 2.6)}/>`);
  // 비닐 조각, 과자 봉지
  o += `<path d="${poly([[-12, -4], [-4, -9], [6, -6], [12, 2], [4, 7], [-8, 6]], 322, 178)}" ${s('#D9D6DF', 3)}/><path d="M316 176 L324 180" ${s('line', 2)}/>`;
  o += `<path d="M132 180 L146 176 L150 184 L136 188 Z" ${s('#C7B37E', 3)}/><path d="M130 179 L133 189 M147 175 L151 185" ${s('line', 2)}/>`;
  return o;
}

function sky(c: Ctx, dim: boolean): string {
  const s = c.s;
  if (!dim) {
    let o = `<circle cx="318" cy="40" r="17" ${s('sun', 3.6)}/>`;
    for (let i = 0; i < 8; i++) {
      const a = (i * Math.PI) / 4;
      o += `<path d="M${n(318 + 24 * Math.cos(a))} ${n(40 + 24 * Math.sin(a))} L${n(318 + 30 * Math.cos(a))} ${n(40 + 30 * Math.sin(a))}" ${s('line', 3)}/>`;
    }
    o += `<path d="${fluff(70, 42, 26, 11, 7, 3.5, 0.4)}" ${s('cloud', 3.4)}/>`;
    o += `<path d="${fluff(206, 28, 17, 7, 6, 2.6, 0.4)}" ${s('cloud', 3)}/>`;
    return o;
  }
  return `<circle cx="324" cy="34" r="15" ${s('sun', 3.4)}/>` +
    `<path d="${fluff(298, 46, 30, 13, 8, 4, 0.3)}" ${s('cloud', 3.6)}/>` +
    `<path d="M282 50 Q298 56 316 50" ${s('line', 2.2)}/>`;
}

export function renderGarden(stage: GardenStage, mood: GardenMood): string {
  const dim = mood === 'dim';
  const c = ctx(GP[mood]);
  const p = c.p;
  const s = c.s;
  let bg = `<rect width="360" height="200" rx="18" fill="${p.sky}"/>`;
  bg += `<path d="M0 124 Q50 98 110 118 Q170 136 230 112 Q300 90 360 116 L360 160 L0 160 Z" fill="${p.far}"/>`;
  bg += `<path d="M0 146 Q90 132 180 144 Q270 154 360 138 L360 182 Q360 200 342 200 L18 200 Q0 200 0 182 Z" fill="${p.hill}"/>`;
  bg += `<path d="M0 176 Q120 168 220 178 Q300 184 360 172 L360 182 Q360 200 342 200 L18 200 Q0 200 0 182 Z" fill="${p.hill2}"/>`;

  let plant = '';
  if (stage === 1) {
    plant += mound(c, CX, 54) + seed(c, CX, BASE - 22, 1, dim);
  } else if (stage === 2) {
    plant += mound(c, CX, 50);
    plant += tube(`M${CX} ${BASE - 14} C${CX + 2} ${BASE - 34} ${CX - 4} ${BASE - 46} ${CX} ${BASE - 60}`, 11, p.stem, 6);
    plant += leaf(s, CX, BASE - 58, 36, -160, 'body') + leaf(s, CX, BASE - 60, 40, -24, 'body');
    plant += seed(c, CX, BASE - 10, 0.85, dim);
  } else {
    if (stage === 4) {
      plant += pineTree(c, 62, BASE - 6, 82) + roundTree(c, 116, BASE - 4, 62, 30, 0, dim);
      plant += roundTree(c, 252, BASE - 4, 58, 28, 0, dim) + pineTree(c, 304, BASE - 8, 90);
      plant += `<path d="${fluff(26, BASE + 4, 18, 10, 6, 3, 3.3)}" ${s('dark', 0)} stroke="#2A2622" stroke-width="3.6"/>`;
      plant += `<path d="${fluff(340, BASE + 2, 16, 9, 6, 3, 3.3)}" ${s('dark', 0)} stroke="#2A2622" stroke-width="3.6"/>`;
    }
    const r = stage === 4 ? 52 : 48;
    plant += roundTree(c, CX, BASE, stage === 4 ? 80 : 74, r, 0.62, dim);
    if (!dim) plant += [[-30, -86], [24, -96], [36, -70], [-18, -110]].map((q) => `<circle cx="${CX + q[0]}" cy="${BASE + q[1]}" r="5" ${s('fruit', 2.6)}/>`).join('');
    plant += flower(c, 128, BASE + 2, 'flower') + flower(c, 232, BASE + 4, 'flower2');
    if (stage === 4) plant += flower(c, 88, BASE + 16, 'flower2') + flower(c, 282, BASE + 14, 'flower') + flower(c, 210, BASE + 22, 'flower');
  }
  // 풀
  const grass = [[40, 170], [150, 186], [226, 172], [300, 188], [100, 160]]
    .map((g) => `<path d="M${g[0] - 5} ${g[1]} L${g[0] - 7} ${g[1] - 8} M${g[0]} ${g[1]} L${g[0]} ${g[1] - 10} M${g[0] + 5} ${g[1]} L${g[0] + 7} ${g[1] - 8}" stroke="${p.dark}" stroke-width="2.6" stroke-linecap="round"/>`).join('');

  const stk = (inner: string): string => `<g filter="url(#rc-stk-m)"><g filter="url(#rc-wob)">${inner}</g></g>`;
  return (
    `<svg viewBox="0 0 360 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="garden-${stage}-${mood}">` +
    bg + grass + stk(sky(c, dim)) +
    `<ellipse cx="${CX}" cy="${BASE + 8}" rx="${stage >= 3 ? 60 : 50}" ry="6" fill="#000000" fill-opacity=".1"/>` +
    stk(plant) + (dim ? stk(litter(c)) : '') +
    '</svg>'
  );
}
