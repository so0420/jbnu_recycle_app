import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Remon } from '../components/Art';
import { get, send } from '../lib/api';
import { ROLE_NAMES, TYPE_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';

interface StarterRow { species: string; name: string; type: string; role: string; desc: string; art: string }

export default function Starter() {
  const { me, refresh, toast } = useStore();
  const nav = useNavigate();
  const [rows, setRows] = useState<StarterRow[]>([]);
  const [pick, setPick] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (me?.starter_done) nav('/', { replace: true });
    get<{ starters: StarterRow[] }>('/monsters').then((r) => setRows(r.starters));
  }, [me, nav]);

  async function go() {
    setBusy(true);
    try {
      await send('/monsters/starter', 'POST', { species: pick });
      await refresh();
      toast('첫 리몬이 생겼어요!');
      nav('/', { replace: true });
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap" style={{ justifyContent: 'flex-start' }}>
      <h1>첫 리몬을 골라 주세요</h1>
      <p className="muted">리몬은 제대로 버린 쓰레기에서 태어난 친구예요. 함께 동네의 오염 괴물을 물리쳐요.</p>
      <div className="col">
        {rows.map((r) => (
          <button key={r.species} className={`card ${pick === r.species ? 'pop' : ''}`} style={{ textAlign: 'left', cursor: 'pointer' }} onClick={() => setPick(r.species)} aria-pressed={pick === r.species}>
            <div className="row">
              <Remon art={r.art} size={86} mood={pick === r.species ? 'happy' : 'normal'} />
              <div className="col grow" style={{ gap: 4 }}>
                <div className="row wrap" style={{ gap: 6 }}>
                  <h3>{r.name}</h3>
                  <span className={`chip ${r.type}`}>{TYPE_NAMES[r.type]}</span>
                  <span className="chip common">{ROLE_NAMES[r.role]}</span>
                </div>
                <p className="small muted">{r.desc}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
      <button className="btn block" disabled={!pick || busy} onClick={go}>{pick ? '이 리몬과 시작하기' : '리몬을 골라 주세요'}</button>
    </div>
  );
}
