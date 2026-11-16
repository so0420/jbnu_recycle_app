// 오염 괴물(레이드 보스) 5종. 성난 빨간 눈, hurt 는 찡그린 눈 + 충격 별.

import { Ctx, Pal, ctx, scaleFrom, mirror, rot, tube, poly, fluff, spiky, stickerSvg, n, RED_EYE } from './core';

export interface BossOpts {
  hurt?: boolean;
}

type BossDraw = (c: Ctx, hurt: boolean) => string;

/** 성난 눈 한 쌍 */
function bossEyes(c: Ctx, x: number, y: number, gap: number, k: number, hurt: boolean): string {
  const s = c.s;
  let out = '';
  [-1, 1].forEach((sd) => {
    const ex = x + sd * gap;
    const side = -sd; // 안쪽 방향
    const X = (d: number): number => n(ex + d * k * side);
    const Y = (d: number): number => n(y + d * k);
    if (hurt) {
      out += `<path d="M${X(-6)} ${Y(-7)} L${X(5)} ${Y(0)} L${X(-6)} ${Y(7)}" ${s('line', 3.8 * Math.max(k, 0.6))}/>`;
      return;
    }
    out += `<path d="M${X(-10)} ${Y(-7)} L${X(9)} ${Y(0)} Q${X(8)} ${Y(9)} ${X(0)} ${Y(9)} Q${X(-10)} ${Y(9)} ${X(-10)} ${Y(-7)} Z" fill="${RED_EYE}" stroke="#2A2622" stroke-width="${n(4 * Math.max(k, 0.55))}" stroke-linejoin="round"/>`;
    out += `<circle cx="${X(2)}" cy="${Y(3)}" r="${n(3.2 * k)}" ${s('eye')}/>`;
    out += `<path d="M${X(-12)} ${Y(-13)} L${X(11)} ${Y(-4)}" ${s('line', 4.4 * Math.max(k, 0.55))}/>`;
  });
  if (hurt) out += `<path d="M${n(x + gap + 14 * k)} ${n(y - 16 * k)} Q${n(x + gap + 20 * k)} ${n(y - 6 * k)} ${n(x + gap + 14 * k)} ${n(y - 4 * k)} Q${n(x + gap + 8 * k)} ${n(y - 6 * k)} ${n(x + gap + 14 * k)} ${n(y - 16 * k)} Z" fill="#8CC8EA" stroke="#2A2622" stroke-width="${n(2.6 * Math.max(k, 0.6))}"/>`;
  return out;
}

/** 송곳니 입 */
function fangs(c: Ctx, x: number, y: number, w: number, h: number, hurt: boolean): string {
  const s = c.s;
  if (hurt) {
    return `<path d="M${x - w} ${y + h * 0.3} L${x - w / 2} ${y} L${x} ${y + h * 0.3} L${x + w / 2} ${y} L${x + w} ${y + h * 0.3}" ${s('line', 3.4)}/>`;
  }
  const f = (a: number, b: number): string => `<path d="M${n(x + a)} ${y} L${n(x + b)} ${y} L${n((2 * x + a + b) / 2)} ${n(y + h * 0.45)} Z" fill="#FFFFFF"/>`;
  return `<path d="M${x - w} ${y} L${x + w} ${y} Q${x} ${y + h * 1.6} ${x - w} ${y} Z" ${s('eye')}/>` + f(-w * 0.7, -w * 0.35) + f(w * 0.35, w * 0.7);
}

function burst(x: number, y: number, r: number): string {
  return `<path d="${spiky(x, y, r, r * 0.45, 8, -Math.PI / 8)}" fill="#FFFFFF" stroke="#2A2622" stroke-width="3" stroke-linejoin="round"/>`;
}

