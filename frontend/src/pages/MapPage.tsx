import L from 'leaflet';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHead } from '../components/common';
import { get } from '../lib/api';
import { getPosition, getQuickPosition, lastFix } from '../lib/device';
import { errMsg, useStore } from '../lib/store';
import type { Place } from '../lib/types';

const JEONJU: [number, number] = [35.8242, 127.148];
const KINDS: { key: string; name: string; color: string }[] = [
  { key: 'recycle_point', name: '분리배출장소', color: '#1E7A4C' },
  { key: 'clothes_bin', name: '의류수거함', color: '#C2577A' },
  { key: 'battery_bin', name: '폐건전지·소형가전', color: '#D9A400' },
  { key: 'reverse_vending', name: '무인회수기', color: '#2C6BCB' },
  { key: 'bag_shop', name: '종량제봉투 판매소', color: '#7B8391' },
];

// 확대 단계별 표시: 14 이상 개별 수거장, 13 행정동, 11~12 시·군·구, 10 이하 시·도 묶음
const DETAIL_ZOOM = 14;
function levelOf(z: number): 'sido' | 'sigungu' | 'dong' | null {
  if (z >= DETAIL_ZOOM) return null;
  if (z >= 13) return 'dong';
  if (z >= 11) return 'sigungu';
  return 'sido';
}
const NEXT_ZOOM = { sido: 11, sigungu: 13, dong: DETAIL_ZOOM } as const;

interface Cluster { key: string; name: string; n: number; lat: number; lng: number }
type MapRow = [number, string, number, number, number];

