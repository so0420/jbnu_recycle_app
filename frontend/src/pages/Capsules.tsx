import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon, Remon } from '../components/Art';
import { Modal, PageHead } from '../components/common';
import { get, send } from '../lib/api';
import { MAT_NAMES, RARITY_NAMES, TYPE_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';

interface Cap { id: number; type: string; source: string }
interface Opened {
  name: string; rarity: string; shiny: boolean; duplicate: boolean; stars: number; art: string; type: string; monster_id: number;
  overflow?: { material: string; amount: number } | null;
  legend?: { monster_id: number; name: string; art: string };
}

interface Rates { rare_rate: number; clean_bonus_rate: number; pity: number; shiny_rate: number; shiny_clean_rate: number; max_stars: number; dup_overflow_materials: number }
const pct = (x: number) => `${Math.round(x * 1000) / 10}%`;

const SOURCE: Record<string, string> = { verify: '배출 인증', weekly: '주간 미션', raid_kill: '레이드 처치' };

export default function Capsules() {
  const { refresh, toast } = useStore();
  const [caps, setCaps] = useState<Cap[]>([]);
  const [opening, setOpening] = useState<Cap | null>(null);
  const [result, setResult] = useState<Opened | null>(null);

  const [rates, setRates] = useState<Rates | null>(null);
  const load = () => get<Cap[]>('/capsules').then(setCaps).catch((e) => toast(errMsg(e), 'err'));
  useEffect(() => {
    void load();
    get<Rates>('/capsules/rates').then(setRates).catch(() => {});
  }, []);

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
      {rates && (
        <details className="card">
          <summary><b>캡슐 확률</b></summary>
          <ul className="small" style={{ margin: '8px 0 0', paddingLeft: 18 }}>
            <li>일반 {pct(1 - rates.rare_rate)} · 희귀 {pct(rates.rare_rate)}</li>
            <li>정산한 가방 물건이 모두 깨끗했으면 희귀 +{pct(rates.clean_bonus_rate)}p, 반짝이 {pct(rates.shiny_clean_rate)} (평소 {pct(rates.shiny_rate)})</li>
            <li>희귀가 {rates.pity - 1}번 연속 안 나오면 {rates.pity}번째는 희귀 확정</li>
            <li>특수 수거함(폐건전지·의류) 캡슐은 그 타입의 에픽 리몬 확정</li>
            <li>같은 종류가 나오면 별이 하나 늘고(최대 {rates.max_stars}개), 별이 가득하면 재료 {rates.dup_overflow_materials}개로 바뀌어요</li>
            <li>일반·희귀 리몬 10종을 모두 모으면 전설의 리몬이 찾아와요</li>
          </ul>
        </details>
      )}

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
                <p className="small muted center">
                  {!result.duplicate
                    ? '새 리몬을 만났어요! 도감에 기록했어요'
                    : result.overflow
                      ? `별이 가득 차서 ${MAT_NAMES[result.overflow.material]} ${result.overflow.amount}개로 바뀌었어요`
                      : `이미 있는 리몬이라 별이 올랐어요 (★${result.stars})`}
                </p>
                {result.legend && (
                  <div className="col center" style={{ alignItems: 'center' }}>
                    <div className="shine"><Remon art={result.legend.art} mood="happy" size={140} /></div>
                    <b>10종을 모두 모아 전설의 리몬 「{result.legend.name}」이 찾아왔어요!</b>
                  </div>
                )}
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
