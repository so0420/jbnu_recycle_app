import { useEffect, useState } from 'react';
import { PageHead } from '../components/common';
import { get, send } from '../lib/api';
import { fmt } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';

interface Stats {
  users: number; scans_7d: number; judged_by_7d: Record<string, number>; system_one_ratio: number | null;
  avg_latency_ms: number; verifications_7d: Record<string, number>; fail_codes_7d: Record<string, number>;
  openai_tokens_today: number; openai_daily_limit: number;
}
interface V { id: number; user_id: number; at: string; result: string; fail_code: string | null; flag_reason: string | null; score: number | null; judged_by: string; distance_m: number | null; has_photo: boolean }

export default function Admin() {
  const { toast } = useStore();
  const [s, setS] = useState<Stats | null>(null);
  const [vs, setVs] = useState<V[]>([]);
  const [err, setErr] = useState('');
  const load = () => {
    get<Stats>('/admin/stats').then(setS).catch((e) => setErr(errMsg(e)));
    get<V[]>('/admin/verifications').then(setVs).catch(() => {});
  };
  useEffect(load, []);
  if (err) return <div className="empty">{err}</div>;
  if (!s) return <div className="splash">불러오는 중…</div>;
  return (
    <>
      <PageHead title="관리자" />
      <div className="card">
        <h3>최근 7일</h3>
        <dl className="kv">
          <dt>가입자</dt><dd>{fmt(s.users)}명</dd>
          <dt>스캔</dt><dd>{fmt(s.scans_7d)}건 · 1차(로컬 AI)에서 끝난 비율 {s.system_one_ratio !== null ? `${Math.round(s.system_one_ratio * 100)}%` : '-'}</dd>
          <dt>판정 방식</dt><dd>{Object.entries(s.judged_by_7d).map(([k, v]) => `${k} ${v}`).join(' · ') || '-'}</dd>
          <dt>평균 응답</dt><dd>{(s.avg_latency_ms / 1000).toFixed(1)}초</dd>
          <dt>인증</dt><dd>{Object.entries(s.verifications_7d).map(([k, v]) => `${k} ${v}`).join(' · ') || '-'}</dd>
          <dt>실패 사유</dt><dd>{Object.entries(s.fail_codes_7d).map(([k, v]) => `${k} ${v}`).join(' · ') || '-'}</dd>
          <dt>OpenAI 오늘</dt><dd>{fmt(s.openai_tokens_today)} / {fmt(s.openai_daily_limit)} 토큰</dd>
        </dl>
      </div>
      <h3>검토가 필요한 인증</h3>
      {vs.length === 0 && <p className="small muted">없어요</p>}
      <div className="list">
        {vs.map((v) => (
          <div key={v.id} className="card">
            <div className="row between"><b>#{v.id} · 사용자 {v.user_id}</b><span className="tiny muted">{new Date(v.at).toLocaleString('ko-KR')}</span></div>
            <p className="small">{v.flag_reason} · 점수 {v.score?.toFixed(2) ?? '-'} · {v.distance_m ?? '-'}m</p>
            {v.has_photo && <img className="shot" src={`/api/v1/admin/photo/verify/${v.id}`} alt={`인증 ${v.id} 사진`} loading="lazy" />}
            <button className="btn ghost sm" onClick={async () => { try { await send(`/admin/verifications/${v.id}/clear`, 'POST'); load(); } catch (e) { toast(errMsg(e), 'err'); } }}>문제없음</button>
          </div>
        ))}
      </div>
    </>
  );
}
