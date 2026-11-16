// 스티커 그림체 공용 도구: 역할(role) 기반 색칠, 얼굴, 별, 튜브, 감싸기.
// 모든 그림은 같은 styler/face 를 써서 선 굵기·눈·볼을 통일한다.

export const LINE = '#2A2622';
export const RED_EYE = '#E4473A';

export const TYPE_COLORS = {
  plastic: '#2C6BCB',
  paper: '#A97A45',
  metal: '#7B8391',
  glass: '#2E7D4F',
  vinyl: '#7A55B0',
  volt: '#D9A400',
  fabric: '#C2577A',
} as const;
export type RemonType = keyof typeof TYPE_COLORS;
export const REMON_TYPES: RemonType[] = ['plastic', 'paper', 'metal', 'glass', 'vinyl', 'volt', 'fabric'];

export type Mood = 'normal' | 'hurt' | 'happy';

/** 팔레트: 필수 역할 + 그림마다 필요한 추가 역할 */
export interface Pal {
  body: string;
  dark: string;
  acc: string;
  acc2: string;
  cheek: string;
  [role: string]: string;
}

/** role -> SVG 속성 문자열. w 는 선 굵기(덮어쓰기) */
export type S = (role: string, w?: number) => string;

export interface Ctx {
  s: S;
  p: Pal;
  mood: Mood;
}

export const n = (v: number): number => Math.round(v * 100) / 100;

/**
 * 역할 규칙
 * line / lightline : 선만
 * eye / hi / light / cheek / dark : 외곽선 없는 납작한 칠
 * spark : 노란 반짝 별
 * '~이름' : 외곽선 없이 팔레트 색(또는 '#hex')
 * 그 밖 : 팔레트 색(또는 '#hex') + 굵은 외곽선
 */
export function styler(pal: Pal, k = 1): S {
  const sw = n(4.5 * k);
  return (role: string, w?: number): string => {
    if (role === 'line')
      return `fill="none" stroke="${LINE}" stroke-width="${n((w ?? 3.6) * k)}" stroke-linecap="round" stroke-linejoin="round"`;
    if (role === 'lightline')
      return `fill="none" stroke="#FFFFFF" stroke-opacity=".85" stroke-width="${n((w ?? 5) * k)}" stroke-linecap="round"`;
    if (role === 'eye') return `fill="${LINE}"`;
    if (role === 'hi') return 'fill="#FFFFFF"';
    if (role === 'light') return 'fill="#FFFFFF" fill-opacity=".8"';
    if (role === 'cheek') return `fill="${pal.cheek}" fill-opacity=".9"`;
    if (role === 'dark') return `fill="${pal.dark}"`;
    if (role === 'spark') return `fill="#FFD447" stroke="${LINE}" stroke-width="${n(sw * 0.7)}" stroke-linejoin="round"`;
    if (role.charAt(0) === '~') {
      const r = role.slice(1);
      return `fill="${pal[r] ?? r}"`;
    }
    const sww = w !== undefined ? n(w * k) : sw;
    return `fill="${pal[role] ?? role}" stroke="${LINE}" stroke-width="${sww}" stroke-linejoin="round"`;
  };
}

export function ctx(pal: Pal, mood: Mood = 'normal', k = 1): Ctx {
  return { s: styler(pal, k), p: pal, mood };
}

export type MouthKind = 'smile' | 'smirk' | 'open' | 'frown' | 'wavy' | 'flat';

/** 기분이 입 모양을 덮어쓴다 */
export function moodMouth(c: Ctx, kind: MouthKind): MouthKind {
  if (c.mood === 'hurt') return 'wavy';
  if (c.mood === 'happy') return 'open';
  return kind;
}

/** yb: 입 윗선 높이 */
export function mouth(c: Ctx, x: number, yb: number, k: number, kind: MouthKind): string {
  const s = c.s;
  const lw = 3.6 * Math.max(k, 0.6);
  const X = (d: number): number => n(x + d * k);
  const Y = (d: number): number => n(yb + d * k);
  switch (kind) {
    case 'open':
      return `<path d="M${X(-7)} ${Y(-1)} Q${X(0)} ${Y(10)} ${X(7)} ${Y(-1)} Z" ${s('eye')}/>`;
    case 'smirk':
      return `<path d="M${X(-5)} ${Y(1)} Q${X(2)} ${Y(5)} ${X(8)} ${Y(-2)}" ${s('line', lw)}/>`;
    case 'frown':
      return `<path d="M${X(-6)} ${Y(5)} Q${X(0)} ${Y(-1)} ${X(6)} ${Y(5)}" ${s('line', lw)}/>`;
    case 'wavy':
      return `<path d="M${X(-8)} ${Y(3)} Q${X(-4)} ${Y(-1)} ${X(0)} ${Y(3)} Q${X(4)} ${Y(7)} ${X(8)} ${Y(3)}" ${s('line', lw)}/>`;
    case 'flat':
      return `<path d="M${X(-5)} ${Y(3)} L${X(5)} ${Y(3)}" ${s('line', lw)}/>`;
    default:
      return `<path d="M${X(-6)} ${Y(0)} Q${X(0)} ${Y(6)} ${X(6)} ${Y(0)}" ${s('line', lw)}/>`;
  }
}

