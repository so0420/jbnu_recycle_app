import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Boss, Icon, Remon } from '../components/Art';
import BattlePlayer from '../components/BattlePlayer';
import { PageHead } from '../components/common';
import { get, send } from '../lib/api';
import { fmt, TYPE_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';
import type { BattleEvent, BattleUnit, Monster } from '../lib/types';

interface BossView { key: string; name: string; weak: string; desc: string; habit: string }
interface RaidRes {
  unit: string; boss: BossView; hp: number; max_hp: number; killed: boolean; next_boss: BossView;
  board: { nickname: string; damage: number; attempts: number }[]; my_damage: number; my_attempts: number;
  free_left: boolean; tickets: number; unlocked: boolean; party: Monster[];
}
interface AttemptRes {
  damage: number; boss_hp: number; boss_max_hp: number; killed: boolean; free: boolean;
  battle: { units: BattleUnit[]; log: BattleEvent[]; rounds: number; wiped: boolean };
  reward: { coins: number; materials: Record<string, number>; xp?: number };
}

const weakText = (w: string) => (w === 'rotate' ? '3라운드마다 바뀜' : TYPE_NAMES[w]);

export default function Raid() {
  const { me, refresh, toast } = useStore();
  const [r, setR] = useState<RaidRes | null>(null);
  const [err, setErr] = useState('');
  const [battle, setBattle] = useState<AttemptRes | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = () => get<RaidRes>('/raid').then(setR).catch((e) => setErr(errMsg(e)));
  useEffect(() => { void load(); }, []);

  async function go() {
    setBusy(true);
    setDone(false);
    try {
      const a = await send<AttemptRes>('/raid/attempt', 'POST');
      setBattle(a);
      void refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }

  if (err) return (<><PageHead title="동네 레이드" back={false} /><div className="card"><p>{err}</p><Link className="btn" to="/me">내 동네 정하기</Link></div></>);
  if (!r) return <div className="splash">불러오는 중…</div>;

  if (battle) {
    return (
      <>
        <PageHead title={r.boss.name} back={false} />
        <BattlePlayer units={battle.battle.units} log={battle.battle.log} onDone={() => setDone(true)} />
        {done && (
          <div className="card pop">
            <h2>{battle.killed ? '보스를 쓰러뜨렸어요!' : `피해 ${fmt(battle.damage)}`}</h2>
            <div className="boss-hp">
              <div className="bar red"><span style={{ width: `${(battle.boss_hp / battle.boss_max_hp) * 100}%` }} /></div>
              <span className="small muted num">남은 체력 {fmt(battle.boss_hp)} / {fmt(battle.boss_max_hp)}</span>
            </div>
            <p className="small">보상: 코인 +{battle.reward.coins}
              {Object.entries(battle.reward.materials).map(([k, n]) => ` · ${TYPE_NAMES[k]} 재료 +${n}`).join('')}
              {battle.reward.xp ? ` · 경험치 +${battle.reward.xp}` : ''}</p>
            {battle.killed && <p className="small">참여한 모두에게 캡슐과 정화의 결정을 보냈어요!</p>}
            <button className="btn block" onClick={() => { setBattle(null); void load(); }}>확인</button>
          </div>
        )}
      </>
    );
  }

  if (!r.unlocked) {
    return (
      <>
        <PageHead title="동네 레이드" back={false} />
        <div className="card center">
          <Boss boss={r.boss.key} size={180} />
          <h2>{r.boss.name}</h2>
          <p className="muted">레이드는 정원 레벨 {me?.unlock_levels.raid}에 열려요. 스캔과 배출 인증으로 레벨을 올려 주세요!</p>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHead title="동네 레이드" back={false} right={<Link className="btn ghost sm" to="/regions">청결도</Link>} />
      <div className="card pop">
        <div className="center"><Boss boss={r.boss.key} size={200} hurt={r.killed} /></div>
        <div className="row between wrap">
          <h2>{r.boss.name}</h2>
          <span className="chip bad">약점 {weakText(r.boss.weak)}</span>
        </div>
        <div className="boss-hp">
          <div className="bar red"><span style={{ width: `${(r.hp / r.max_hp) * 100}%` }} /></div>
          <span className="small muted num">{fmt(r.hp)} / {fmt(r.max_hp)}</span>
        </div>
        <p className="small">{r.boss.desc}</p>
        <p className="small muted">이 괴물에게서 배우는 습관: <b>{r.boss.habit}</b></p>
      </div>
      <div className="card">
        <div className="row between">
          <h3>내 파티</h3>
          <Link className="btn ghost sm" to="/party">편성</Link>
        </div>
        <div className="row" style={{ gap: 6 }}>
          {r.party.map((m) => (
            <div key={m.id} className="mon-card grow">
              <Remon art={m.art} shiny={m.is_shiny} />
              <span className="nm">{m.name}</span>
              <span className={`chip ${m.type}`}>{TYPE_NAMES[m.type]}</span>
            </div>
          ))}
        </div>
        <button className="btn block" disabled={busy || r.killed || (!r.free_left && r.tickets < 1) || r.party.length === 0} onClick={go}>
          {r.killed ? '이번 주 보스 처치 완료' : r.free_left ? '도전하기 (오늘 무료 1회)' : `도전하기 (도전권 1장 · ${r.tickets}장 보유)`}
        </button>
        <p className="tiny muted center">내 누적 피해 {fmt(r.my_damage)} · {r.my_attempts}회 도전</p>
      </div>
      <div className="card">
        <h3>우리 동네 기여 순위</h3>
        {r.board.length === 0 && <p className="small muted">아직 아무도 도전하지 않았어요. 첫 번째가 되어 보세요!</p>}
        {r.board.map((b, i) => (
          <div key={i} className="row between small"><span>{i + 1}. {b.nickname}</span><span className="num">{fmt(b.damage)} ({b.attempts}회)</span></div>
        ))}
      </div>
      <div className="card">
        <div className="row"><Icon name="raid" size={28} /><h3>다음 주 보스 예고</h3></div>
        <div className="row">
          <Boss boss={r.next_boss.key} size={90} />
          <div className="col" style={{ gap: 2 }}>
            <b>{r.next_boss.name}</b>
            <span className="small muted">약점 {weakText(r.next_boss.weak)} · 미리 키워 두세요!</span>
          </div>
        </div>
      </div>
    </>
  );
}
