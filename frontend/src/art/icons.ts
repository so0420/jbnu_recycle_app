// 64x64 아이콘: 재료, 재화, 캡슐, 타입 문장, 기타 UI.

import { Pal, S, RemonType, REMON_TYPES, TYPE_COLORS, styler, star, rot, tube, poly, fluff, leaf, spiky, n } from './core';

const K = 0.62; // 64 좌표계용 선 굵기 배율
const PAL: Pal = { body: '#FFFFFF', dark: '#000000', acc: '#FFFFFF', acc2: '#FFFFFF', cheek: '#F3A0A6' };
const s: S = styler(PAL, K);
const shade = (d: string): string => `<path d="${d}" fill="#000000" fill-opacity=".14"/>`;

/** 타입별 연한 색 (캡슐 위쪽, 재료) */
const LIGHT: Record<RemonType, string> = {
  plastic: '#7FB0EE', paper: '#D9B07A', metal: '#C3C9D2', glass: '#7CC79A', vinyl: '#B79BDF', volt: '#FFD43B', fabric: '#EC8FAE',
};

function bottle(x: number, y: number, k: number, fill: string, cap: string): string {
  const P = (dx: number, dy: number): string => `${n(x + dx * k)} ${n(y + dy * k)}`;
  return `<path d="M${P(-3, -16)} L${P(3, -16)} L${P(3, -12)} Q${P(8, -10)} ${P(8, -4)} L${P(8, 14)} Q${P(8, 16)} ${P(6, 16)} L${P(-6, 16)} Q${P(-8, 16)} ${P(-8, 14)} L${P(-8, -4)} Q${P(-8, -10)} ${P(-3, -12)} Z" ${s(fill, 3)}/>` +
    `<rect x="${n(x - 4 * k)}" y="${n(y - 20 * k)}" width="${n(8 * k)}" height="${n(5 * k)}" rx="1" ${s(cap, 3)}/>`;
}

/** 묶은 쓰레기 봉투 (중심 x,y) */
function trashBag(x: number, y: number, k: number, fill: string): string {
  const P = (dx: number, dy: number): string => `${n(x + dx * k)} ${n(y + dy * k)}`;
  return `<path d="M${P(-13, -8)} Q${P(-20, 6)} ${P(-15, 18)} Q${P(0, 25)} ${P(15, 18)} Q${P(20, 6)} ${P(13, -8)} Z" ${s(fill)}/>` +
    shade(`M${P(8, -6)} Q${P(18, 6)} ${P(13, 18)} Q${P(9, 21)} ${P(4, 22)} Q${P(12, 8)} ${P(8, -6)} Z`) +
    `<path d="M${P(-9, -8)} L${P(-6, -19)} L${P(0, -12)} L${P(6, -19)} L${P(9, -8)} Z" ${s(fill, 2.6)}/>` +
    `<path d="M${P(-10, 0)} Q${P(-9, -4)} ${P(-5, -5)}" ${s('lightline', 3.2)}/>` +
    `<path d="M${P(-4, 10)} L${P(2, 6)} M${P(5, 15)} L${P(9, 11)}" ${s('line', 2)}/>`;
}

/** 타입 문장 안의 흰 상징 (중심 32,32) */
const SYMBOL: Record<RemonType, () => string> = {
  plastic: () => bottle(32, 34, 0.95, '#FFFFFF', '#FFFFFF'),
  paper: () => `<rect x="20" y="24" width="24" height="20" rx="2" ${s('#FFFFFF', 3)}/><path d="M20 30 L44 30" ${s('line', 2.6)}/><rect x="29" y="24" width="6" height="6" ${s('#FFFFFF', 2.4)}/>`,
  metal: () => `<rect x="23" y="18" width="18" height="28" rx="3" ${s('#FFFFFF', 3)}/><ellipse cx="32" cy="19" rx="9" ry="2.6" ${s('#FFFFFF', 2.6)}/><path d="M23 36 L41 36" ${s('line', 2.6)}/>`,
  glass: () => `<path d="M32 17 L45 29 L32 48 L19 29 Z" ${s('#FFFFFF', 3)}/><path d="M19 29 L45 29 M27 29 L32 47 M37 29 L32 47" ${s('line', 2)}/>`,
  vinyl: () => tube('M26 24 C25 15 31 15 30 24', 6, '#FFFFFF', 4) + tube('M34 24 C33 15 39 15 38 24', 6, '#FFFFFF', 4) + `<path d="M21 23 L43 23 L45 46 Q32 50 19 46 Z" ${s('#FFFFFF', 3)}/>`,
  volt: () => `<path d="${poly([[-4, -16], [9, -16], [3, -3], [10, -3], [-6, 17], [-2, 3], [-9, 3]], 32, 32)}" ${s('#FFFFFF', 3)}/>`,
  fabric: () => `<circle cx="32" cy="32" r="13" ${s('#FFFFFF', 3)}/><circle cx="32" cy="32" r="9" ${s('line', 1.8)}/>` +
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].map((d) => `<circle cx="${32 + d[0] * 3.6}" cy="${32 + d[1] * 3.6}" r="1.9" ${s('eye')}/>`).join(''),
};

