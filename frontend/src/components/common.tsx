import { useEffect, useRef, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from './Art';
import { dumpWindowText, MAT_NAMES, WEEKDAYS } from '../lib/labels';

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

// 열린 창 목록: 안드로이드 뒤로 가기는 화면을 넘기기 전에 맨 위 창부터 닫는다
const modalStack: { close?: () => void }[] = [];

export function closeTopModal(): boolean {
  const top = modalStack[modalStack.length - 1];
  if (!top) return false;
  top.close?.();
  return true;
}

export function Modal({ children, onClose }: { children: ReactNode; onClose?: () => void }) {
  const entry = useRef<{ close?: () => void }>({});
  entry.current.close = onClose;
  useEffect(() => {
    const e = entry.current;
    modalStack.push(e);
    return () => { const i = modalStack.indexOf(e); if (i >= 0) modalStack.splice(i, 1); };
  }, []);
  return (
    <div className="modal-bg" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

/** 우리 동네 요일별 배출 품목 표 */
export function DumpSchedule({ s }: { s: { days: { weekday: number; items: string[] }[]; note: string | null } }) {
  return (
    <div className="dump-sched">
      {s.days.map((d) => (
        <div key={d.weekday} className="dump-day">
          <div className="col" style={{ gap: 0 }}>
            <b>{WEEKDAYS[d.weekday]}요일 수거</b>
            <span className="tiny muted">{dumpWindowText(d.weekday)}에 내놓기</span>
          </div>
          <span className="small">{d.items.join(' · ')}</span>
        </div>
      ))}
      {s.note && <p className="tiny muted">{s.note}</p>}
    </div>
  );
}

export function Stars({ n }: { n: number }) {
  if (!n) return null;
  return <span className="stars" aria-label={`별 ${n}개`}>{'★'.repeat(n)}</span>;
}

export function LoadError({ msg, onRetry }: { msg: string; onRetry: () => void }) {
  return (
    <div className="empty">
      <p>{msg}</p>
      <button className="btn" style={{ marginTop: 12 }} onClick={onRetry}>다시 시도</button>
    </div>
  );
}
