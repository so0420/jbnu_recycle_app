import L from 'leaflet';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHead } from '../components/common';
import { get } from '../lib/api';
import { getPosition } from '../lib/device';
import type { Place } from '../lib/types';

const JEONJU: [number, number] = [35.8242, 127.148];
const KINDS: { key: string; name: string; color: string }[] = [
  { key: 'recycle_point', name: '분리배출장소', color: '#1E7A4C' },
  { key: 'clothes_bin', name: '의류수거함', color: '#C2577A' },
  { key: 'battery_bin', name: '폐건전지·소형가전', color: '#D9A400' },
  { key: 'reverse_vending', name: '무인회수기', color: '#2C6BCB' },
  { key: 'bag_shop', name: '종량제봉투 판매소', color: '#7B8391' },
];

export default function MapPage() {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const [kinds, setKinds] = useState<string[]>(['recycle_point', 'clothes_bin', 'battery_bin', 'reverse_vending']);
  const [sel, setSel] = useState<Place | null>(null);
  const [count, setCount] = useState(0);
  const kindsRef = useRef(kinds);
  kindsRef.current = kinds;

  async function load() {
    const m = map.current;
    if (!m || !layer.current) return;
    const c = m.getCenter();
    const radius = Math.min(3000, Math.max(300, m.distance(c, m.getBounds().getNorthEast())));
    const rows = await get<Place[]>(`/places?lat=${c.lat}&lng=${c.lng}&radius=${Math.round(radius)}&kind=${kindsRef.current.join(',')}`).catch(() => []);
    layer.current.clearLayers();
    for (const p of rows) {
      const k = KINDS.find((x) => x.key === p.kind);
      L.circleMarker([p.lat, p.lng], {
        radius: p.kind === 'bag_shop' ? 5 : 8, color: '#2A2622', weight: 2,
        fillColor: p.is_active ? (k?.color ?? '#999') : '#bbb', fillOpacity: 0.95,
      }).on('click', () => setSel(p)).addTo(layer.current);
    }
    setCount(rows.length);
  }

  useEffect(() => {
    if (!box.current || map.current) return;
    const m = L.map(box.current, { zoomControl: false, attributionControl: true }).setView(JEONJU, 15);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '© OpenStreetMap',
    }).addTo(m);
    L.control.zoom({ position: 'bottomright' }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    let t: ReturnType<typeof setTimeout>;
    m.on('moveend', () => { clearTimeout(t); t = setTimeout(load, 250); });
    getPosition(8000)
      .then((f) => {
        m.setView([f.lat, f.lng], 16);
        L.circleMarker([f.lat, f.lng], { radius: 7, color: '#fff', weight: 3, fillColor: '#2C6BCB', fillOpacity: 1 }).addTo(m);
      })
      .catch(() => void load());
    return () => { m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void load(); }, [kinds]);

  const toggle = (k: string) => setKinds((ks) => (ks.includes(k) ? ks.filter((x) => x !== k) : [...ks, k]));

  return (
    <>
      <PageHead title="수거장 지도" back={false} right={<span className="small muted">{count}곳</span>} />
      <div className="filters" role="group" aria-label="종류">
        {KINDS.map((k) => (
          <button key={k.key} aria-pressed={kinds.includes(k.key)} onClick={() => toggle(k.key)}>
            <span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 9, background: k.color, marginRight: 5 }} />{k.name}
          </button>
        ))}
      </div>
      <div className="map-wrap" ref={box} />
      {sel && (
        <div className="card pop">
          <div className="row between">
            <b>{sel.name || sel.kind_name}</b>
            <button className="back" onClick={() => setSel(null)} aria-label="닫기">✕</button>
          </div>
          <span className="chip common">{sel.kind_name}</span>
          <dl className="kv">
            <dt>주소</dt><dd>{sel.address} {sel.detail}</dd>
            {sel.hours && (<><dt>이용</dt><dd>{sel.hours}</dd></>)}
            {sel.items && (<><dt>품목</dt><dd>{sel.items}</dd></>)}
          </dl>
          {!sel.is_active && <p className="caution">현재 사용하지 않는 곳으로 표시돼 있어요</p>}
          <div className="row" style={{ gap: 8 }}>
            <a className="btn ghost grow sm" href={`https://map.kakao.com/link/to/${encodeURIComponent(sel.name || '수거장')},${sel.lat},${sel.lng}`} target="_blank" rel="noreferrer">길찾기</a>
            {sel.can_verify && <Link className="btn grow sm" to="/verify">여기서 인증</Link>}
          </div>
        </div>
      )}
      <p className="tiny muted">자료: 한국폐기물협회 「분리의정석」(2024), 전주시 생활지리정보. 실제와 다를 수 있어요.</p>
    </>
  );
}
