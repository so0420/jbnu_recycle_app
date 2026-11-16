import { useEffect, useState } from 'react';
import { LoadError, PageHead } from '../components/common';
import { get, send } from '../lib/api';
import { MAT_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';

interface M { id: string; name: string; goal: number; progress: number; claimed: boolean; reward?: string }
interface Res {
  daily: M[];
  weekly: M[];
  unlocked: boolean;
  types3_material_pending: boolean;
  reward_preview: { daily_coins: number; daily_xp: number; weekly_materials: number };
}
interface ClaimRes { coins?: number; xp?: number; tickets?: number; capsule?: unknown; materials_choice?: number }

export default function Missions() {
  const { me, refresh, toast } = useStore();
  const [d, setD] = useState<Res | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const load = () => get<Res>('/missions').then((r) => { setErr(''); setD(r); })
    .catch((e) => { if (d) toast(errMsg(e), 'err'); else setErr(errMsg(e)); });
  useEffect(() => { void load(); }, []);

  async function claim(id: string) {
    if (busy) return;
    setBusy(true);
    try {
      const r = await send<ClaimRes>(`/missions/${id}/claim`, 'POST');
      if (r.capsule) toast('캡슐을 받았어요!');
      else if (r.coins !== undefined) toast(`코인 +${r.coins} · 경험치 +${r.xp ?? 0}${r.tickets ? ` · 도전권 +${r.tickets}` : ''}`);
      await Promise.all([load(), refresh()]);
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }

  async function pickMat(k: string) {
    if (busy) return;
    setBusy(true);
    try {
      const r = await send<{ material: string; amount: number }>('/missions/types3/material', 'POST', { material: k });
      toast(`${MAT_NAMES[r.material]} ${r.amount}개를 받았어요`);
      await Promise.all([load(), refresh()]);
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }

  if (!d && err) return <LoadError msg={err} onRetry={() => { setErr(''); void load(); }} />;
  if (!d) return <div className="splash">불러오는 중…</div>;
  const Row = ({ m, reward }: { m: M; reward: string }) => (
    <div className="list-item">
      <div className="col grow" style={{ gap: 4 }}>
        <b>{m.name}</b>
        <span className="tiny muted">{reward}</span>
        <div className="bar"><span style={{ width: `${(m.progress / m.goal) * 100}%` }} /></div>
      </div>
      <span className="num small">{m.progress}/{m.goal}</span>
      <button className="btn sm" disabled={busy || m.claimed || m.progress < m.goal || !d.unlocked} onClick={() => claim(m.id)}>
        {m.claimed ? '완료' : '받기'}
      </button>
    </div>
  );
  const rp = d.reward_preview;
  return (
    <>
      <PageHead title="미션" />
      {!d.unlocked && <p className="caution">미션 보상은 정원 레벨 {me?.unlock_levels.missions}부터 받을 수 있어요.</p>}
      <h3>오늘의 미션</h3>
      <div className="list">{d.daily.map((m) => <Row key={m.id} m={m} reward={`코인 ${rp.daily_coins} · 경험치 ${rp.daily_xp}`} />)}</div>
      <p className="tiny muted">오늘 미션을 모두 받으면 도전권 +1</p>
      <h3>이번 주 미션</h3>
      <div className="list">
        {d.weekly.map((m) => (
          <Row key={m.id} m={m} reward={m.reward === 'capsule' ? '캡슐 1개' : `원하는 재료 ${rp.weekly_materials}개`} />
        ))}
      </div>
      {d.types3_material_pending && (
        <div className="card pop">
          <h3>받을 재료를 골라 주세요 ({rp.weekly_materials}개)</h3>
          <div className="grid3">
            {['plastic', 'paper', 'metal', 'glass', 'vinyl'].map((k) => (
              <button key={k} className="btn ghost sm" disabled={busy} onClick={() => pickMat(k)}>{MAT_NAMES[k]}</button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