export default function MapPage() {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const canvas = useRef<L.Canvas | null>(null);
  const meDot = useRef<L.CircleMarker | null>(null);
  const [locating, setLocating] = useState(false);
  const [kinds, setKinds] = useState<string[]>(['recycle_point', 'clothes_bin', 'battery_bin', 'reverse_vending']);
  const [sel, setSel] = useState<Place | null>(null);
  const [count, setCount] = useState(0);
  const [loadErr, setLoadErr] = useState('');
  const { me } = useStore();
  const home = me?.region?.center;
  const kindsRef = useRef(kinds);
  kindsRef.current = kinds;
  const seq = useRef(0);

  function showMe(lat: number, lng: number) {
    const m = map.current;
    if (!m) return;
    if (meDot.current) meDot.current.setLatLng([lat, lng]);
    else meDot.current = L.circleMarker([lat, lng], { radius: 7, color: '#fff', weight: 3, fillColor: '#2C6BCB', fillOpacity: 1 }).addTo(m);
  }

  async function goToMe() {
    if (locating) return;
    setLocating(true);
    try {
      const f = await getPosition(10000);
      showMe(f.lat, f.lng);
      map.current?.setView([f.lat, f.lng], Math.max(16, map.current.getZoom()));
      setLoadErr('');
    } catch (e) {
      setLoadErr(errMsg(e));
    } finally {
      setLocating(false);
    }
  }

  async function pick(id: number) {
    try {
      setSel(await get<Place>(`/places/${id}`));
    } catch {
      setLoadErr('수거장 정보를 불러오지 못했어요');
    }
  }

  async function load() {
    const m = map.current;
    if (!m || !layer.current) return;
    const my = ++seq.current;            // 늦게 온 옛 응답이 새 결과를 덮지 않게
    if (kindsRef.current.length === 0) {
      layer.current.clearLayers();
      setCount(0);
      return;
    }
    const b = m.getBounds();
    const box4 = `south=${b.getSouth()}&west=${b.getWest()}&north=${b.getNorth()}&east=${b.getEast()}`;
    const asked = kindsRef.current.join(',');
    const level = levelOf(m.getZoom());
    try {
      if (level) {
        const rows = await get<Cluster[]>(`/places/clusters?level=${level}&${box4}&kind=${asked}`);
        if (my !== seq.current || asked !== kindsRef.current.join(',') || !layer.current) return;
        drawClusters(m, rows, level);
      } else {
        const r = await get<{ truncated: boolean; rows: MapRow[] }>(`/places/map?${box4}&kind=${asked}`);
        if (my !== seq.current || asked !== kindsRef.current.join(',') || !layer.current) return;
        drawPlaces(m, r.rows);
      }
      setLoadErr('');
    } catch {
      if (my === seq.current) setLoadErr('수거장 정보를 불러오지 못했어요. 지도를 조금 움직이면 다시 시도해요.');
    }
  }

  function drawPlaces(m: L.Map, rows: MapRow[]) {
    const lg = layer.current!;
    lg.clearLayers();
    const z = m.getZoom();
    const r = z >= 16 ? 8 : z >= 15 ? 7 : 5;
    for (const [id, kind, lat, lng, active] of rows) {
      const k = KINDS.find((x) => x.key === kind);
      L.circleMarker([lat, lng], {
        renderer: canvas.current ?? undefined,          // 수천 곳도 빠르게 그리도록 캔버스 사용
        radius: kind === 'bag_shop' ? Math.max(4, r - 3) : r, color: '#2A2622', weight: z >= 15 ? 2 : 1.5,
        fillColor: active ? (k?.color ?? '#999') : '#bbb', fillOpacity: 0.95,
      }).on('click', () => void pick(id)).addTo(lg);
    }
    setCount(rows.length);
  }

  function drawClusters(m: L.Map, rows: Cluster[], level: 'sido' | 'sigungu' | 'dong') {
    const lg = layer.current!;
    lg.clearLayers();
    const b = m.getBounds();
    // 화면 안의 수는 모두 더하고, 말풍선은 겹치지 않게 큰 곳부터 놓는다
    setCount(rows.filter((c) => b.contains([c.lat, c.lng])).reduce((a, c) => a + c.n, 0));
    const placed: { x: number; y: number; w: number }[] = [];
    const size = m.getSize();
    for (const c of [...rows].sort((a, b2) => b2.n - a.n)) {
      const pt = m.latLngToContainerPoint([c.lat, c.lng]);
      if (pt.x < 0 || pt.y < 0 || pt.x > size.x || pt.y > size.y) continue;   // 화면 밖 묶음은 그리지 않는다
      const label = `${c.name} ${c.n.toLocaleString('ko-KR')}곳`;
      const w = label.length * 9 + 22;
      if (placed.some((p) => Math.abs(p.x - pt.x) < (p.w + w) / 2 && Math.abs(p.y - pt.y) < 30)) continue;
      placed.push({ x: pt.x, y: pt.y, w });
      const icon = L.divIcon({
        className: 'cl-icon', iconSize: undefined,
        html: `<div class="cl-bubble"><b>${c.name}</b> ${c.n.toLocaleString('ko-KR')}곳</div>`,
      });
      L.marker([c.lat, c.lng], { icon, keyboard: false, title: label })
        .on('click', () => m.setView([c.lat, c.lng], Math.max(m.getZoom() + 1, NEXT_ZOOM[level])))
        .addTo(lg);
    }
  }

  useEffect(() => {
    if (!box.current || map.current) return;
    const start = lastFix();
    // 위치를 못 받으면 내 동네 중심, 그것도 없으면 시범 지역(전주)
    const m = L.map(box.current, { zoomControl: false, attributionControl: true })
      .setView(start ? [start.lat, start.lng] : home && home[0] ? home : JEONJU, start ? 16 : 15);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '© OpenStreetMap',
    }).addTo(m);
    L.control.zoom({ position: 'bottomright' }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    canvas.current = L.canvas({ padding: 0.3 });
    map.current = m;
    let t: ReturnType<typeof setTimeout>;
    m.on('moveend', () => { clearTimeout(t); t = setTimeout(load, 250); });
    // 사용자가 지도를 만지기 시작하면, 늦게 도착한 위치로 지도를 옮기지 않는다 (파란 점만 갱신)
    let touched = false;
    const touch = () => { touched = true; };
    const el = m.getContainer();
    el.addEventListener('pointerdown', touch);
    el.addEventListener('wheel', touch, { passive: true });
    el.addEventListener('touchstart', touch, { passive: true });
    let centered = !!start;
    if (start) showMe(start.lat, start.lng);
    const arrive = (f: { lat: number; lng: number }) => {
      if (!map.current) return;
      showMe(f.lat, f.lng);
      if (!touched) {
        m.setView([f.lat, f.lng], centered ? m.getZoom() : 16);
        centered = true;
      }
    };
    getQuickPosition().then(arrive).catch(() => {});     // 대략 위치로 먼저 빠르게
    getPosition(10000).then(arrive).catch(() => { if (!centered) void load(); });   // 그다음 정확한 위치
    return () => { m.remove(); map.current = null; meDot.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void load(); }, [kinds]);
  useEffect(() => {
    if (sel) document.getElementById('place-card')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [sel]);

  const toggle = (k: string) => setKinds((ks) => (ks.includes(k) ? ks.filter((x) => x !== k) : [...ks, k]));

  return (
    <>
      <PageHead title="수거장 지도" back={false} right={<span className="small muted">{count.toLocaleString('ko-KR')}곳</span>} />
      <div className="filters" role="group" aria-label="종류">
        {KINDS.map((k) => (
          <button key={k.key} aria-pressed={kinds.includes(k.key)} onClick={() => toggle(k.key)}>
            <span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: 9, background: k.color, marginRight: 5 }} />{k.name}
          </button>
        ))}
      </div>
      <div className="map-box">
        <div className="map-wrap" ref={box} />
        <button className="map-locate" onClick={() => void goToMe()} disabled={locating} aria-label="현재 위치로 이동" title="현재 위치로 이동">
          {locating ? <span className="spinner sm" /> : (
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <circle cx="12" cy="12" r="4" fill="#2C6BCB" />
              <circle cx="12" cy="12" r="7.5" fill="none" stroke="#2A2622" strokeWidth="2" />
              <path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4" stroke="#2A2622" strokeWidth="2" strokeLinecap="round" />
            </svg>
          )}
        </button>
      </div>
      {loadErr && <p className="err small">{loadErr}</p>}
      <p className="tiny muted">축소하면 지역별로 묶어서 보여요. 묶음을 누르면 그 지역으로 확대돼요.</p>
      {sel && (
        <div className="card pop" id="place-card">
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
            {sel.can_verify && <Link className="btn grow sm" to="/verify">도착하면 인증하기</Link>}
          </div>
        </div>
      )}
      <p className="tiny muted">자료: 한국폐기물협회 「분리의정석」(2024), 전주시 생활지리정보. 실제와 다를 수 있어요.</p>
    </>
  );
}
