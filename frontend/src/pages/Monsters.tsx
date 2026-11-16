import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Remon } from '../components/Art';
import { Mat, PageHead, Stars } from '../components/common';
import { get, send } from '../lib/api';
import { MAT_NAMES, TYPE_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';
import type { Monster } from '../lib/types';

const BASE = ['plastic', 'paper', 'metal', 'glass', 'vinyl'] as const;

function Exchange() {
  const { me, refresh, toast } = useStore();
  const [src, setSrc] = useState<string>('plastic');
  const [dst, setDst] = useState<string>('glass');
  const [amount, setAmount] = useState(1);
  const [busy, setBusy] = useState(false);
  if (!me?.unlocks.exchange) return null;
  const cost = src === 'coins' ? amount * 5 : amount * 3;
  async function go() {
    setBusy(true);
    try {
      const r = await send<{ spent: number; got: number }>('/exchange', 'POST', { src, dst, amount });
      toast(`${MAT_NAMES[dst]} ${r.got}개로 바꿨어요`);
      await refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="card">
      <h3>재료 교환</h3>
      <p className="tiny muted">재료 3개 → 다른 재료 1개, 코인 5 → 재료 1개 (기본 재료끼리만)</p>
      <div className="row wrap" style={{ gap: 6 }}>
        <select aria-label="낼 것" value={src} onChange={(e) => { const v = e.target.value; setSrc(v); if (v === dst) setDst(BASE.find((k) => k !== v) ?? 'plastic'); }}>
          {BASE.map((k) => <option key={k} value={k}>{MAT_NAMES[k]} ({me.materials[k]})</option>)}
          <option value="coins">코인 ({me.coins})</option>
        </select>
        <span>→</span>
        <select aria-label="받을 재료" value={dst} onChange={(e) => setDst(e.target.value)}>
          {BASE.filter((k) => k !== src).map((k) => <option key={k} value={k}>{MAT_NAMES[k]}</option>)}
        </select>
        <input aria-label="받을 개수" type="number" min={1} max={100} value={amount} style={{ width: 64 }}
          onChange={(e) => setAmount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))} />
        <button className="btn sm" disabled={busy || src === dst} onClick={go}>바꾸기 ({src === 'coins' ? '코인' : MAT_NAMES[src]} {cost})</button>
      </div>
    </div>
  );
}

export default function Monsters() {
  const { me } = useStore();
  const [list, setList] = useState<Monster[]>([]);
  useEffect(() => {
    get<{ monsters: Monster[] }>('/monsters').then((r) => setList(r.monsters)).catch(() => setList([]));
  }, []);
  return (
    <>
      <PageHead title="내 리몬" back={false} right={<div className="row" style={{ gap: 6 }}><Link className="btn ghost sm" to="/party">파티</Link><Link className="btn ghost sm" to="/dex">도감</Link></div>} />
      {me && (
        <div className="card">
          <div className="row wrap" style={{ gap: 12 }}>
            {(['plastic', 'paper', 'metal', 'glass', 'vinyl', 'volt', 'fabric'] as const).map((k) => <Mat key={k} k={k} n={me.materials[k]} />)}
          </div>
        </div>
      )}
      <Exchange />
      <div className="mon-grid">
        {list.map((m) => (
          <Link key={m.id} to={`/monsters/${m.id}`} className="mon-card">
            {m.slot !== null && <span className="slot-tag">파티</span>}
            {m.on_expedition && <span className="exp-tag">탐사</span>}
            <Remon art={m.art} shiny={m.is_shiny} />
            <span className="nm">{m.name}</span>
            <span className="row" style={{ gap: 4 }}>
              <span className={`chip ${m.type}`}>{TYPE_NAMES[m.type]}</span>
            </span>
            <span className="tiny muted">Lv{m.level} <Stars n={m.stars} /></span>
          </Link>
        ))}
      </div>
      {list.length < 3 && <p className="small muted center">배출 인증을 하면 캡슐이 나와요. 캡슐에서 새 리몬을 만날 수 있어요.</p>}
    </>
  );
}
