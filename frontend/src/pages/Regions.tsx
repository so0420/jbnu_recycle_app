import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../components/Art';
import { PageHead } from '../components/common';
import TrashThrow, { type ThrowTarget } from '../components/TrashThrow';
import { get, send } from '../lib/api';
import { STAGE_COLORS } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';
import type { Monster } from '../lib/types';

interface Stage { key: string; name: string }
interface Target {
  unit: string; name: string; sido: string; cleanliness: number; verifs: number; stage: Stage; rank: number;
  damage: number; mods: string[]; hit_today: number; my_today: number; can: boolean;
}
interface Overview {
  unit: string; name: string; sido: string; mode: string;
  mine: { cleanliness: number; stage: Stage; rank: number | null; verifs: number; hit_today: number };
  confirmed: boolean; attack_tickets: number; cap: number; daily_per_target: number;
  cleanse: { amount: number; mods: string[]; can: boolean };
  total: number; targets: Target[]; thrower: Monster | null;
}
interface AttackRes {
  target: ThrowTarget & { unit: string; sido: string; rank_before: number | null };
  from: { unit: string; name: string }; damage: number; planned: number; mods: string[]; attack_tickets: number;
}
interface CleanseRes {
  target: ThrowTarget & { unit: string; sido: string }; amount: number; planned: number; mods: string[]; attack_tickets: number;
}
/** 공격·정화 결과를 연출과 결과 카드에 쓰는 한 형태로 */
interface Outcome { mode: 'attack' | 'cleanse'; target: ThrowTarget; delta: number; planned: number; mods: string[]; tickets: number }
interface Ev { type: string; amount: number; nickname: string | null; at: string; dir?: 'in' | 'out'; other?: string }

const MODE_TEXT: Record<string, string> = { sigungu: '전국 시·군·구', zone: '전주 권역', dong: '행정동' };
const MOD_TEXT: Record<string, { label: string; cls: string; desc: string }> = {
  underdog: { label: '역전 ×1.2', cls: 'ok', desc: '우리보다 순위가 높은 지역이라 피해가 커요' },
  fatigue: { label: '많이 맞음 ×0.5', cls: 'common', desc: '오늘 이미 많이 공격받은 지역이라 피해가 줄어요' },
  crisis: { label: '위기 보호 ×0.5', cls: 'bad', desc: '청결도가 위기인 지역이라 피해가 줄어요' },
  crisis_boost: { label: '위기 회복 ×1.5', cls: 'ok', desc: '청결도가 위기라서 더 크게 회복했어요' },
};

function day(at: string) {
  return `${Number(at.slice(5, 7))}월 ${Number(at.slice(8, 10))}일`;
}

