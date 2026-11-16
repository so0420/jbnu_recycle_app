import { useEffect, useState } from 'react';
import { PageHead } from '../components/common';
import { get } from '../lib/api';
import { STAGE_COLORS } from '../lib/labels';
import { useStore } from '../lib/store';

interface Row { unit: string; name: string; cleanliness: number; verifs: number; stage: { key: string; name: string }; rank: number }
interface Ev { type: string; amount: number; nickname: string | null; at: string }

export default function Regions() {
  const { me } = useStore();
  const [rows, setRows] = useState<Row[]>([]);
  const [feed, setFeed] = useState<Ev[]>([]);
  const mine = me?.region?.unit;
  useEffect(() => {
    get<Row[]>('/regions').then(setRows);
    if (mine) get<Ev[]>(`/regions/${mine}/feed`).then(setFeed);
  }, [mine]);
  return (
    <>
      <PageHead title="동네 청결도" />
      <p className="small muted">우리 동네 수거장에서 인증하면 청결도가 오르고, 매일 자정 생활 쓰레기만큼 내려가요. 레이드 보스를 쓰러뜨리면 크게 회복해요. 순위는 인구 대비 참여율로 공평하게 계산해요. 매주 월요일에 새로 시작해요.</p>
      <div className="list">
        {rows.map((r) => (
          <div key={r.unit} className={`rank-row ${r.unit === mine ? 'mine' : ''}`}>
            <span className="rk">{r.rank}</span>
            <div className="col" style={{ gap: 4 }}>
              <b>{r.name}{r.unit === mine ? ' (우리)' : ''}</b>
              <div className="bar"><span style={{ width: `${r.cleanliness / 10}%`, background: STAGE_COLORS[r.stage.key] }} /></div>
            </div>
            <span className="num small" style={{ color: STAGE_COLORS[r.stage.key] }}>{r.cleanliness}<br /><span className="tiny">{r.stage.name}</span></span>
          </div>
        ))}
      </div>
      {mine && (
        <div className="card">
          <h3>우리 동네 소식</h3>
          {feed.length === 0 && <p className="small muted">아직 소식이 없어요</p>}
          {feed.map((e, i) => (
            <p key={i} className="small">
              {e.type === 'restore' && `${e.nickname ?? '누군가'}님이 분리배출했어요 (+${e.amount})`}
              {e.type === 'raid_kill' && `레이드 보스를 쓰러뜨렸어요! (+${e.amount})`}
              <span className="tiny muted"> · {new Date(e.at).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
            </p>
          ))}
        </div>
      )}
    </>
  );
}
