import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon, Remon } from './Art';
import { STAGE_COLORS } from '../lib/labels';
import type { Monster } from '../lib/types';

const TRASH = ['trash_bottle', 'trash_can', 'trash_box', 'trash_bag', 'trash_peel'];
const SPARK = ['clean_spark'];
const WINDUP = 450;      // 던지기 전 준비 동작
const GAP = 140;         // 쓰레기 사이 간격
const FLIGHT = 760;      // 한 개가 날아가는 시간

export interface ThrowTarget { name: string; before: number; after: number; stage: { key: string; name: string } }

function stageKeyOf(c: number): string {
  return c >= 900 ? 'sparkle' : c >= 700 ? 'clean' : c >= 400 ? 'normal' : c >= 200 ? 'dirty' : 'crisis';
}

interface Shot { id: number; icon: string; dx: number; rot: number; delay: number; hitX: number }
interface Splat { id: number; x: number; amount: number }

/** 우리 리몬이 상대 지역에 쓰레기를 던지는 연출 (attack), 또는 우리 지역에 반짝이를 날려 얼룩을 닦는 연출 (cleanse).
 *  damage 는 청결도 변화량의 크기. 화면을 누르면 건너뛴다. */
export default function TrashThrow({ thrower, fromName, target, damage, onDone, mode = 'attack' }: {
  thrower: Monster | null; fromName: string; target: ThrowTarget; damage: number; onDone: () => void;
  mode?: 'attack' | 'cleanse';
}) {
  const heal = mode === 'cleanse';
  const shots = useMemo<Shot[]>(() => {
    const count = Math.max(4, Math.min(9, Math.round(damage / 18)));
    return Array.from({ length: count }, (_, i) => {
      const dx = Math.round((Math.random() * 2 - 1) * 70);
      return { id: i, icon: heal ? SPARK[i % SPARK.length] : TRASH[(i + Math.floor(Math.random() * TRASH.length)) % TRASH.length], dx,
               rot: (Math.random() < 0.5 ? -1 : 1) * (360 + Math.round(Math.random() * 360)),
               delay: WINDUP + i * GAP, hitX: dx };
    });
  }, [damage, heal]);
  const reduced = useMemo(() => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches, []);
  const [hits, setHits] = useState(0);
  const [splats, setSplats] = useState<Splat[]>([]);
  const [shake, setShake] = useState(0);
  const [done, setDone] = useState(false);
  const timers = useRef<number[]>([]);
  const finished = useRef(false);

  const per = shots.length ? damage / shots.length : 0;
  const sign = heal ? 1 : -1;
  const shown = done ? target.after : target.before + sign * per * hits;
  const stainCount = heal ? Math.max(0, Math.min(shots.length, 9) - hits) : Math.min(hits, 9);

  function finish() {
    if (finished.current) return;
    finished.current = true;
    timers.current.forEach((t) => clearTimeout(t));
    setHits(shots.length);
    setDone(true);
    onDone();
  }

  useEffect(() => {
    if (reduced) { finish(); return; }
    shots.forEach((s, i) => {
      timers.current.push(window.setTimeout(() => {
        setHits(i + 1);
        setShake((k) => k + 1);
        setSplats((sp) => [...sp, { id: s.id, x: s.hitX, amount: Math.round(per * 10) / 10 }]);
        timers.current.push(window.setTimeout(() => setSplats((sp) => sp.filter((x) => x.id !== s.id)), 700));
      }, s.delay + FLIGHT));
    });
    timers.current.push(window.setTimeout(finish, WINDUP + (shots.length - 1) * GAP + FLIGHT + 500));
    return () => timers.current.forEach((t) => clearTimeout(t));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stageKey = done ? target.stage.key : stageKeyOf(shown);
  return (
    <div className={`throw-stage ${heal ? 'heal' : ''}`} onClick={finish} role="button"
         aria-label={`${heal ? '정화' : '쓰레기 던지기'} 연출 (누르면 건너뛰기)`}>
      <div className={`throw-target ${heal ? (shake ? `glow-${shake % 2 ? 'a' : 'b'}` : '') : shake % 2 ? 'shake-a' : shake ? 'shake-b' : ''}`}>
        <div className="row between">
          <b>{target.name}</b>
          <span className="num small" style={{ color: STAGE_COLORS[stageKey] }}>청결도 {Math.round(shown)}</span>
        </div>
        <div className="bar"><span style={{ width: `${Math.max(0, shown) / 10}%`, background: STAGE_COLORS[stageKey] }} /></div>
        {Array.from({ length: stainCount }, (_, i) => <span key={i} className={`stain s${i}`} />)}
        {splats.map((s) => (
          <span key={s.id} className={`splat ${heal ? 'heal' : ''}`} style={{ left: `calc(50% + ${s.x}px)` }}>
            <span className="puff" /><span className="hit-num">{heal ? '+' : '−'}{s.amount}</span>
          </span>
        ))}
      </div>
      {!reduced && !done && shots.map((s) => (
        <span key={s.id} className="proj" style={{ ['--dx' as string]: `${s.dx}px`, ['--rot' as string]: `${s.rot}deg`,
                                                  animationDelay: `${s.delay}ms` }}>
          <span className="proj-y" style={{ animationDelay: `${s.delay}ms` }}>
            <span className="proj-spin" style={{ animationDelay: `${s.delay}ms` }}><Icon name={s.icon} size={42} /></span>
          </span>
        </span>
      ))}
      <div className={`thrower ${done ? '' : 'throwing'}`}>
        {thrower ? <Remon art={thrower.art} shiny={thrower.is_shiny} mood={done ? 'happy' : 'normal'} size={104} />
                 : <Icon name="attack" size={80} />}
        <span className="tiny muted">{fromName}</span>
      </div>
      {!done && <span className="throw-skip tiny">누르면 건너뛰기</span>}
    </div>
  );
}