export interface FaceOpt {
  k?: number;
  gap?: number;
  cheeks?: boolean;
  eye?: 'cool';
  brow?: boolean | 'sad';
  mouth?: false | MouthKind;
}

/** 프로토타입 face() + 기분(hurt: > <, happy: 감은 눈) */
export function face(c: Ctx, x: number, y: number, o: FaceOpt = {}): string {
  const s = c.s;
  const k = o.k ?? 1;
  const g = (o.gap ?? 19) * k;
  const lw = 3.6 * Math.max(k, 0.6);
  let out = '';
  if (o.cheeks !== false) {
    out += `<ellipse cx="${n(x - g - 11 * k)}" cy="${n(y + 12 * k)}" rx="${n(7 * k)}" ry="${n(4.2 * k)}" ${s('cheek')}/>`;
    out += `<ellipse cx="${n(x + g + 11 * k)}" cy="${n(y + 12 * k)}" rx="${n(7 * k)}" ry="${n(4.2 * k)}" ${s('cheek')}/>`;
  }
  [-g, g].forEach((dx, i) => {
    const ex = x + dx;
    const side = i === 0 ? 1 : -1;
    const X = (d: number): number => n(ex + d * k);
    const Y = (d: number): number => n(y + d * k);
    if (c.mood === 'hurt') {
      out += `<path d="M${n(ex - 5 * k * side)} ${Y(-7)} L${n(ex + 5 * k * side)} ${Y(0)} L${n(ex - 5 * k * side)} ${Y(7)}" ${s('line', lw * 1.05)}/>`;
      return;
    }
    if (c.mood === 'happy') {
      out += `<path d="M${X(-7)} ${Y(3)} Q${X(0)} ${Y(-9)} ${X(7)} ${Y(3)}" ${s('line', lw * 1.05)}/>`;
      return;
    }
    if (o.eye === 'cool') {
      out += `<path d="M${X(-7)} ${Y(-1)} A${n(7 * k)} ${n(8 * k)} 0 0 0 ${X(7)} ${Y(-1)} Z" ${s('eye')}/>`;
      out += `<path d="M${X(-8)} ${Y(-2)} L${X(8)} ${Y(-2)}" ${s('line', 3.2 * Math.max(k, 0.6))}/>`;
    } else {
      out += `<ellipse cx="${n(ex)}" cy="${n(y)}" rx="${n(6.5 * k)}" ry="${n(8 * k)}" ${s('eye')}/>`;
      out += `<circle cx="${X(-2)}" cy="${Y(-3)}" r="${n(2.3 * k)}" ${s('hi')}/>`;
    }
    if (o.brow === true) {
      out += `<path d="M${n(ex - 8 * k * side)} ${Y(-14)} L${n(ex + 7 * k * side)} ${Y(-10)}" ${s('line', 3.4 * Math.max(k, 0.6))}/>`;
    } else if (o.brow === 'sad') {
      out += `<path d="M${n(ex - 8 * k * side)} ${Y(-10)} L${n(ex + 7 * k * side)} ${Y(-14)}" ${s('line', 3 * Math.max(k, 0.6))}/>`;
    }
  });
  if (o.mouth !== false) {
    out += mouth(c, x, y + 11 * k, k, moodMouth(c, o.mouth ?? 'smile'));
  }
  return out;
}

export function star(s: S, x: number, y: number, r: number): string {
  return `<path d="M${x} ${y - r} Q${x} ${y} ${x + r} ${y} Q${x} ${y} ${x} ${y + r} Q${x} ${y} ${x - r} ${y} Q${x} ${y} ${x} ${y - r} Z" ${s('spark')}/>`;
}

export function stars(s: S, pts: number[][]): string {
  return pts.map((p) => star(s, p[0], p[1], p[2])).join('');
}