export default function Regions() {
  const { refresh, toast } = useStore();
  const [ov, setOv] = useState<Overview | null>(null);
  const [err, setErr] = useState('');
  const [feed, setFeed] = useState<Ev[]>([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [hit, setHit] = useState<Outcome | null>(null);
  const [hitDone, setHitDone] = useState(false);

  const load = async () => {
    try {
      const o = await get<Overview>('/attack');
      setOv(o);
      get<Ev[]>(`/regions/${encodeURIComponent(o.unit)}/feed`).then(setFeed).catch(() => setFeed([]));
    } catch (e) {
      setErr(errMsg(e));
    }
  };
  useEffect(() => { void load(); }, []);

  async function attack(t: Target) {
    setBusy(true);
    try {
      const r = await send<AttackRes>('/attack', 'POST', { target: t.unit });
      setHitDone(false);
      setHit({ mode: 'attack', target: r.target, delta: r.damage, planned: r.planned, mods: r.mods, tickets: r.attack_tickets });
      window.scrollTo({ top: 0 });
      void refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
      void load();
    } finally {
      setBusy(false);
    }
  }

  async function cleanse() {
    setBusy(true);
    try {
      const r = await send<CleanseRes>('/attack/cleanse', 'POST');
      setHitDone(false);
      setHit({ mode: 'cleanse', target: r.target, delta: r.amount, planned: r.planned, mods: r.mods, tickets: r.attack_tickets });
      window.scrollTo({ top: 0 });
      void refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
      void load();
    } finally {
      setBusy(false);
    }
  }

  if (err) {
    return (
      <>
        <PageHead title="지역 공방전" />
        <div className="card"><p>{err}</p><Link className="btn" to="/me">내 동네 정하기</Link></div>
      </>
    );
  }
  if (!ov) return <div className="splash">불러오는 중…</div>;

  if (hit) {
    const heal = hit.mode === 'cleanse';
    return (
      <>
        <PageHead title={heal ? `${hit.target.name} 정화!` : `${hit.target.name} 공격!`} back={false} />
        <TrashThrow mode={hit.mode} thrower={ov.thrower} fromName={ov.name} target={hit.target} damage={hit.delta} onDone={() => setHitDone(true)} />
        {hitDone && (
          <div className="card pop">
            <h2>{heal ? '우리 동네를 깨끗하게 정화했어요!' : `${hit.target.name}에 쓰레기를 던졌어요!`}</h2>
            <p>청결도 <b className="num">{Math.round(hit.target.before)} → {Math.round(hit.target.after)}</b>
              {' '}<span className={`chip ${heal ? 'ok' : 'bad'}`}>{heal ? '+' : '−'}{hit.delta}</span> · {hit.target.stage.name}</p>
            {hit.mods.length > 0 && (
              <div className="col" style={{ gap: 4 }}>
                {hit.mods.map((m) => <span key={m} className="small muted">· {MOD_TEXT[m]?.desc ?? m}</span>)}
              </div>
            )}
            {hit.delta < hit.planned && <p className="small muted">{heal ? '청결도는 1000을 넘지 않아요.' : '청결도는 최저치 아래로 내려가지 않아요.'}</p>}
            <p className="small muted">남은 공격권 {hit.tickets}장.{heal ? '' : ' 상대 지역도 분리배출이나 정화로 청결도를 되찾을 수 있어요.'}</p>
            <button className="btn block" onClick={() => { setHit(null); void load(); }}>확인</button>
          </div>
        )}
      </>
    );
  }

  const tickets = ov.attack_tickets;
  const list = q.trim() ? ov.targets.filter((t) => t.name.includes(q.trim()) || t.sido.includes(q.trim())) : ov.targets;
  return (
    <>
      <PageHead title="지역 공방전" right={<Link className="btn ghost sm" to="/raid">레이드</Link>} />

      <div className="card pop">
        <div className="row between">
          <div className="col" style={{ gap: 2 }}>
            <span className="tiny muted">우리 지역 · {MODE_TEXT[ov.mode] ?? ''} 대항</span>
            <h2>{ov.name}</h2>
          </div>
          <span className="chip" style={{ color: STAGE_COLORS[ov.mine.stage.key] }}>
            {ov.mine.rank ? `${ov.mine.rank}위 · ` : ''}{ov.mine.stage.name}
          </span>
        </div>
        <div className="row between small">
          <span>청결도</span><b className="num">{ov.mine.cleanliness} / 1000</b>
        </div>
        <div className="bar"><span style={{ width: `${ov.mine.cleanliness / 10}%`, background: STAGE_COLORS[ov.mine.stage.key] }} /></div>
        {ov.mine.hit_today > 0 && (
          <p className="alert-in"><Icon name="trash_bag" size={26} />오늘 다른 지역에서 쓰레기가 날아왔어요 (−{ov.mine.hit_today}). 분리배출 인증으로 되찾아요!</p>
        )}
        <div className="row between">
          <div className="ticket-row" aria-label={`공격권 ${tickets}장`}>
            {Array.from({ length: ov.cap }, (_, i) => <Icon key={i} name="attack" size={30} className={i < tickets ? '' : 'off'} />)}
          </div>
          <b className="num">공격권 {tickets}/{ov.cap}</b>
        </div>
        <button className="btn block" disabled={busy || !ov.confirmed || tickets < 1 || !ov.cleanse.can} onClick={cleanse}>
          <Icon name="clean_spark" size={24} />
          {ov.cleanse.can ? `공격권으로 우리 동네 정화 +${ov.cleanse.amount}` : '우리 동네는 이미 가장 깨끗해요'}
          {ov.cleanse.mods.includes('crisis_boost') ? ' (위기 ×1.5)' : ''}
        </button>
        <p className="tiny muted">공격권은 <b>배출 시간</b>에 <b>우리 동네 수거장</b>에서 배출 인증하면 1장씩 받아요 (하루 보상 3번 안에서). 다른 지역 공격이나 우리 동네 정화에 써요. 레이드 도전권과는 따로예요.</p>
        {!ov.confirmed && <p className="caution">첫 배출 인증으로 내 동네가 확정되면 공격할 수 있어요.</p>}
      </div>

      <div className="row between">
        <h3>공격할 지역 <span className="small muted">이번 주 참여 {ov.total}곳</span></h3>
      </div>
      {ov.targets.length > 8 && (
        <div className="field"><input placeholder="지역 이름으로 찾기" value={q} onChange={(e) => setQ(e.target.value)} aria-label="지역 찾기" /></div>
      )}
      {ov.targets.length === 0 && <p className="empty">아직 이번 주에 분리배출한 다른 지역이 없어요.</p>}
      <div className="list">
        {list.map((t) => {
          const disabled = busy || !ov.confirmed || tickets < 1 || !t.can;
          return (
            <div key={t.unit} className="atk-row">
              <span className="rk">{t.rank}</span>
              <div className="col" style={{ gap: 4, minWidth: 0 }}>
                <div className="row between" style={{ gap: 6 }}>
                  <b style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.name} <span className="tiny muted">{t.sido}</span>
                  </b>
                  <span className="num small" style={{ color: STAGE_COLORS[t.stage.key] }}>{t.cleanliness}</span>
                </div>
                <div className="bar"><span style={{ width: `${t.cleanliness / 10}%`, background: STAGE_COLORS[t.stage.key] }} /></div>
                {(t.mods.length > 0 || t.my_today > 0) && (
                  <div className="mods">
                    {t.mods.map((m) => <span key={m} className={`chip ${MOD_TEXT[m]?.cls ?? ''}`}>{MOD_TEXT[m]?.label ?? m}</span>)}
                    {t.my_today > 0 && <span className="chip common">오늘 {t.my_today}/{ov.daily_per_target}</span>}
                  </div>
                )}
              </div>
              <button className="btn sm danger" disabled={disabled} onClick={() => attack(t)}
                      aria-label={`${t.name} 공격, 예상 피해 ${t.damage}`}>
                공격<small>−{t.damage}</small>
              </button>
            </div>
          );
        })}
      </div>

      <div className="card">
        <h3>우리 동네 소식</h3>
        {feed.length === 0 && <p className="small muted">아직 소식이 없어요</p>}
        {feed.map((e, i) => (
          <p key={i} className="small">
            {e.type === 'restore' && `${e.nickname ?? '누군가'}님이 분리배출했어요 (+${e.amount})`}
            {e.type === 'raid_kill' && `레이드 보스를 쓰러뜨렸어요! (+${e.amount})`}
            {e.type === 'cleanse' && <span style={{ color: '#2e9a5a' }}>{e.nickname ?? '누군가'}님이 공격권으로 정화했어요 (+{e.amount})</span>}
            {e.type === 'attack' && e.dir === 'in' && <span style={{ color: 'var(--bad)' }}>{e.other}에서 쓰레기가 날아왔어요 ({e.amount})</span>}
            {e.type === 'attack' && e.dir === 'out' && `${e.nickname ?? '우리 주민'}님이 ${e.other}에 쓰레기를 던졌어요 (${e.amount})`}
            <span className="tiny muted"> · {day(e.at)}</span>
          </p>
        ))}
      </div>

      <details className="card">
        <summary><b>공방전 규칙</b></summary>
        <ul className="small" style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
          <li>공격권 1장으로 이번 주에 분리배출한 다른 지역에 쓰레기를 던져 청결도를 깎아요.</li>
          <li>피해는 인구를 고려해 정해요. 인구가 적은 지역 주민일수록 한 번의 공격(그리고 회복)이 커요.</li>
          <li>우리보다 순위가 높은 지역을 공격하면 피해 ×1.2. 오늘 이미 많이 맞은 지역과 위기 지역(청결도 200 미만)은 피해가 절반이에요.</li>
          <li>같은 지역은 하루 {ov.daily_per_target}번까지 공격할 수 있고, 공격권은 {ov.cap}장까지 모을 수 있어요.</li>
          <li>방어는 분리배출이에요. 우리 동네 수거장에서 인증하면 청결도가 회복되고, 레이드 보스를 쓰러뜨리면 크게 회복해요.</li>
          <li>공격권 1장으로 우리 동네를 정화할 수도 있어요. 회복량은 공격 1회와 같고, 위기 지역(청결도 200 미만)이면 1.5배예요.</li>
          <li>매일 자정 생활 쓰레기만큼 청결도가 내려가고, 순위는 매주 월요일에 새로 시작해요.</li>
        </ul>
      </details>
    </>
  );
}
