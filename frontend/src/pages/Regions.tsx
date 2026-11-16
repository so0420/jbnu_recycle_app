import { useEffect, useState } from 'react';
import { PageHead } from '../components/common';
import { get } from '../lib/api';
import { STAGE_COLORS } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';

interface Row { unit: string; name: string; sido: string; cleanliness: number; verifs: number; stage: { key: string; name: string }; rank: number | null }
interface Standings { mode: string; total: number; rows: Row[]; mine: Row | null }
interface Ev { type: string; amount: number; nickname: string | null; at: string }

const MODE_TEXT: Record<string, string> = { sigungu: '전국 시·군·구', zone: '전주 권역', dong: '행정동' };

function RankRow({ r, mine }: { r: Row; mine: boolean }) {
  return (
    <div className={`rank-row ${mine ? 'mine' : ''}`}>
      <span className="rk">{r.rank ?? '–'}</span>
      <div className="col" style={{ gap: 4, minWidth: 0 }}>
        <b style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {r.name}{mine ? ' (우리)' : ''} <span className="tiny muted">{r.sido}</span>
        </b>
        <div className="bar"><span style={{ width: `${r.cleanliness / 10}%`, background: STAGE_COLORS[r.stage.key] }} /></div>
      </div>
      <span className="num small" style={{ color: STAGE_COLORS[r.stage.key], textAlign: 'right' }}>
        {r.cleanliness}<br /><span className="tiny">{r.verifs}회 인증</span>
      </span>
    </div>
  );
}

export default function Regions() {
  const { me, toast } = useStore();
  const [st, setSt] = useState<Standings | null>(null);
  const [feed, setFeed] = useState<Ev[]>([]);
  const mine = me?.region?.unit ?? null;

  useEffect(() => {
    get<Standings>(`/regions${mine ? `?mine=${encodeURIComponent(mine)}` : ''}`).then(setSt)
      .catch((e) => { toast(errMsg(e), 'err'); setSt({ mode: '', total: 0, rows: [], mine: null }); });
    if (mine) get<Ev[]>(`/regions/${encodeURIComponent(mine)}/feed`).then(setFeed);
  }, [mine]);

  if (!st) return <div className="splash">불러오는 중…</div>;
  const mineInTop = st.rows.some((r) => r.unit === mine);

  return (
    <>
      <PageHead title="동네 청결도" />
      <p className="small muted">
        {MODE_TEXT[st.mode] ?? ''} 대항전이에요. 우리 동네 수거장에서 인증하면 청결도가 오르고, 매일 자정 생활 쓰레기만큼 내려가요.
        레이드 보스를 쓰러뜨리면 크게 회복해요. 순위는 인구 대비 참여율로 공평하게 계산하고, 매주 월요일에 새로 시작해요.
      </p>
      {st.mine && !mineInTop && (
        <>
          <h3>우리 동네</h3>
          <RankRow r={st.mine} mine />
        </>
      )}
      <h3>이번 주 순위 <span className="small muted">참여 {st.total}곳</span></h3>
      {st.rows.length === 0 && <p className="empty">아직 이번 주에 인증한 동네가 없어요. 첫 번째가 되어 보세요!</p>}
      <div className="list">
        {st.rows.map((r) => <RankRow key={r.unit} r={r} mine={r.unit === mine} />)}
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