/** 발 아래(100,186) 기준 확대: 진화 단계마다 커진다 */
export function scaleFrom(scale: number, inner: string, ox = 100, oy = 186): string {
  if (scale === 1) return inner;
  return `<g transform="translate(${ox} ${oy}) scale(${scale}) translate(${-ox} ${-oy})">${inner}</g>`;
}

/** x=axis/2 축 좌우 반전 (기본 100) */
export function mirror(inner: string, axis = 200): string {
  return `<g transform="translate(${axis} 0) scale(-1 1)">${inner}</g>`;
}

export function rot(deg: number, cx: number, cy: number, inner: string): string {
  return `<g transform="rotate(${deg} ${cx} ${cy})">${inner}</g>`;
}

/** 외곽선이 있는 굵은 관(손잡이, 팔, 꼬리). ol = 외곽선 두께 합 */
export function tube(d: string, w: number, color: string, ol = 9): string {
  return (
    `<path d="${d}" fill="none" stroke="${LINE}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<path d="${d}" fill="none" stroke="${color}" stroke-width="${n(w - ol)}" stroke-linecap="round" stroke-linejoin="round"/>`
  );
}

/** 점 목록 -> 닫힌 다각형 path d (dx,dy 이동, k 배율, fx 좌우반전) */
export function poly(pts: number[][], dx = 0, dy = 0, k = 1, fx = 1): string {
  return pts.map((p, i) => `${i ? 'L' : 'M'}${n(dx + p[0] * k * fx)} ${n(dy + p[1] * k)}`).join(' ') + ' Z';
}

/** 뭉게뭉게 테두리(솜, 나뭇잎, 구름) */
export function fluff(cx: number, cy: number, rx: number, ry: number, nb: number, bump: number, rot0 = 0): string {
  let d = '';
  const step = (Math.PI * 2) / nb;
  for (let i = 0; i < nb; i++) {
    const a0 = rot0 + i * step;
    const a1 = a0 + step;
    const am = (a0 + a1) / 2;
    const x0 = cx + rx * Math.cos(a0);
    const y0 = cy + ry * Math.sin(a0);
    const x1 = cx + rx * Math.cos(a1);
    const y1 = cy + ry * Math.sin(a1);
    const qx = cx + (rx + bump * 2) * Math.cos(am);
    const qy = cy + (ry + bump * 2) * Math.sin(am);
    if (i === 0) d += `M${n(x0)} ${n(y0)} `;
    d += `Q${n(qx)} ${n(qy)} ${n(x1)} ${n(y1)} `;
  }
  return d + 'Z';
}

/** 별 모양(갈기, 충격) 다각형 */
export function spiky(cx: number, cy: number, ro: number, ri: number, nb: number, rot0 = -Math.PI / 2): string {
  const pts: number[][] = [];
  for (let i = 0; i < nb * 2; i++) {
    const a = rot0 + (i * Math.PI) / nb;
    const r = i % 2 === 0 ? ro : ri;
    pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return poly(pts);
}

/** 나뭇잎 (x,y 에서 ang 방향으로 len 길이) */
export function leaf(s: S, x: number, y: number, len: number, ang: number, role: string): string {
  const w = len * 0.36;
  return (
    `<g transform="translate(${n(x)} ${n(y)}) rotate(${n(ang)})">` +
    `<path d="M0 0 Q${n(len * 0.45)} ${n(-w)} ${n(len)} 0 Q${n(len * 0.45)} ${n(w)} 0 0 Z" ${s(role)}/>` +
    `<path d="M${n(len * 0.15)} 0 L${n(len * 0.7)} 0" ${s('line', 2)}/></g>`
  );
}

export interface WrapOpt {
  groundRx?: number;
  float?: boolean;
  label?: string;
  anim?: string;
}

/** 200x200 스티커 캐릭터 SVG: 바닥 그림자 + 스티커 필터 */
export function stickerSvg(inner: string, o: WrapOpt = {}): string {
  const rx = o.groundRx ?? 44;
  const ground = `<ellipse cx="100" cy="188" rx="${o.float ? n(rx * 0.8) : rx}" ry="6" fill="#000000" fill-opacity="${o.float ? 0.08 : 0.12}"/>`;
  const cls = o.anim ?? (o.float ? 'rc-float' : 'rc-bob');
  const label = o.label ? ` aria-label="${o.label}"` : '';
  return (
    `<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" role="img"${label}>` +
    `${ground}<g class="${cls}"><g filter="url(#rc-stk)"><g filter="url(#rc-wob)">${inner}</g></g></g></svg>`
  );
}
