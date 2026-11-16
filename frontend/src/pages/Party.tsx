import { useEffect, useState } from 'react';
import { Remon } from '../components/Art';
import { PageHead } from '../components/common';
import { get, send } from '../lib/api';
import { ROLE_NAMES, TIMING_NAMES, TYPE_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';
import type { Monster } from '../lib/types';

const BEAT_TEXT = '상성: 금속 → 유리 → 비닐 → 종이 → 플라스틱 → 금속 (화살표 방향이 1.5배)';

export default function Party() {
  const { toast } = useStore();
  const [all, setAll] = useState<Monster[]>([]);
  const [slots, setSlots] = useState<(number | null)[]>([null, null, null]);
  const [timings, setTimings] = useState<Record<number, string>>({});
  const [active, setActive] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get<{ monsters: Monster[] }>('/monsters').then((r) => {
      setAll(r.monsters);
      const s: (number | null)[] = [null, null, null];
      r.monsters.forEach((m) => { if (m.slot !== null && m.slot < 3) s[m.slot] = m.id; });
      setSlots(s);
      setTimings(Object.fromEntries(r.monsters.map((m) => [m.id, m.skill_timing])));
    });
  }, []);

  const byId = (id: number | null) => all.find((m) => m.id === id);

  function place(m: Monster) {
    const next = slots.map((x) => (x === m.id ? null : x));
    next[active] = m.id;
    setSlots(next);
    setActive(Math.min(2, active + 1));
  }

  async function save() {
    setBusy(true);
    try {
      await send('/party', 'PUT', { ids: slots, timings });
      toast('파티를 저장했어요');
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead title="파티 편성" />
      <p className="small muted">앞줄은 적의 공격을 70% 확률로 먼저 받아요. 탱커를 앞줄에 두면 좋아요.</p>
      <div className="grid3">
        {slots.map((id, i) => {
          const m = byId(id);
          return (
            <button key={i} className={`mon-card ${active === i ? 'sel' : ''}`} onClick={() => setActive(i)} aria-label={`${i === 0 ? '앞줄' : '뒷줄'} 자리`}>
              <span className="slot-tag">{i === 0 ? '앞줄' : '뒷줄'}</span>
              {m ? <Remon art={m.art} shiny={m.is_shiny} /> : <span className="art" style={{ width: 84, height: 84, display: 'grid', placeItems: 'center' }}>＋</span>}
              <span className="nm">{m?.name ?? '빈 자리'}</span>
              {m && <span className="tiny muted">{ROLE_NAMES[m.role]}</span>}
            </button>
          );
        })}
      </div>
      {slots.map((id) => byId(id)).filter(Boolean).map((m) => (
        <div key={m!.id} className="row between small">
          <span>{m!.name} 스킬 시점</span>
          <select value={timings[m!.id] ?? 'now'} onChange={(e) => setTimings({ ...timings, [m!.id]: e.target.value })} aria-label={`${m!.name} 스킬 시점`}>
            {Object.entries(TIMING_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      ))}
      <div className="row" style={{ gap: 8 }}>
        <button className="btn ghost grow" onClick={() => { const s = [...slots]; s[active] = null; setSlots(s); }}>이 자리 비우기</button>
        <button className="btn grow" onClick={save} disabled={busy}>저장</button>
      </div>
      <p className="tiny muted">{BEAT_TEXT}</p>
      <h3>보유 리몬 (눌러서 {active === 0 ? '앞줄' : '뒷줄'}에 넣기)</h3>
      <div className="mon-grid">
        {all.filter((m) => !m.on_expedition).map((m) => (
          <button key={m.id} className={`mon-card ${slots.includes(m.id) ? 'sel' : ''}`} onClick={() => place(m)}>
            <Remon art={m.art} shiny={m.is_shiny} />
            <span className="nm">{m.name}</span>
            <span className={`chip ${m.type}`}>{TYPE_NAMES[m.type]}</span>
            <span className="tiny muted">Lv{m.level} · 전투력 {m.power}</span>
          </button>
        ))}
      </div>
    </>
  );
}
