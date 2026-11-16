import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Garden, Icon, Remon } from '../components/Art';
import { get } from '../lib/api';
import { dumpDaysText, STAGE_COLORS } from '../lib/labels';
import { useStore } from '../lib/store';
import type { Monster } from '../lib/types';

interface MissionsRes { daily: { progress: number; goal: number; claimed: boolean }[]; weekly: { progress: number; goal: number; claimed: boolean }[]; unlocked: boolean }

export default function Home() {
  const { me, refresh } = useStore();
  const [party, setParty] = useState<Monster[]>([]);
  const [caps, setCaps] = useState(0);
  const [claimable, setClaimable] = useState(0);

  useEffect(() => {
    void refresh();
    get<{ monsters: Monster[] }>('/monsters').then((r) =>
      setParty(r.monsters.filter((m) => m.slot !== null).sort((a, b) => (a.slot ?? 0) - (b.slot ?? 0))),
    );
    get<unknown[]>('/capsules').then((r) => setCaps(r.length));
    get<MissionsRes>('/missions').then((r) =>
      setClaimable(r.unlocked ? [...r.daily, ...r.weekly].filter((m) => !m.claimed && m.progress >= m.goal).length : 0),
    );
  }, [refresh]);

  if (!me) return null;
  const reg = me.region;
  const dim = (reg?.cleanliness ?? 600) < 400;
  const nextDump = me.today.next_dump_at ? new Date(me.today.next_dump_at) : null;

  return (
    <>
      <div className="garden">
        <Garden stage={me.garden_stage} mood={dim ? 'dim' : 'bright'} label="내 정원" />
        <div className="party-on-garden">
          {party.map((m) => <Remon key={m.id} art={m.art} shiny={m.is_shiny} mood={dim ? 'hurt' : 'normal'} label={m.name} />)}
        </div>
      </div>

      <div className="card">
        <div className="row between">
          <div className="col" style={{ gap: 2 }}>
            <span className="tiny muted">
              {reg ? (reg.unit_name && reg.unit_name !== reg.gu ? `${reg.gu} · ${reg.unit_name}` : `${reg.sido} ${reg.gu}`) : '내 동네'}
            </span>
            <h3>{reg ? reg.name : '동네를 정해 주세요'}</h3>
          </div>
          {reg?.stage && (
            <Link to="/regions" className="chip" style={{ color: STAGE_COLORS[reg.stage.key], textDecoration: 'none' }}>
              청결도 {reg.cleanliness} · {reg.stage.name}
            </Link>
          )}
        </div>
        {reg ? (
          <p className="small muted">
            재활용 {dumpDaysText(reg.dump_weekdays)} ·{' '}
            {me.today.dump_time_now && !me.today.dumpday_ticket_taken
              ? <b style={{ color: 'var(--accent)' }}>지금 배출 시간이에요! 인증하면 도전권 +1</b>
              : nextDump
                ? `다음 배출 시간: ${['일', '월', '화', '수', '목', '금', '토'][nextDump.getDay()]}요일 ${nextDump.getHours() >= 12 ? '오후' : '오전'} ${nextDump.getHours() % 12 || 12}시부터`
                : '언제든 배출 인증할 수 있어요'}
          </p>
        ) : (
          <p className="small muted">첫 배출 인증을 하면 그 위치의 동네로 정해져요.</p>
        )}
      </div>

      <div className="big-actions">
        <Link className="btn" to="/scan">쓰레기 스캔<small>버리는 법 + 가방에 담기</small></Link>
        <Link className="btn warn" to="/verify">배출 인증<small>오늘 보상 {me.today.verify_reward_left}번 남음</small></Link>
      </div>

      <div className="quick">
        <Link to="/bag"><Icon name="bag" size={34} />가방 {me.bag.count}/{me.bag.capacity}</Link>
        <Link to="/capsules"><Icon name="capsule_glass" size={34} />캡슐{caps > 0 && <span className="badge">{caps}</span>}</Link>
        <Link to="/missions"><Icon name="stamp" size={34} />미션{claimable > 0 && <span className="badge">{claimable}</span>}</Link>
        <Link to="/dex"><Icon name="type_glass" size={34} />도감</Link>
      </div>

      <div className="card">
        <div className="row between">
          <h3>내 파티</h3>
          <Link className="btn ghost sm" to="/party">편성</Link>
        </div>
        <div className="row" style={{ gap: 6 }}>
          {party.length === 0 && <p className="small muted">파티가 비어 있어요</p>}
          {party.map((m) => (
            <Link key={m.id} to={`/monsters/${m.id}`} className="mon-card grow">
              <Remon art={m.art} shiny={m.is_shiny} />
              <span className="nm">{m.name}</span>
              <span className="tiny muted">Lv{m.level}</span>
            </Link>
          ))}
        </div>
      </div>

      {me.economy_multiplier > 1 && (
        <p className="tiny muted center">테스트 시즌: 보상이 {me.economy_multiplier}배로 지급되고 있어요</p>
      )}
    </>
  );
}
