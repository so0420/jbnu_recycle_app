import { useEffect, useMemo, useRef, useState } from 'react';
import { Boss, Remon } from './Art';
import type { BattleEvent, BattleUnit } from '../lib/types';

const SKILL_NAMES: Record<string, string> = {
  crush: '찌그러뜨리기', shards: '파편 난사', regen: '재생', wrap: '겹겹이 포장', bind: '휘감기',
  discharge: '방전', patch: '덧대기', cycle: '순환',
};

interface Floater { id: number; unit: string; text: string; kind: '' | 'heal' | 'crit' }

export default function BattlePlayer({ units, log, onDone }: { units: BattleUnit[]; log: BattleEvent[]; onDone?: () => void }) {
  const init = useMemo(() => Object.fromEntries(units.map((u) => [u.id, u.hp])), [units]);
  const [hp, setHp] = useState<Record<string, number>>(init);
  const [i, setI] = useState(0);
  const [actor, setActor] = useState<string | null>(null);
  const [hit, setHit] = useState<string | null>(null);
  const [floaters, setFloaters] = useState<Floater[]>([]);
  const [line, setLine] = useState('전투 시작!');
  const fid = useRef(0);
  const name = (id?: string) => units.find((u) => u.id === id)?.name ?? '';
  const allies = units.filter((u) => u.side === 'ally');
  const enemies = units.filter((u) => u.side === 'enemy');
  const swarm = enemies.length > 1;

  function apply(e: BattleEvent, h: Record<string, number>, visual: boolean) {
    const float = (unit: string, text: string, kind: Floater['kind'] = '') => {
      if (!visual) return;
      const id = ++fid.current;
      setFloaters((f) => [...f, { id, unit, text, kind }]);
      setTimeout(() => setFloaters((f) => f.filter((x) => x.id !== id)), 750);
    };
    if (e.dmg !== undefined && e.t) {
      h[e.t] = Math.max(0, (h[e.t] ?? 0) - e.dmg);
      float(e.t, e.crit ? `${e.dmg}!` : String(e.dmg), e.crit ? 'crit' : '');
    }
    if (e.heal !== undefined && e.t) {
      const u = units.find((x) => x.id === e.t);
      h[e.t] = Math.min(u?.max_hp ?? 9e9, (h[e.t] ?? 0) + e.heal);
      float(e.t, `+${e.heal}`, 'heal');
    }
    if (e.act === 'heal_all' && e.amount) {
      for (const u of allies) if ((h[u.id] ?? 0) > 0) h[u.id] = Math.min(u.max_hp, h[u.id] + e.amount);
    }
    if (e.act === 'respawn') for (const u of enemies) h[u.id] = u.max_hp;
    if (visual) {
      if (e.act === 'skill') setLine(`${name(e.a)}의 「${SKILL_NAMES[e.skill ?? ''] ?? '스킬'}」!`);
      else if (e.act === 'slam') setLine('스티로폼 거인의 내려찍기!');
      else if (e.act === 'pollute') setLine('오염이 번졌다… (공격력 감소)');
      else if (e.act === 'reshield') setLine('라벨 보호막이 다시 생겼다!');
      else if (e.act === 'respawn') setLine('미세플라스틱이 다시 몰려온다!');
      else if (e.act === 'stunned') setLine(`${name(e.a)}은(는) 묶여서 움직이지 못한다`);
      else if (e.shield_hit) setLine(`보호막을 깎았다 (−${e.shield_hit})`);
      setActor(e.a ?? null);
      setHit(e.t ?? null);
    }
  }

  useEffect(() => {
    if (i >= log.length) {
      setActor(null);
      setHit(null);
      onDone?.();
      return;
    }
    const t = setTimeout(() => {
      const h = { ...hp };
      apply(log[i], h, true);
      setHp(h);
      setI(i + 1);
    }, i === 0 ? 500 : 380);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, log]);

  function skip() {
    const h = { ...hp };
    for (let k = i; k < log.length; k++) apply(log[k], h, false);
    setHp(h);
    setI(log.length);
    setLine('전투 끝!');
  }

  const U = ({ u }: { u: BattleUnit }) => {
    const dead = (hp[u.id] ?? 0) <= 0;
    const cls = `unit ${u.side} ${u.side === 'enemy' ? 'boss' : ''} ${dead ? 'dead' : ''} ${actor === u.id ? 'act' : ''} ${hit === u.id ? 'hit' : ''}`;
    return (
      <div className={cls}>
        {u.side === 'ally' ? <Remon art={u.art} mood={dead ? 'hurt' : 'normal'} /> : <Boss boss={u.art} hurt={hit === u.id} />}
        <span className="tiny">{u.name}</span>
        <div className="hpbar"><span style={{ width: `${Math.max(0, (hp[u.id] / u.max_hp) * 100)}%` }} /></div>
        {floaters.filter((f) => f.unit === u.id).map((f) => <span key={f.id} className={`floater ${f.kind}`}>{f.text}</span>)}
      </div>
    );
  };

  return (
    <div className="col">
      <div className="arena">
        <div className="side">
          {swarm ? (
            <div className={`unit boss ${hit && hit.startsWith('b') ? 'hit' : ''}`}>
              <Boss boss={enemies[0].art} />
              <span className="tiny">{enemies[0].name.replace(/ \d+$/, '')} × {enemies.filter((u) => hp[u.id] > 0).length}</span>
              <div className="hpbar"><span style={{ width: `${(enemies.reduce((a, u) => a + hp[u.id], 0) / enemies.reduce((a, u) => a + u.max_hp, 0)) * 100}%` }} /></div>
              {floaters.filter((f) => f.unit.startsWith('b')).map((f) => <span key={f.id} className={`floater ${f.kind}`}>{f.text}</span>)}
            </div>
          ) : (
            enemies.map((u) => <div key={u.id} className="boss-wrap"><U u={u} /></div>)
          )}
        </div>
        <div className="side">{allies.map((u) => <U key={u.id} u={u} />)}</div>
      </div>
      <p className="battle-log" aria-live="polite">{line}</p>
      {i < log.length && <button className="btn ghost sm" onClick={skip}>건너뛰기</button>}
    </div>
  );
}
