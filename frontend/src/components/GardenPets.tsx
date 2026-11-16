import { useEffect, useRef, useState } from 'react';
import { Remon } from './Art';
import type { Monster } from '../lib/types';

// 정원 위를 돌아다니는 파티 리몬. 위치는 정원 상자 기준 % (x: 가로, y: 발 위치)
type Mode = 'idle' | 'walk' | 'hop' | 'happy' | 'sit';
interface Pet { x: number; y: number; flip: boolean; mode: Mode; dur: number; say: string | null; emote: string | null }

// 발 위치가 가운데 화분(정원 식물)의 밑동보다 앞쪽이어야 겹쳐 보이지 않는다
const X_MIN = 10, X_MAX = 90, Y_MIN = 80, Y_MAX = 95;
const rand = (a: number, b: number) => a + Math.random() * (b - a);
const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

export default function GardenPets({ party, dim, lines }: { party: Monster[]; dim: boolean; lines: string[] }) {
  const [pets, setPetsState] = useState<Pet[]>([]);
  const petsRef = useRef<Pet[]>([]);
  const setPets = (ps: Pet[]) => { petsRef.current = ps; setPetsState(ps); };
  const timers = useRef<number[]>([]);
  const busyUntil = useRef<number[]>([]);
  const linesRef = useRef(lines);
  linesRef.current = lines;

  const update = (i: number, p: Partial<Pet>) => setPets(petsRef.current.map((q, j) => (j === i ? { ...q, ...p } : q)));

  useEffect(() => {
    const n = party.length;
    // 처음 자리: 가로로 고르게 흩어 놓는다
    setPets(party.map((_, i) => ({
      x: n === 1 ? pick([28, 72]) + rand(-5, 5) : X_MIN + 10 + ((X_MAX - X_MIN - 20) * i) / Math.max(1, n - 1) + rand(-4, 4),
      y: rand(Y_MIN + 3, Y_MAX - 3), flip: Math.random() < 0.5, mode: 'idle', dur: 0, say: null, emote: null,
    })));
    busyUntil.current = party.map(() => 0);
    if (reduceMotion()) return;

    const speed = dim ? 7 : 12;          // 초당 이동 거리(%). 동네가 더러우면 기운이 없다
    const later = (fn: () => void, ms: number) => { timers.current.push(window.setTimeout(fn, ms)); };
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
            const cx = Math.min(X_MAX, Math.max(X_MIN, p.x + rand(-28, 28)));
            const cy = Math.min(Y_MAX, Math.max(Y_MIN, p.y + rand(-6, 6)));
            const c = crowd(cx, cy);
            if (c < best) { best = c; x = cx; y = cy; }
            if (c === 0) break;
          }
          const dist = Math.hypot(x - p.x, (y - p.y) * 2.5);
          const dur = Math.max(700, (dist / speed) * 1000);
          next = { ...p, x, y, flip: x < p.x, mode: 'walk', dur, emote: null };
          wait = dur;
          later(() => update(i, { mode: 'idle' }), dur);
        } else if (r < 0.75 && !dim) {         // 제자리 폴짝
          next = { ...p, mode: 'hop', emote: pick(['♪', '!', '✨']) };
          wait = 900;
          later(() => update(i, { mode: 'idle', emote: null }), 900);
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
    busyUntil.current[i] = Date.now() + 2600;
    update(i, { mode: 'happy', emote: dim ? '💦' : '❤', say: pick(linesRef.current) });
    timers.current.push(window.setTimeout(() => update(i, { mode: 'idle', emote: null, say: null }), 2600));
  }

  return (
    <div className="pets" aria-label="정원의 리몬들">
      {pets.map((p, i) => {
        const m = party[i];
        if (!m) return null;
        const depth = 0.78 + ((p.y - Y_MIN) / (Y_MAX - Y_MIN)) * 0.3;     // 앞쪽(아래)일수록 크게
        return (
          <button
            key={m.id}
            type="button"
            className={`pet ${p.mode}`}
            style={{
              left: `${p.x}%`, top: `${p.y}%`, zIndex: Math.round(p.y),
              transitionDuration: p.mode === 'walk' ? `${p.dur}ms` : '0ms',
              ['--s' as string]: depth,
            }}
            onClick={() => tap(i)}
            aria-label={`${m.name} 쓰다듬기`}
          >
            <span className="pet-shadow" />
            <span className="pet-flip" style={{ transform: `scaleX(${p.flip ? -1 : 1})` }}>
              <span className="pet-body">
                <Remon art={m.art} shiny={m.is_shiny} mood={p.mode === 'happy' ? 'happy' : dim ? 'hurt' : 'normal'} />
              </span>
            </span>
            {p.emote && !p.say && <span className="pet-emote">{p.emote}</span>}
            {p.say && <span className={`pet-say ${p.x < 32 ? 'l' : p.x > 68 ? 'r' : ''}`}>{p.say}</span>}
          </button>
        );
      })}
    </div>
  );
}
