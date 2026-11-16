import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon, Remon } from '../components/Art';
import { Modal, PageHead } from '../components/common';
import { get, send } from '../lib/api';
import { RARITY_NAMES, TYPE_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';

interface Cap { id: number; type: string; source: string }
interface Opened { name: string; rarity: string; shiny: boolean; duplicate: boolean; stars: number; art: string; type: string; monster_id: number }

const SOURCE: Record<string, string> = { verify: '배출 인증', weekly: '주간 미션', raid_kill: '레이드 처치' };

export default function Capsules() {
  const { refresh, toast } = useStore();
  const [caps, setCaps] = useState<Cap[]>([]);
  const [opening, setOpening] = useState<Cap | null>(null);
  const [result, setResult] = useState<Opened | null>(null);

  const load = () => get<Cap[]>('/capsules').then(setCaps);
  useEffect(() => { void load(); }, []);

  async function open(c: Cap) {
    setOpening(c);
    setResult(null);
    try {
      const [r] = await Promise.all([send<Opened>(`/capsules/${c.id}/open`, 'POST'), new Promise((ok) => setTimeout(ok, 1300))]);
      setResult(r);
      void load();
      void refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
      setOpening(null);
    }
  }

  return (
    <>
      <PageHead title="캡슐" />
      {caps.length === 0 && (
        <div className="empty">
          <Icon name="capsule_plastic" size={80} />
          <p>열 캡슐이 없어요. 배출 인증을 하면 캡슐이 나와요.</p>
          <Link className="btn" to="/verify" style={{ marginTop: 12 }}>배출 인증하러 가기</Link>
        </div>
      )}
      <div className="grid3">
        {caps.map((c) => (
          <button key={c.id} className="mon-card" onClick={() => open(c)}>
            <Icon name={`capsule_${c.type}`} size={72} />
            <span className="nm">{TYPE_NAMES[c.type]} 캡슐</span>
            <span className="tiny muted">{SOURCE[c.source] ?? c.source}</span>
          </button>
        ))}
      </div>
      <p className="tiny muted">희귀가 4번 연속 안 나오면 다음은 희귀 확정이에요. 가방의 물건이 모두 깨끗했다면 희귀 확률이 올라가요.</p>

      {opening && (
        <Modal onClose={() => result && setOpening(null)}>
          {!result ? (
            <div className="capsule-stage">
              <Icon className="cap" name={`capsule_${opening.type}`} size={140} />
              <p className="muted">두근두근…</p>
            </div>
          ) : (
            <>
              <div className="capsule-stage">
                <div className={result.rarity !== 'common' || result.shiny ? 'shine' : ''}>
                  <Remon className="reveal" art={result.art} shiny={result.shiny} mood="happy" />
                </div>
                <div className="row" style={{ gap: 6 }}>
                  <span className={`chip ${result.rarity}`}>{RARITY_NAMES[result.rarity]}</span>
                  {result.shiny && <span className="chip volt">반짝이!</span>}
                </div>
                <h2 className="center">{result.name}</h2>
                <p className="small muted center">{result.duplicate ? `이미 있는 리몬이라 별이 올랐어요 (★${result.stars})` : '새 리몬을 만났어요! 도감에 기록했어요'}</p>
              </div>
              <div className="row" style={{ gap: 8 }}>
                <Link className="btn ghost grow" to={`/monsters/${result.monster_id}`}>보러 가기</Link>
                <button className="btn grow" onClick={() => setOpening(null)}>확인</button>
              </div>
            </>
          )}
        </Modal>
      )}
    </>
  );
}
