import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Remon } from '../components/Art';
import { Mat, PageHead, Stars } from '../components/common';
import { get } from '../lib/api';
import { TYPE_NAMES } from '../lib/labels';
import { useStore } from '../lib/store';
import type { Monster } from '../lib/types';

export default function Monsters() {
  const { me } = useStore();
  const [list, setList] = useState<Monster[]>([]);
  useEffect(() => {
    get<{ monsters: Monster[] }>('/monsters').then((r) => setList(r.monsters));
  }, []);
  return (
    <>
      <PageHead title="내 리몬" back={false} right={<div className="row" style={{ gap: 6 }}><Link className="btn ghost sm" to="/party">파티</Link><Link className="btn ghost sm" to="/dex">도감</Link></div>} />
      {me && (
        <div className="card">
          <div className="row wrap" style={{ gap: 12 }}>
            {(['plastic', 'paper', 'metal', 'glass', 'vinyl', 'volt', 'fabric'] as const).map((k) => <Mat key={k} k={k} n={me.materials[k]} />)}
          </div>
        </div>
      )}
      <div className="mon-grid">
        {list.map((m) => (
          <Link key={m.id} to={`/monsters/${m.id}`} className="mon-card">
            {m.slot !== null && <span className="slot-tag">파티</span>}
            {m.on_expedition && <span className="exp-tag">탐사</span>}
            <Remon art={m.art} shiny={m.is_shiny} />
            <span className="nm">{m.name}</span>
            <span className="row" style={{ gap: 4 }}>
              <span className={`chip ${m.type}`}>{TYPE_NAMES[m.type]}</span>
            </span>
            <span className="tiny muted">Lv{m.level} <Stars n={m.stars} /></span>
          </Link>
        ))}
      </div>
      {list.length < 3 && <p className="small muted center">배출 인증을 하면 캡슐이 나와요. 캡슐에서 새 리몬을 만날 수 있어요.</p>}
    </>
  );
}
