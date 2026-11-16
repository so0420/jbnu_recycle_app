import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Remon } from '../components/Art';
import { Mat, Modal, PageHead, Stars } from '../components/common';
import { get, send } from '../lib/api';
import { MAT_NAMES, RARITY_NAMES, ROLE_NAMES, TYPE_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';
import type { Monster } from '../lib/types';

interface MonstersRes { monsters: Monster[]; habits: Record<string, number>; habit_names: Record<string, string> }

export default function MonsterDetail() {
  const { id } = useParams();
  const { me, refresh, toast } = useStore();
  const [data, setData] = useState<MonstersRes | null>(null);
  const [evolved, setEvolved] = useState<Monster | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => get<MonstersRes>('/monsters').then(setData);
  useEffect(() => { void load(); }, [id]);

  const m = data?.monsters.find((x) => String(x.id) === id);
  if (!data) return <div className="splash">불러오는 중…</div>;
  if (!m) return <div className="empty">리몬을 찾을 수 없어요</div>;

  async function act(path: string, ok: string) {
    setBusy(true);
    try {
      const r = await send<{ monster?: Monster; evolved?: { name: string } } & Partial<Monster>>(path, 'POST');
      if (r.evolved && r.monster) setEvolved(r.monster);
      else toast(ok);
      await Promise.all([load(), refresh()]);
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }

  const cost = m.levelup_cost;
  const have = cost && me ? me.materials[cost.material] : 0;
  const expDone = m.expedition_until && new Date(m.expedition_until) <= new Date();
  const ev = m.evolve;
  const habitName = data.habit_names[m.type] ?? '올바른 습관';

  return (
    <>
      <PageHead title={m.name} />
      <div className="card pop">
        <div className="hero"><Remon art={m.art} shiny={m.is_shiny} mood="happy" /></div>
        <div className="row wrap center" style={{ justifyContent: 'center', gap: 6 }}>
          <span className={`chip ${m.type}`}>{TYPE_NAMES[m.type]}</span>
          <span className={`chip ${m.rarity}`}>{RARITY_NAMES[m.rarity]}</span>
          <span className="chip common">{ROLE_NAMES[m.role]}</span>
          {m.is_shiny && <span className="chip volt">반짝이</span>}
        </div>
        <p className="center"><b>Lv{m.level}</b> / {m.level_cap} · {m.stage}단계 <Stars n={m.stars} /></p>
        <div className="stat-grid">
          <div><span className="tiny muted">체력</span><b>{m.stats.hp}</b></div>
          <div><span className="tiny muted">공격</span><b>{m.stats.atk}</b></div>
          <div><span className="tiny muted">방어</span><b>{m.stats.def}</b></div>
          <div><span className="tiny muted">속도</span><b>{m.stats.spd}</b></div>
        </div>
        <div className="col" style={{ gap: 2 }}>
          <b>스킬 · {m.skill.name}</b>
          <span className="small muted">{m.skill.desc}</span>
        </div>
        <p className="small muted">{m.desc}</p>
      </div>

      {cost && (
        <div className="card">
          <div className="row between">
            <h3>레벨업</h3>
            <span className="row small" style={{ gap: 8 }}>
              <Mat k={cost.material} n={cost.materials} /> 코인 {cost.coins}
            </span>
          </div>
          <p className="small muted">{MAT_NAMES[cost.material]} {have} / {cost.materials} 보유 · 코인 {me?.coins ?? 0}</p>
          <button className="btn block" disabled={busy || m.on_expedition} onClick={() => act(`/monsters/${m.id}/levelup`, `Lv${m.level + 1}이 됐어요!`)}>레벨업</button>
        </div>
      )}

      {ev && (
        <div className="card">
          <h3>진화 ({ev.to_stage}단계)</h3>
          <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
            <li style={{ color: m.level >= ev.level ? 'var(--accent)' : undefined }}>Lv{ev.level} 달성 (지금 {m.level})</li>
            <li style={{ color: ev.habit_now >= ev.habits ? 'var(--accent)' : undefined }}>'{habitName}' 스캔 {ev.habits}번 (지금 {ev.habit_now}번)</li>
            <li>{MAT_NAMES[cost?.material ?? m.type] ?? '재료'} {ev.materials}개{ev.crystals ? ` + 정화의 결정 ${ev.crystals}개` : ''}</li>
          </ul>
          <button className="btn warn block" disabled={busy || m.level < ev.level || ev.habit_now < ev.habits} onClick={() => act(`/monsters/${m.id}/evolve`, '진화했어요!')}>진화하기</button>
        </div>
      )}

      {me?.unlocks.expedition && (
        <div className="card">
          <h3>탐사</h3>
          <p className="small muted">12시간 동안 탐사를 보내면 {MAT_NAMES[m.type] ?? '재료'} {2 * (me?.economy_multiplier ?? 1)}개와 코인 {15 * (me?.economy_multiplier ?? 1)}을 가져와요. 탐사 중에는 파티에서 빠지고, 돌아오면 빈자리에 다시 들어가요.</p>
          {m.on_expedition ? (
            <button className="btn block" disabled={busy || !expDone} onClick={() => act(`/monsters/${m.id}/expedition/claim`, '탐사 보상을 받았어요')}>
              {expDone ? '보상 받기' : `돌아오는 시간 ${new Date(m.expedition_until!).toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit' })}`}
            </button>
          ) : (
            <button className="btn ghost block" disabled={busy} onClick={() => act(`/monsters/${m.id}/expedition`, '탐사를 보냈어요')}>탐사 보내기</button>
          )}
        </div>
      )}

      {evolved && (
        <Modal onClose={() => setEvolved(null)}>
          <div className="capsule-stage">
            <div className="shine"><Remon className="reveal" art={evolved.art} shiny={evolved.is_shiny} mood="happy" /></div>
            <h2>{evolved.name}(으)로 진화했어요!</h2>
          </div>
          <button className="btn block" onClick={() => setEvolved(null)}>좋아요</button>
        </Modal>
      )}
    </>
  );
}
