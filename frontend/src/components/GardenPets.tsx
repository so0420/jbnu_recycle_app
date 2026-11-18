import { useEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { Remon } from './Art';
import type { Monster } from '../lib/types';

// 정원 위를 돌아다니는 파티 리몬. 위치는 정원 상자 기준 % (x: 가로, y: 발 위치)
// 누르면 반응하고, 끌어서 정원 안 어디든 옮길 수 있다 (공중에 놓으면 땅으로 떨어진다).
type Mode = 'idle' | 'walk' | 'hop' | 'happy' | 'sit' | 'held' | 'fall' | 'land';
interface Pet { x: number; y: number; flip: boolean; mode: Mode; dur: number; say: string | null; emote: string | null }
// 누르고 있는 손가락/마우스. ox·oy 는 누른 점과 발 위치의 차이(px) — 집은 자리 그대로 따라오게
interface Grab { i: number; id: number; sx: number; sy: number; ox: number; oy: number; moved: boolean; x: number; y: number }

// 발 위치가 가운데 화분(정원 식물)의 밑동보다 앞쪽이어야 겹쳐 보이지 않는다
const X_MIN = 10, X_MAX = 90, Y_MIN = 80, Y_MAX = 95;
const PET_PX = 68;                     // 맨 앞(깊이 1)일 때 리몬 크기
const DRAG_PX = 6;                     // 이만큼 움직여야 끌기로 본다 (그 전에 떼면 쓰다듬기)
const FALL_EASE = 'cubic-bezier(0.5, 0, 1, 0.6)';
const rand = (a: number, b: number) => a + Math.random() * (b - a);
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];
const depthAt = (y: number) => 0.78 + ((clamp(y, Y_MIN, Y_MAX) - Y_MIN) / (Y_MAX - Y_MIN)) * 0.3;   // 앞쪽(아래)일수록 크게
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export default function GardenPets({ party, dim, lines }: { party: Monster[]; dim: boolean; lines: string[] }) {
  const [pets, setPetsState] = useState<Pet[]>([]);
  const petsRef = useRef<Pet[]>([]);
  const setPets = (ps: Pet[]) => { petsRef.current = ps; setPetsState(ps); };
  const timers = useRef<number[]>([]);
  const busyUntil = useRef<number[]>([]);
  // 리몬마다 동작 번호. 집어 들면 올려서, 그 전에 예약해 둔 "동작 끝" 처리가 끼어들지 않게 한다
  const gen = useRef<number[]>([]);
  const boxRef = useRef<HTMLDivElement>(null);
  const grab = useRef<Grab | null>(null);
  const [drag, setDrag] = useState<{ i: number; x: number; y: number } | null>(null);
  const droppedAt = useRef(0);
  const linesRef = useRef(lines);
  linesRef.current = lines;

  const update = (i: number, p: Partial<Pet>) => setPets(petsRef.current.map((q, j) => (j === i ? { ...q, ...p } : q)));
  const later = (fn: () => void, ms: number) => { timers.current.push(window.setTimeout(fn, ms)); };
  const finish = (i: number, fn: () => void, ms: number) => {
    const g = gen.current[i];
    later(() => { if (gen.current[i] === g) fn(); }, ms);
  };

  useEffect(() => {
    const n = party.length;
    // 처음 자리: 가로로 고르게 흩어 놓는다
    setPets(party.map((_, i) => ({
      x: n === 1 ? pick([28, 72]) + rand(-5, 5) : X_MIN + 10 + ((X_MAX - X_MIN - 20) * i) / Math.max(1, n - 1) + rand(-4, 4),
      y: rand(Y_MIN + 3, Y_MAX - 3), flip: Math.random() < 0.5, mode: 'idle', dur: 0, say: null, emote: null,
    })));
    busyUntil.current = party.map(() => 0);
    gen.current = party.map(() => 0);
    grab.current = null;
    setDrag(null);
    if (reduceMotion()) return;

    const speed = dim ? 7 : 12;          // 초당 이동 거리(%). 동네가 더러우면 기운이 없다
    const schedule = (i: number, ms: number) => later(() => act(i), ms);
    const act = (i: number) => {
      if (document.hidden || Date.now() < busyUntil.current[i]) return schedule(i, 1500);
      {
        const p = petsRef.current[i];
        if (!p) return;
        const r = Math.random();
        let next: Pet;
        let wait: number;
        if (r < 0.62) {                       // 걷기
          // 다른 리몬과 너무 붙지 않는 자리를 몇 번 골라 본다
          const others = petsRef.current.filter((_, j) => j !== i);
          const crowd = (x: number, y: number) => others.reduce((s, q) => s + Math.max(0, 16 - Math.hypot(x - q.x, (y - q.y) * 2)), 0);
          let x = p.x, y = p.y, best = Infinity;
          for (let k = 0; k < 6; k++) {
            const cx = clamp(p.x + rand(-28, 28), X_MIN, X_MAX);
            const cy = clamp(p.y + rand(-6, 6), Y_MIN, Y_MAX);
            const c = crowd(cx, cy);
            if (c < best) { best = c; x = cx; y = cy; }
            if (c === 0) break;
          }
          const dist = Math.hypot(x - p.x, (y - p.y) * 2.5);
          const dur = Math.max(700, (dist / speed) * 1000);
          next = { ...p, x, y, flip: x < p.x, mode: 'walk', dur, emote: null };
          wait = dur;
          finish(i, () => update(i, { mode: 'idle' }), dur);
        } else if (r < 0.75 && !dim) {         // 제자리 폴짝
          next = { ...p, mode: 'hop', emote: pick(['♪', '!', '✨']) };
          wait = 900;
          finish(i, () => update(i, { mode: 'idle', emote: null }), 900);
        } else if (r < 0.84) {                 // 잠깐 앉아 쉬기
          next = { ...p, mode: 'sit', emote: dim ? '…' : null };
          wait = rand(2500, 4500);
        } else {                              // 두리번
          next = { ...p, flip: !p.flip, mode: 'idle', emote: null };
          wait = rand(800, 1600);
        }
        update(i, next);
        schedule(i, wait + rand(500, 1800));
      }
    };
    party.forEach((_, i) => schedule(i, rand(400, 2200)));
    return () => { timers.current.forEach((t) => clearTimeout(t)); timers.current = []; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [party.map((m) => m.id).join(','), dim]);

  function tap(i: number) {
    // 끌어다 놓은 직후 따라오는 click 은 쓰다듬기가 아니다
    if (performance.now() - droppedAt.current < 400) return;
    if (pets[i]?.mode === 'held' || pets[i]?.mode === 'fall') return;
    busyUntil.current[i] = Date.now() + 2600;
    update(i, { mode: 'happy', emote: dim ? '💦' : '❤', say: pick(linesRef.current) });
    finish(i, () => update(i, { mode: 'idle', emote: null, say: null }), 2600);
  }

  // 누른 점 → 발 위치(%). 정원 상자 밖으로는 못 나가고, 머리가 위쪽 테두리에 걸리면 멈춘다
  function footAt(g: Grab, cx: number, cy: number) {
    const box = boxRef.current!.getBoundingClientRect();
    const top = ((PET_PX * depthAt(Y_MIN)) / box.height) * 100;
    return {
      x: clamp(((cx - g.ox - box.left) / box.width) * 100, X_MIN, X_MAX),
      y: clamp(((cy - g.oy - box.top) / box.height) * 100, top, Y_MAX),
    };
  }

  function onDown(i: number, e: ReactPointerEvent<HTMLButtonElement>) {
    if (e.button !== 0 || grab.current || !boxRef.current) return;
    const r = e.currentTarget.getBoundingClientRect();     // 걷는 중이면 지금 보이는 자리
    grab.current = {
      i, id: e.pointerId, sx: e.clientX, sy: e.clientY,
      ox: e.clientX - (r.left + r.width / 2), oy: e.clientY - r.bottom, moved: false, x: 0, y: 0,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function onMove(e: ReactPointerEvent<HTMLButtonElement>) {
    const g = grab.current;
    if (!g || e.pointerId !== g.id) return;
    if (!g.moved) {
      if (Math.hypot(e.clientX - g.sx, e.clientY - g.sy) < DRAG_PX) return;
      g.moved = true;
      gen.current[g.i]++;
      busyUntil.current[g.i] = Infinity;
      update(g.i, { mode: 'held', say: null, emote: dim ? '💦' : '!' });
    }
    const f = footAt(g, e.clientX, e.clientY);
    g.x = f.x; g.y = f.y;
    setDrag({ i: g.i, ...f });
  }

  function onUp(e: ReactPointerEvent<HTMLButtonElement>) {
    const g = grab.current;
    if (!g || e.pointerId !== g.id) return;
    grab.current = null;
    if (!g.moved) return;                // 그냥 누른 것 — click 이 쓰다듬기로 처리
    droppedAt.current = performance.now();
    setDrag(null);
    drop(g.i, g.x, g.y);
  }

  // 땅(걷는 띠)보다 위에서 놓으면 그 자리에서 수직으로 떨어진 뒤 털썩
  function drop(i: number, x: number, y: number) {
    gen.current[i]++;
    const air = Y_MIN - y;
    const fall = air > 0 && !reduceMotion() ? Math.round(200 + Math.sqrt(air) * 45) : 0;   // 높을수록 오래 (중력처럼 √높이)
    update(i, { x, y: Math.max(y, Y_MIN), mode: fall ? 'fall' : 'land', dur: fall, emote: null, say: null });
    if (fall) finish(i, () => update(i, { mode: 'land' }), fall);
    finish(i, () => update(i, { mode: 'idle' }), fall + 400);
    busyUntil.current[i] = Date.now() + fall + 1400;
  }

  return (
    <div className="pets" ref={boxRef} aria-label="정원의 리몬들">
      {pets.map((p, i) => {
        const m = party[i];
        if (!m) return null;
        const d = drag?.i === i ? drag : null;
        const x = d ? d.x : p.x, y = d ? d.y : p.y;
        const moving = p.mode === 'walk' || p.mode === 'fall';
        return (
          <button
            key={m.id}
            type="button"
            className={`pet ${p.mode}`}
            style={{
              left: `${x}%`, top: `${y}%`, zIndex: p.mode === 'held' || p.mode === 'fall' ? 100 : Math.round(y),
              transitionDuration: moving && !d ? `${p.dur}ms` : '0ms',
              transitionTimingFunction: p.mode === 'fall' ? FALL_EASE : undefined,
              ['--s' as string]: depthAt(y),
            }}
            onPointerDown={(e) => onDown(i, e)}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
            onClick={() => tap(i)}
            aria-label={`${m.name} 쓰다듬기`}
          >
            <span className="pet-shadow" />
            <span className="pet-flip" style={{ transform: `scaleX(${p.flip ? -1 : 1})` }}>
              <span className="pet-body">
                <Remon art={m.art} shiny={m.is_shiny} mood={p.mode === 'happy' || p.mode === 'held' ? 'happy' : dim ? 'hurt' : 'normal'} />
              </span>
            </span>
            {p.emote && !p.say && <span className="pet-emote">{p.emote}</span>}
            {p.say && <span className={`pet-say ${x < 32 ? 'l' : x > 68 ? 'r' : ''}`}>{p.say}</span>}
          </button>
        );
      })}
    </div>
  );
}