// ───────────── 음식물 범벅 슬라임 ─────────────
const slime: BossDraw = (c, hurt) => {
  const s = c.s;
  let b = '';
  b += `<path d="M44 128 L156 128 L146 182 L54 182 Z" ${s('acc')}/>`;
  b += `<path d="M134 132 L150 132 L142 178 L128 178 Z" ${s('~tubd')}/>`;
  b += `<path d="M72 146 L74 174 M100 146 L100 176 M128 146 L126 174" ${s('line', 2.2)}/>`;
  b += `<path d="M38 136 C26 104 50 52 100 50 C150 52 174 104 162 136 C150 148 50 148 38 136 Z" ${s('body')}/>`;
  b += `<path d="M56 136 Q54 160 61 162 Q68 160 66 138 Z" ${s('body', 3.6)}/><path d="M92 140 Q91 166 99 168 Q107 166 106 140 Z" ${s('body', 3.6)}/><path d="M132 136 Q132 152 138 154 Q144 152 142 136 Z" ${s('body', 3.6)}/>`;
  b += `<path d="M138 72 Q162 100 154 132 Q148 104 128 80 Z" ${s('dark')}/>`;
  b += `<path d="M58 92 Q62 74 76 66" ${s('lightline', 5)}/>`;
  // 국수 + 얼룩
  b += tube('M58 112 q6 -8 12 0 t12 0', 8, c.p.noodle, 4.4);
  b += `<path d="${fluff(130, 118, 8, 6, 6, 2)}" ${s('sauce', 3)}/><circle cx="72" cy="128" r="5" ${s('yolk', 3)}/><circle cx="118" cy="64" r="4" ${s('sauce', 2.6)}/>`;
  b += `<path d="${fluff(118, 162, 7, 5, 5, 2)}" ${s('sauce', 3)}/><circle cx="76" cy="164" r="3.4" ${s('yolk', 2.4)}/>`;
  // 비뚤어진 뚜껑
  b += rot(-16, 80, 50, `<rect x="44" y="40" width="72" height="12" rx="4" ${s('acc2')}/><rect x="72" y="32" width="16" height="9" rx="3" ${s('acc2', 3.4)}/>`);
  b += bossEyes(c, 100, 92, 22, 1, hurt);
  b += fangs(c, 100, 112, 18, 14, hurt);
  // 파리
  const fly = (x: number, y: number): string =>
    `<ellipse cx="${x - 4}" cy="${y - 4}" rx="4" ry="2.6" fill="#FFFFFF" stroke="#2A2622" stroke-width="1.8"/><ellipse cx="${x + 4}" cy="${y - 4}" rx="4" ry="2.6" fill="#FFFFFF" stroke="#2A2622" stroke-width="1.8"/><circle cx="${x}" cy="${y}" r="3.4" fill="#2A2622"/>`;
  b += fly(30, 64) + fly(172, 50);
  return b;
};

// ───────────── 라벨 골렘 (시안) ─────────────
const golem: BossDraw = (c, hurt) => {
  const s = c.s;
  let b = '';
  b += `<rect x="62" y="150" width="30" height="34" rx="6" ${s('body')}/><rect x="108" y="150" width="30" height="34" rx="6" ${s('body')}/>`;
  b += `<rect x="20" y="78" width="30" height="74" rx="13" ${s('body')}/><rect x="150" y="78" width="30" height="74" rx="13" ${s('body')}/>`;
  b += `<rect x="46" y="64" width="108" height="98" rx="16" ${s('body')}/>`;
  b += `<rect x="134" y="74" width="12" height="80" rx="6" ${s('dark')}/>`;
  b += `<g transform="rotate(-17 100 112)"><rect x="28" y="100" width="144" height="22" ${s('acc')}/><path d="M60 105 L60 117 M64 105 L64 117 M70 105 L70 117 M73 105 L73 117 M78 105 L78 117" ${s('line', 2)}/></g>`;
  b += `<g transform="rotate(13 100 136)"><rect x="34" y="128" width="132" height="18" ${s('acc2')}/></g>`;
  b += `<path d="M58 80 L66 90 L62 98" ${s('line', 2.6)}/>`;
  b += `<rect x="68" y="26" width="64" height="46" rx="11" ${s('body')}/>`;
  b += `<rect x="116" y="32" width="9" height="34" rx="4.5" ${s('dark')}/>`;
  b += bossEyes(c, 100, 47, 13, 0.75, hurt);
  b += `<path d="M84 64 L90 60 L96 64 L102 60 L108 64 L114 60" ${s('line', 3.2)}/>`;
  return b;
};