const ICONS: Record<string, () => string> = {
  mat_plastic: () =>
    `<path d="${poly([[-10, -4], [-2, -12], [10, -8], [12, 4], [2, 10], [-8, 8]], 22, 24)}" ${s('#CFE8F4')}/>` +
    `<path d="${poly([[-18, -6], [-4, -18], [14, -14], [18, 6], [6, 18], [-14, 14]], 36, 38)}" ${s(LIGHT.plastic)}/>` +
    shade(poly([[18, 6], [6, 18], [-2, 10], [10, 2]], 36, 38)) + `<path d="M26 32 L32 26" ${s('lightline', 4)}/>`,
  mat_paper: () =>
    `<path d="${fluff(22, 40, 11, 9, 6, 2.4)}" ${s('#EBDBBB')}/>` +
    `<path d="${fluff(36, 34, 18, 15, 8, 3)}" ${s(LIGHT.paper)}/>` +
    `<path d="M26 30 q4 -4 8 0 t8 0 M28 40 q4 -4 8 0 t8 0" ${s('line', 2.4)}/>`,
  mat_metal: () =>
    `<path d="M8 36 L56 36 L56 48 Q56 50 54 50 L10 50 Q8 50 8 48 Z" ${s('#99A1AD')}/>` +
    `<path d="M16 20 L48 20 L56 36 L8 36 Z" ${s(LIGHT.metal)}/>` +
    `<path d="M20 26 L34 26" ${s('lightline', 4)}/><path d="M48 40 L48 46" ${s('lightline', 3)}/>`,
  mat_glass: () =>
    `<path d="M36 54 L46 24 L56 54 Z" ${s('#A9DDBA')}/>` +
    `<path d="M10 54 L26 8 L40 54 Z" ${s(LIGHT.glass)}/>` + shade('M26 8 L40 54 L30 54 Z') +
    `<path d="M20 42 L25 22" ${s('lightline', 3.6)}/>`,
  mat_vinyl: () =>
    `<path d="M14 16 Q24 10 34 16 T54 16 L54 38 Q44 44 34 38 T14 38 Z" ${s('#E4DAF3')}/>` +
    `<path d="M10 26 Q21 18 32 26 T52 26 L52 50 Q41 58 32 50 T10 50 Z" ${s(LIGHT.vinyl)}/>` +
    `<path d="M24 26 L22 50 M40 28 L42 50" ${s('line', 2)}/><path d="M14 32 Q18 29 22 30" ${s('lightline', 3.6)}/>`,
  mat_volt: () =>
    `<path d="${spiky(32, 32, 24, 24, 3, -Math.PI / 2)}" ${s(LIGHT.volt)}/>` +
    `<path d="${spiky(32, 32, 15, 15, 3, -Math.PI / 2)}" ${s('#E8B620', 2.6)}/>` +
    `<path d="${poly([[-3, -11], [6, -11], [2, -2], [7, -2], [-4, 12], [-1, 2], [-6, 2]], 32, 32)}" ${s('#FFFFFF', 2.6)}/>`,
  mat_fabric: () =>
    tube('M44 40 C56 42 58 54 48 54 C42 54 44 48 50 48', 6, LIGHT.fabric, 3.6) +
    `<rect x="14" y="8" width="32" height="8" rx="3" ${s('#C99A62')}/><rect x="14" y="48" width="32" height="8" rx="3" ${s('#C99A62')}/>` +
    `<rect x="18" y="16" width="24" height="32" ${s(LIGHT.fabric)}/>` +
    `<path d="M18 22 L42 26 M18 30 L42 34 M18 38 L42 42" ${s('line', 1.8)}/>`,
  crystal: () =>
    `<path d="M32 6 L46 20 L46 44 L32 58 L18 44 L18 20 Z" ${s('#8EE0CC')}/>` +
    shade('M32 6 L46 20 L46 44 L32 58 Z') +
    `<path d="M18 20 L32 28 L46 20 M32 28 L32 58" ${s('line', 2)}/>` +
    `<path d="M23 24 L23 38" ${s('lightline', 3.6)}/>` + star(s, 50, 10, 5),
  coin: () =>
    `<circle cx="32" cy="33" r="23" ${s('#F2C14E')}/><circle cx="32" cy="33" r="16" ${s('line', 2)}/>` +
    shade('M48 18 A23 23 0 0 1 32 56 A20 20 0 0 0 48 18 Z') +
    leaf(s, 22, 42, 22, -50, '#D99A2B') + `<path d="M18 22 Q22 16 28 14" ${s('lightline', 3.6)}/>`,
  ticket: () =>
    rot(-12, 32, 32,
      `<path d="M8 20 L56 20 L56 28 A4 4 0 0 0 56 36 L56 44 L8 44 L8 36 A4 4 0 0 0 8 28 Z" ${s('#F2836B')}/>` +
      `<path d="M42 22 L42 42" stroke="#FFFFFF" stroke-width="2.6" stroke-dasharray="3 3"/>` +
      `<path d="M14 25 L36 25" ${s('lightline', 2.6)}/>` + star(s, 25, 33, 7) + `<circle cx="49" cy="32" r="3" fill="#FFFFFF"/>`),
  bag: () =>
    tube('M22 26 C22 8 42 8 42 26', 8, '#3E8E5A', 5) +
    `<path d="M10 24 L54 24 L50 56 L14 56 Z" ${s('#4FA36B')}/>` + shade('M44 24 L54 24 L50 56 L42 56 Z') +
    `<rect x="20" y="34" width="22" height="16" rx="3" ${s('#8BCB63', 2.6)}/>` + leaf(s, 25, 46, 14, -45, '#FFFFFF'),
  stamp: () =>
    `<circle cx="44" cy="48" r="13" fill="none" stroke="#3FA66B" stroke-width="3" stroke-dasharray="5 3"/>` +
    rot(-14, 28, 30,
      `<rect x="10" y="36" width="36" height="8" rx="2" ${s('#E4473A')}/>` +
      `<rect x="13" y="28" width="30" height="9" rx="3" ${s('#C99A62')}/>` +
      `<rect x="24" y="14" width="8" height="15" ${s('#C99A62')}/><circle cx="28" cy="11" r="7" ${s('#C99A62')}/>` +
      `<path d="M25 8 Q27 6 30 6" ${s('lightline', 2.4)}/>`),
  raid: () =>
    `<path d="${spiky(32, 32, 14, 7, 6)}" ${s('#FFD447', 2.6)}/>` +
    rot(42, 32, 32, bottle(32, 33, 1.45, '#CFE8F4', '#2C6BCB') + `<rect x="21" y="34" width="22" height="8" ${s('#E5553C', 2.6)}/>`) +
    rot(-42, 32, 32, `<rect x="25" y="8" width="14" height="48" rx="4" ${s('#C8CDD5')}/><ellipse cx="32" cy="9" rx="7" ry="2.4" ${s('#7B8391', 2.4)}/><rect x="25" y="34" width="14" height="10" ${s('#D8402F', 2.6)}/>`),
  // ── 지역 공방전: 공격권과 던지는 쓰레기 ──
  attack: () =>
    `<path d="M5 28 L15 28 M3 37 L14 37 M7 46 L16 46" ${s('line', 3.4)}/>` +
    rot(-18, 38, 36, trashBag(38, 38, 0.9, '#5E6E64')) + star(s, 54, 12, 5),
  trash_bag: () => trashBag(32, 34, 1, '#4E5F55'),
  clean_spark: () =>
    `<path d="${spiky(30, 34, 22, 8, 4, -Math.PI / 2)}" ${s('#BFF0D4')}/>` +
    `<path d="${spiky(30, 34, 11, 4, 4, -Math.PI / 4)}" fill="#FFFFFF"/>` + star(s, 50, 14, 6) + star(s, 52, 46, 4),
  trash_bottle: () =>
    rot(-24, 32, 32, bottle(32, 34, 1.3, '#CFE8F4', '#2C6BCB') + `<rect x="22" y="32" width="20" height="9" ${s('#E5553C', 2.6)}/>` +
      `<path d="M24 46 L30 50 M36 22 L40 26" ${s('line', 2)}/>` + `<path d="M26 24 L26 30" ${s('lightline', 3)}/>`),
  trash_can: () =>
    rot(16, 32, 32,
      `<path d="M22 14 L42 14 L44 26 L38 32 L44 40 L42 52 L22 52 L20 40 L26 32 L20 26 Z" ${s('#C8CDD5')}/>` +
      `<ellipse cx="32" cy="14" rx="10" ry="3" ${s('#7B8391', 2.4)}/>` +
      `<path d="M21 40 L43 40 L42 46 L22 46 Z" ${s('#D8402F', 2.4)}/>` +
      `<path d="M26 32 L38 32" ${s('line', 2.2)}/>` + `<path d="M26 20 L25 26" ${s('lightline', 3)}/>`),
  trash_box: () =>
    rot(-10, 32, 34,
      `<path d="M12 24 L52 24 L50 54 L14 54 Z" ${s('#D9B07A')}/>` + shade('M42 24 L52 24 L50 54 L40 54 Z') +
      `<path d="M12 24 L4 14 L26 14 L32 24 M52 24 L60 14 L38 14 L32 24" ${s('#C99A62', 2.6)}/>` +
      `<rect x="28" y="24" width="8" height="12" ${s('#F2E2C0', 2.2)}/>` + `<path d="M18 46 L28 44" ${s('line', 2)}/>`),
  trash_peel: () =>
    `<path d="M32 30 C22 34 14 44 12 54 C20 48 26 42 32 38 C38 42 44 48 52 54 C50 44 42 34 32 30 Z" ${s('#F2D24B')}/>` +
    `<path d="M32 38 C30 46 30 52 32 58 C34 52 34 46 32 38 Z" ${s('#E8B620', 2.4)}/>` +
    `<path d="M28 30 Q30 18 34 10 L38 12 Q36 22 36 30 Z" ${s('#E8C33A', 2.6)}/>` + `<rect x="33" y="6" width="6" height="6" rx="2" ${s('#6B5A2E', 2.2)}/>`,
  map_pin: () =>
    `<path d="M32 58 C22 44 12 36 12 25 A20 20 0 0 1 52 25 C52 36 42 44 32 58 Z" ${s('#3FA66B')}/>` +
    shade('M42 8 A20 20 0 0 1 52 25 C52 36 42 44 32 58 C38 44 46 34 42 8 Z') +
    `<circle cx="32" cy="25" r="10" ${s('#FFFFFF', 2.6)}/>` + leaf(s, 26, 30, 13, -50, '#8BCB63'),
};

