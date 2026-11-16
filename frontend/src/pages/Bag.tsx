import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../components/Art';
import { PageHead } from '../components/common';
import { get } from '../lib/api';
import { TYPE_NAMES } from '../lib/labels';

interface BagRes { capacity: number; expire_days: number; items: { id: number; category_name: string; item_name: string | null; type: string; clean: boolean; habit_ok: boolean; at: string }[] }

export default function Bag() {
  const [bag, setBag] = useState<BagRes | null>(null);
  useEffect(() => { get<BagRes>('/bag').then(setBag).catch(() => setBag({ capacity: 0, expire_days: 7, items: [] })); }, []);
  if (!bag) return <div className="splash">불러오는 중…</div>;
  return (
    <>
      <PageHead title={`분리 가방 ${bag.items.length}/${bag.capacity}`} />
      <p className="small muted">집에서 스캔한 물건이 모여 있어요. 수거장에서 배출 인증을 하면 한꺼번에 재료로 바뀌어요. 담은 지 {bag.expire_days}일이 지나면 사라져요.</p>
      {bag.items.length === 0 ? (
        <div className="empty">
          <Icon name="bag" size={80} />
          <p>가방이 비어 있어요</p>
          <Link className="btn" to="/scan" style={{ marginTop: 12 }}>스캔하러 가기</Link>
        </div>
      ) : (
        <div className="list">
          {bag.items.map((it) => (
            <div key={it.id} className="list-item">
              <Icon name={`mat_${it.type}`} size={36} />
              <div className="col grow" style={{ gap: 0 }}>
                <b>{it.item_name ?? it.category_name}</b>
                <span className="tiny muted">{new Date(it.at).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
              </div>
              <span className={`chip ${it.type}`}>{TYPE_NAMES[it.type]}</span>
              {it.clean && <span className="chip ok">깨끗</span>}
              {it.habit_ok && <span className="chip ok">습관</span>}
            </div>
          ))}
        </div>
      )}
      {bag.items.length > 0 && <Link className="btn warn block" to="/verify">수거장에서 정산하기</Link>}
    </>
  );
}