// ───────────── 혼합배출 키메라 ─────────────
const chimera: BossDraw = (c, hurt) => {
  const s = c.s;
  const X = (x: number, y: number): string => `<path d="M${x - 5} ${y - 5} L${x + 5} ${y + 5} M${x + 5} ${y - 5} L${x - 5} ${y + 5}" ${s('line', 2.6)}/>`;
  let b = '';
  // 비닐봉지 날개 (뒤)
  b += rot(22, 150, 100,
    tube('M146 74 C144 56 158 56 156 74', 10, c.p.bag, 7) + tube('M164 74 C162 56 176 56 174 74', 10, c.p.bag, 7) +
    `<path d="M138 72 L182 72 L188 128 Q180 136 172 128 Q164 138 156 128 Q148 136 138 128 Z" ${s('bag')}/>` +
    `<path d="M138 72 L182 72 L183 82 L138 82 Z" ${s('bagb')}/><path d="M150 100 L156 110 M170 96 L174 108" ${s('line', 2.2)}/>`);
  // 다리
  b += `<rect x="64" y="160" width="26" height="24" rx="5" ${s('body')}/><rect x="110" y="160" width="26" height="24" rx="5" ${s('can')}/>`;
  // 페트병 팔 (몽둥이)
  b += rot(28, 52, 100,
    `<rect x="42" y="84" width="16" height="10" rx="3" ${s('label')}/>` +
    `<path d="M44 92 L56 92 L56 98 C56 104 66 106 66 116 L66 152 Q66 160 58 160 L42 160 Q34 160 34 152 L34 116 C34 106 44 104 44 98 Z" ${s('pet')}/>` +
    `<rect x="34" y="126" width="32" height="14" ${s('#E5553C')}/><rect x="40" y="110" width="5" height="12" rx="2.5" ${s('light')}/>`);
  // 상자 몸
  b += `<rect x="52" y="96" width="96" height="70" rx="8" ${s('body')}/>`;
  b += `<rect x="130" y="102" width="10" height="58" rx="5" ${s('dark')}/>`;
  b += `<path d="M52 114 L148 114" ${s('line', 3)}/><rect x="90" y="96" width="20" height="18" ${s('acc')}/>`;
  b += `<path d="M66 154 L74 142 L82 154 Z" ${s('line', 2.4)}/>`;
  // 유리 조각 뿔
  b += `<path d="M118 44 L136 14 L130 48 Z" ${s('glass')}/>`;
  // 캔 머리
  b += `<rect x="68" y="38" width="64" height="62" rx="10" ${s('can')}/>`;
  b += `<rect x="116" y="48" width="8" height="46" rx="4" ${s('~cand')}/>`;
  b += `<ellipse cx="100" cy="40" rx="32" ry="8" ${s('cant')}/><ellipse cx="100" cy="40" rx="22" ry="4.5" ${s('~cand')}/>`;
  b += `<ellipse cx="84" cy="28" rx="8" ry="5" ${s('line', 3.2)}/>`;
  b += `<rect x="68" y="86" width="64" height="12" ${s('canb')}/>`;
  b += bossEyes(c, 100, 60, 14, 0.75, hurt);
  b += fangs(c, 100, 74, 11, 8, hurt);
  b += X(84, 100) + X(116, 100) + X(56, 106) + X(146, 108);
  return b;
};

