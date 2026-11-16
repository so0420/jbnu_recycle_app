import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from './Art';
import { MAT_NAMES } from '../lib/labels';

export function PageHead({ title, back = true, right }: { title: string; back?: boolean; right?: ReactNode }) {
  const nav = useNavigate();
  return (
    <div className="page-head">
      <div className="row">
        {back && (
          <button className="back" onClick={() => nav(-1)} aria-label="뒤로">
            ←
          </button>
        )}
        <h1>{title}</h1>
      </div>
      {right}
    </div>
  );
}

export function Mat({ k, n }: { k: string; n: number }) {
  return (
    <span className="row" style={{ gap: 4 }} title={MAT_NAMES[k]}>
      <Icon name={`mat_${k}`} size={22} />
      <span className="num small">{n}</span>
    </span>
  );
}

export function Modal({ children, onClose }: { children: ReactNode; onClose?: () => void }) {
  return (
    <div className="modal-bg" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

export function Stars({ n }: { n: number }) {
  if (!n) return null;
  return <span className="stars" aria-label={`별 ${n}개`}>{'★'.repeat(n)}</span>;
}
