import { useEffect, useState } from 'react';
import { PageHead } from '../components/common';
import { get, send } from '../lib/api';
import { MAT_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';

interface M { id: string; name: string; goal: number; progress: number; claimed: boolean; reward?: string }
interface Res { daily: M[]; weekly: M[]; unlocked: boolean }

export default function Missions() {
  const { me, refresh, toast } = useStore();
  const [d, setD] = useState<Res | null>(null);
  const [matPick, setMatPick] = useState(false);
  const load = () => get<Res>('/missions').then(setD);
  useEffect(() => { void load(); }, []);

  async function claim(id: string) {
    try {
      const r = await send<{ materials_choice?: number; capsule?: unknown }>(`/missions/${id}/claim`, 'POST');
      if (r.materials_choice) setMatPick(true);
      else toast(r.capsule ? '캡슐을 받았어요!' : '보상을 받았어요');
      await Promise.all([load(), refresh()]);
    } catch (e) {
      toast(errMsg(e), 'err');
    }
  }
  async function pickMat(k: string) {
    try {
      await send('/missions/types3/material', 'POST', { material: k });
      toast(`${MAT_NAMES[k]} 30개를 받았어요`);
      setMatPick(false);
      void refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
    }
  }

  if (!d) return <div className="splash">불러오는 중…</div>;
  const Row = ({ m }: { m: M }) => (
    <div className="list-item">
      <div className="col grow" style={{ gap: 4 }}>
        <b>{m.name}</b>
        <div className="bar"><span style={{ width: `${(m.progress / m.goal) * 100}%` }} /></div>
      </div>
      <span className="num small">{m.progress}/{m.goal}</span>
      <button className="btn sm" disabled={m.claimed || m.progress < m.goal || !d.unlocked} onClick={() => claim(m.id)}>{m.claimed ? '완료' : '받기'}</button>
    </div>
  );
  return (
    <>
      <PageHead title="미션" />
      {!d.unlocked && <p className="caution">미션 보상은 정원 레벨 {me?.unlock_levels.missions}부터 받을 수 있어요.</p>}
      <h3>오늘의 미션</h3>
      <div className="list">{d.daily.map((m) => <Row key={m.id} m={m} />)}</div>
      <p className="tiny muted">오늘 미션을 모두 받으면 도전권 +1</p>
      <h3>이번 주 미션</h3>
      <div className="list">{d.weekly.map((m) => <Row key={m.id} m={m} />)}</div>
      {matPick && (
        <div className="card pop">
          <h3>받을 재료를 골라 주세요 (30개)</h3>
          <div className="grid3">
            {['plastic', 'paper', 'metal', 'glass', 'vinyl'].map((k) => <button key={k} className="btn ghost sm" onClick={() => pickMat(k)}>{MAT_NAMES[k]}</button>)}
          </div>
        </div>
      )}
    </>
  );
}