// ───────────── 미세플라스틱 떼 ─────────────
const CRITTERS: { x: number; y: number; col: string; pts: number[][] }[] = [
  { x: 52, y: 150, col: '#5AA0E0', pts: [[-22, -8], [-6, -24], [18, -18], [24, 6], [8, 20], [-18, 16]] },
  { x: 102, y: 160, col: '#F4F1EA', pts: [[-20, -14], [2, -22], [22, -10], [18, 16], [-10, 20], [-24, 4]] },
  { x: 152, y: 148, col: '#E86A5A', pts: [[-18, -18], [14, -22], [22, 0], [10, 20], [-16, 18], [-24, -2]] },
  { x: 74, y: 92, col: '#F2C94C', pts: [[-18, -12], [4, -20], [20, -6], [14, 16], [-14, 14]] },
  { x: 130, y: 88, col: '#7CC46A', pts: [[-16, -16], [16, -14], [20, 10], [0, 20], [-20, 8]] },
];
const micro: BossDraw = (c, hurt) => {
  const s = c.s;
  let b = '';
  // 떠다니는 작은 부스러기
  [[30, 108, '#5AA0E0'], [172, 110, '#F2C94C'], [102, 50, '#E86A5A'], [42, 60, '#7CC46A'], [164, 56, '#F4F1EA'], [104, 120, '#F2C94C']].forEach((d, i) => {
    const x = d[0] as number, y = d[1] as number;
    b += `<path d="${poly([[-5, -4], [5, -5], [3, 5], [-4, 4]], x, y, 1 + (i % 2) * 0.3)}" fill="${d[2]}" stroke="#2A2622" stroke-width="2.6" stroke-linejoin="round"/>`;
  });
  CRITTERS.forEach((cr, i) => {
    const shade = cr.pts.slice(2, 4).concat([[0, 0]]);
    b += `<path d="${poly(cr.pts, cr.x, cr.y)}" fill="${cr.col}" stroke="#2A2622" stroke-width="4.2" stroke-linejoin="round"/>`;
    b += `<path d="${poly(shade, cr.x, cr.y, 0.8)}" fill="#000000" fill-opacity=".12"/>`;
    b += `<path d="M${cr.x - 12} ${cr.y - 6} L${cr.x - 6} ${cr.y - 13}" ${s('lightline', 3.4)}/>`;
    b += bossEyes(c, cr.x, cr.y - 1, 7, 0.45, hurt);
    b += fangs(c, cr.x, cr.y + 7, 5, 4, hurt);
    if (i >= 3) b += `<path d="M${cr.x - 8} ${cr.y + 26} L${cr.x - 8} ${cr.y + 32} M${cr.x} ${cr.y + 28} L${cr.x} ${cr.y + 35} M${cr.x + 8} ${cr.y + 26} L${cr.x + 8} ${cr.y + 32}" ${s('line', 2.2)}/>`;
  });
  return b;
};

