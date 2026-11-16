import { useEffect, useState } from 'react';
import { get } from '../lib/api';

interface Sgg { code: string; name: string }
interface Dong { code: string; name: string; sigungu_code: string; sido: string }

// 시·도 → 시·군·구 → 행정동 순서로 고르는 동네 선택기
export default function RegionPicker({ value, onChange, idPrefix = 'rp' }: { value: string; onChange: (code: string) => void; idPrefix?: string }) {
  const [sidos, setSidos] = useState<string[]>([]);
  const [sido, setSido] = useState('');
  const [sggs, setSggs] = useState<Sgg[]>([]);
  const [sgg, setSgg] = useState('');
  const [dongs, setDongs] = useState<Dong[]>([]);

  useEffect(() => {
    get<string[]>('/regions/sido').then(setSidos).catch(() => setSidos([]));
  }, []);

  // 이미 정해진 동네가 있으면 상위 선택을 채운다
  useEffect(() => {
    if (!value || sido) return;
    get<{ sido: string; sigungu_code: string }>(`/regions/${value}`)
      .then((r) => { setSido(r.sido); setSgg(r.sigungu_code); })
      .catch(() => {});
  }, [value, sido]);

  useEffect(() => {
    if (!sido) { setSggs([]); return; }
    get<Sgg[]>(`/regions/sigungu?sido=${encodeURIComponent(sido)}`).then(setSggs).catch(() => setSggs([]));
  }, [sido]);

  useEffect(() => {
    if (!sgg) { setDongs([]); return; }
    get<Dong[]>(`/regions/list?sigungu_code=${encodeURIComponent(sgg)}`).then(setDongs).catch(() => setDongs([]));
  }, [sgg]);

  return (
    <div className="col" style={{ gap: 6 }}>
      <select id={`${idPrefix}-sido`} aria-label="시·도" value={sido} onChange={(e) => { setSido(e.target.value); setSgg(''); onChange(''); }}>
        <option value="">시·도 선택</option>
        {sidos.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <select id={`${idPrefix}-sgg`} aria-label="시·군·구" value={sgg} disabled={!sido} onChange={(e) => { setSgg(e.target.value); onChange(''); }}>
        <option value="">시·군·구 선택</option>
        {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
      </select>
      <select id={`${idPrefix}-dong`} aria-label="행정동" value={value} disabled={!sgg} onChange={(e) => onChange(e.target.value)}>
        <option value="">행정동 선택</option>
        {dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
      </select>
    </div>
  );
}
