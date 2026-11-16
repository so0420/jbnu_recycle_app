import { useEffect, useState } from 'react';
import { Remon } from '../components/Art';
import { PageHead } from '../components/common';
import { get } from '../lib/api';
import { RARITY_NAMES } from '../lib/labels';

interface DexRes {
  monsters: { ref: string; name: string; type: string; rarity: string; stage: number; have: boolean; shiny: boolean }[];
  items: { ref: string; name: string; category_name: string; have: boolean }[];
  stamps: string[];
}

export default function Dex() {
  const [d, setD] = useState<DexRes | null>(null);
  const [tab, setTab] = useState<'m' | 'i' | 's'>('m');
  useEffect(() => { get<DexRes>('/dex').then(setD).catch(() => setD({ monsters: [], items: [], stamps: [] })); }, []);
  if (!d) return <div className="splash">불러오는 중…</div>;
  const mHave = d.monsters.filter((m) => m.have).length;
  const iHave = d.items.filter((i) => i.have).length;
  const byCat = d.items.reduce<Record<string, DexRes['items']>>((a, it) => ((a[it.category_name] ||= []).push(it), a), {});
  return (
    <>
      <PageHead title="도감" />
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'm'} onClick={() => setTab('m')}>리몬 {mHave}/{d.monsters.length}</button>
        <button role="tab" aria-selected={tab === 'i'} onClick={() => setTab('i')}>품목 {iHave}/{d.items.length}</button>
        <button role="tab" aria-selected={tab === 's'} onClick={() => setTab('s')}>스탬프 {d.stamps.length}</button>
      </div>
      {tab === 'm' && (
        <>
          <p className="tiny muted">일반·희귀 10종을 모두 모으면 전설의 리몬이 찾아와요.</p>
          <div className="mon-grid">
            {d.monsters.map((m) => (
              <div key={m.ref} className={`mon-card ${m.have ? '' : 'locked'}`}>
                <Remon art={m.ref} shiny={m.shiny} />
                <span className="nm">{m.have ? m.name : '???'}</span>
                <span className={`chip ${m.rarity}`}>{RARITY_NAMES[m.rarity]}</span>
              </div>
            ))}
          </div>
        </>
      )}
      {tab === 'i' && (
        <div className="col">
          <p className="tiny muted">스캔으로 처음 확인한 품목이 기록돼요.</p>
          {Object.entries(byCat).map(([cat, items]) => (
            <div key={cat} className="card">
              <h3>{cat} <span className="small muted">{items.filter((i) => i.have).length}/{items.length}</span></h3>
              <div className="row wrap" style={{ gap: 6 }}>
                {items.map((i) => <span key={i.ref} className={`chip ${i.have ? 'ok' : 'common'}`} style={{ opacity: i.have ? 1 : 0.5 }}>{i.have ? i.name : '?'}</span>)}
              </div>
            </div>
          ))}
        </div>
      )}
      {tab === 's' && (
        <div className="card">
          <p>지금까지 <b>{d.stamps.length}곳</b>의 수거장에서 인증했어요.</p>
          <p className="small muted">새로운 수거장에서 처음 인증할 때마다 스탬프가 하나씩 늘어요. 지도에서 가까운 수거장을 찾아보세요.</p>
        </div>
      )}
    </>
  );
}