// ───────────── 스티로폼 거인 ─────────────
const styro: BossDraw = (c, hurt) => {
  const s = c.s;
  let b = '';
  const dots = (x0: number, y0: number, w: number, h: number): string => {
    let o = '';
    for (let i = 0; i < 6; i++)
      for (let j = 0; j < 5; j++) {
        if ((i * 7 + j * 3) % 4 !== 0) continue;
        o += `<circle cx="${n(x0 + ((i + 0.5) * w) / 6)}" cy="${n(y0 + ((j + 0.5) * h) / 5)}" r="2.2" ${s('~dot')}/>`;
      }
    return o;
  };
  b += `<rect x="56" y="156" width="36" height="30" rx="5" ${s('body')}/><rect x="108" y="156" width="36" height="30" rx="5" ${s('body')}/>`;
  const arm = `<rect x="12" y="80" width="34" height="74" rx="6" ${s('body')}/><rect x="8" y="146" width="42" height="30" rx="8" ${s('body')}/><path d="M18 100 L40 100" ${s('line', 2.2)}/>`;
  b += arm + mirror(arm);
  b += `<rect x="36" y="70" width="128" height="94" rx="8" ${s('body')}/>`;
  b += `<rect x="146" y="78" width="10" height="78" rx="5" ${s('dark')}/>`;
  b += dots(40, 74, 104, 86);
  b += `<path d="M36 92 L110 92 M36 142 L84 142 M120 142 L164 142" ${s('line', 2.4)}/>`;
  b += `<path d="M56 112 L66 120 L62 130 L72 136" ${s('line', 2.6)}/>`;
  b += `<path d="${fluff(124, 120, 9, 7, 6, 2.4)}" ${s('stain', 3)}/><circle cx="30" cy="124" r="4" ${s('stain', 2.4)}/>`;
  // 어깨 깨진 모서리
  b += `<path d="M36 82 L36 70 L46 70 L44 76 Z" fill="#FFFFFF" stroke="none"/>`;
  b += `<rect x="70" y="26" width="60" height="50" rx="6" ${s('body')}/><rect x="114" y="32" width="9" height="38" rx="4.5" ${s('dark')}/>`;
  b += dots(72, 28, 50, 44);
  b += bossEyes(c, 100, 46, 14, 0.8, hurt);
  b += `<path d="M84 64 L90 60 L96 64 L102 60 L108 64 L114 60" ${s('line', 3.2)}/>`;
  return b;
};

const BOSSES: Record<string, { pal: Pal; draw: BossDraw; groundRx: number; scale?: number }> = {
  slime: { draw: slime, groundRx: 66, pal: { body: '#A8BF6A', dark: '#869E4C', acc: '#EEF0F2', acc2: '#C9D3DC', cheek: '#000000', tubd: '#D5DBE1', sauce: '#D8452F', yolk: '#E9B93A', noodle: '#F3E3B0' } },
  label_golem: { draw: golem, groundRx: 72, pal: { body: '#8B87A1', dark: '#68637E', acc: '#EFC83E', acc2: '#E4473A', cheek: '#000000' } },
  chimera: { draw: chimera, groundRx: 66, pal: { body: '#C99A62', dark: '#A97A45', acc: '#EBDBBB', acc2: '#7E5530', cheek: '#000000', can: '#C8CDD5', cand: '#99A1AD', cant: '#7B8391', canb: '#D8402F', pet: '#CFE8F4', label: '#2C6BCB', bag: '#F2EFF6', bagb: '#7A55B0', glass: '#8DCAA1' } },
  microplastic: { draw: micro, groundRx: 78, scale: 1.12, pal: { body: '#5AA0E0', dark: '#3E7FC0', acc: '#F2C94C', acc2: '#E86A5A', cheek: '#000000' } },
  styro_giant: { draw: styro, groundRx: 80, pal: { body: '#F6F5EF', dark: '#DCDBD0', acc: '#E9E7DC', acc2: '#C9C7BA', cheek: '#000000', dot: '#E2E0D3', stain: '#E3A05A' } },
};

export const BOSS_KEYS: string[] = Object.keys(BOSSES);

export function renderBoss(key: string, opts: BossOpts = {}): string {
  const def = BOSSES[key] ?? BOSSES.label_golem;
  const hurt = !!opts.hurt;
  const c = ctx(def.pal, hurt ? 'hurt' : 'normal');
  let inner = scaleFrom(def.scale ?? 1, def.draw(c, hurt));
  if (hurt) inner = `<g transform="rotate(-5 100 186) translate(4 0)">${inner}</g>` + burst(34, 40, 14) + burst(170, 70, 10) + burst(160, 22, 7);
  return stickerSvg(inner, { groundRx: def.groundRx, label: key, anim: hurt ? 'rc-shake' : 'rc-bob' });
}