REMON_TYPES.forEach((t) => {
  // 세로로 긴 뽑기 캡슐: 위는 투명 돔(안에 잎사귀 장난감), 아래는 타입 색
  ICONS['capsule_' + t] = () =>
    rot(-14, 32, 33,
      `<path d="M14 31 Q14 7 32 7 Q50 7 50 31 Z" ${s('#E8F3F6')}/>` +
      leaf(s, 24, 28, 17, -40, TYPE_COLORS[t]) +
      `<path d="M14 33 L50 33 Q50 57 32 57 Q14 57 14 33 Z" ${s(TYPE_COLORS[t])}/>` +
      shade('M40 34 L50 34 Q50 55 34 57 Q46 50 40 34 Z') +
      `<rect x="11" y="28" width="42" height="7" rx="3" ${s(LIGHT[t], 2.6)}/>` +
      `<path d="M20 22 Q21 15 27 12" ${s('lightline', 3.6)}/><path d="M20 44 Q22 49 26 51" ${s('lightline', 2.6)}/>`);
  ICONS['type_' + t] = () => `<circle cx="32" cy="32" r="24" ${s(TYPE_COLORS[t])}/>` + SYMBOL[t]();
});

export const ICON_KEYS: string[] = Object.keys(ICONS);

export function renderIcon(key: string): string {
  const fn = ICONS[key];
  const inner = fn ? fn() : `<circle cx="32" cy="32" r="22" ${s('#C9CCC6')}/>`;
  return `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${key}"><g filter="url(#rc-stk-s)"><g filter="url(#rc-wob-s)">${inner}</g></g></svg>`;
}
