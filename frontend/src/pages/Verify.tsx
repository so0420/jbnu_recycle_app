import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../components/Art';
import PhotoPicker from '../components/PhotoPicker';
import { Mat, PageHead } from '../components/common';
import { get, upload } from '../lib/api';
import { getPosition, shrinkPhoto, uuid, type Fix } from '../lib/device';
import { MAT_NAMES } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';
import type { Place } from '../lib/types';

interface Nearest { limit_m: number; accuracy_ok: boolean; places: Place[] }
interface Reward {
  xp: number;
  xp_breakdown: { type: string; amount: number }[];
  level_before: number;
  level_after: number;
  materials?: Record<string, number>;
  bag_settled?: { category: string; clean: boolean }[];
  coins?: number;
  capsule?: { id: number; type: string };
  tickets?: number;
  region_restore?: number;
  region_cleanliness?: number;
  weekly?: { count: number; goal: number; completed_now?: boolean };
  stamp_new?: { place_id: number };
  evolution_ready?: { id: number; name: string }[];
  dump_time?: boolean;
  in_home_area?: boolean;
  dumpday_bonus?: boolean;
  region_suggest?: { code: string; name: string };
  note?: string;
}
interface VerifyRes { result: 'success' | 'fail'; code?: string; message?: string; detail?: Record<string, unknown>; place?: Place; reward?: Reward }

const XP_NAMES: Record<string, string> = { verify: '배출 인증', dumpday: '배출일 보너스', weekly_goal: '주간 목표 달성' };

export default function Verify() {
  const { refresh, toast } = useStore();
  const [fix, setFix] = useState<Fix | null>(null);
  const [near, setNear] = useState<Nearest | null>(null);
  const [locErr, setLocErr] = useState('');
  const [locating, setLocating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<VerifyRes | null>(null);

  const locate = useCallback(async () => {
    setLocErr('');
    setLocating(true);
    try {
      const f = await getPosition();
      setFix(f);
      setNear(await get<Nearest>(`/verify/nearest?lat=${f.lat}&lng=${f.lng}&accuracy=${Math.round(f.accuracy)}`));
    } catch (e) {
      setLocErr(errMsg(e));
    } finally {
      setLocating(false);
    }
  }, []);

  useEffect(() => { void locate(); }, [locate]);

  async function onPick(file: File) {
    setBusy(true);
    setRes(null);
    try {
      const f = await getPosition().catch(() => fix);
      if (!f) throw new Error('위치를 가져오지 못했어요');
      const blob = await shrinkPhoto(file);
      const fd = new FormData();
      fd.append('photo', blob, 'verify.jpg');
      fd.append('lat', String(f.lat));
      fd.append('lng', String(f.lng));
      fd.append('accuracy', String(Math.round(f.accuracy)));
      fd.append('idempotency_key', uuid());
      if (file.lastModified > 0) fd.append('taken_ms', String(file.lastModified));
      const r = await upload<VerifyRes>('/verify', fd);
      setRes(r);
      if (r.result === 'success') void refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
    } finally {
      setBusy(false);
    }
  }

  const target = near?.places[0];
  const inRange = !!target?.in_range && !!near?.accuracy_ok;
  const rw = res?.reward;

  return (
    <>
      <PageHead title="배출 인증" />
      {!res && (
        <div className="card">
          <div className="row between">
            <h3>가장 가까운 수거장</h3>
            <button className="btn ghost sm" onClick={locate} disabled={locating}>{locating ? '찾는 중…' : '위치 새로고침'}</button>
          </div>
          {locErr && <p className="err">{locErr}</p>}
          {!locErr && !near && <p className="muted small">위치를 확인하고 있어요…</p>}
          {near && !target && <p className="small">500m 안에 등록된 수거장이 없어요. <Link to="/map">지도</Link>에서 가까운 곳을 찾아 보세요.</p>}
          {target && (
            <div className="col" style={{ gap: 4 }}>
              <div className="row wrap" style={{ gap: 6 }}>
                <b>{target.name || target.kind_name}</b>
                <span className={`chip ${inRange ? 'ok' : 'bad'}`}>
                  {target.distance_m}m{' '}
                  {inRange ? '· 인증 가능' : !near?.accuracy_ok ? '· 위치 정확도가 낮아요' : `· ${near?.limit_m}m 안으로 가 주세요`}
                </span>
              </div>
              <span className="small muted">{target.address} {target.detail}</span>
              {fix && <span className="tiny muted">내 위치 오차 약 {Math.round(fix.accuracy)}m{near && !near.accuracy_ok ? ' · 하늘이 보이는 곳에서 위치를 새로고침해 주세요' : ''}</span>}
            </div>
          )}
        </div>
      )}

      {!res && !busy && (
        <PhotoPicker
          onPick={onPick}
          icon="stamp"
          title={inRange ? '버리는 모습을 찍어 주세요' : '수거장에 가까이 가면 인증할 수 있어요'}
          hint="수거함과 버리는 물건이 함께 나오게 찍어 주세요. 사진은 30일 뒤 지워져요."
        />
      )}
      {busy && <div className="card center"><div className="spinner" /><p className="muted small">위치와 사진을 확인하고 있어요…</p></div>}

      {res?.result === 'fail' && (
        <div className="card pop">
          <h2>인증하지 못했어요</h2>
          <p>{res.message}</p>
          {res.code === 'TOO_FAR' && typeof res.detail?.nearest_m === 'number' && (
            <p className="small muted">가장 가까운 수거장까지 {String(res.detail.nearest_m)}m</p>
          )}
          <button className="btn block" onClick={() => { setRes(null); void locate(); }}>다시 하기</button>
        </div>
      )}

      {res?.result === 'success' && rw && (
        <div className="card pop">
          <h2>인증 완료!</h2>
          <p className="small muted">{res.place?.name || res.place?.kind_name} · {res.place?.address}</p>
          {rw.note && <p className="caution">{rw.note}</p>}
          <div className="reward-list">
            {rw.xp_breakdown.map((x, i) => (
              <div className="r" key={i} style={{ animationDelay: `${i * 0.15}s` }}><Icon name="coin" size={22} />{XP_NAMES[x.type] ?? x.type} 경험치 +{x.amount}</div>
            ))}
            {rw.level_after > rw.level_before && <div className="r"><b>정원 레벨 업! Lv{rw.level_after}</b></div>}
            {rw.bag_settled && rw.bag_settled.length > 0 && <div className="r"><Icon name="bag" size={22} />가방 {rw.bag_settled.length}개 정산 (깨끗 {rw.bag_settled.filter((b) => b.clean).length}개)</div>}
            {rw.materials && (
              <div className="r wrap">{Object.entries(rw.materials).map(([k, n]) => <span key={k} className="row" title={MAT_NAMES[k]}><Mat k={k} n={n} /></span>)}</div>
            )}
            {rw.coins ? <div className="r"><Icon name="coin" size={22} />에코 코인 +{rw.coins}</div> : null}
            {rw.tickets ? <div className="r"><Icon name="ticket" size={22} />도전권 +{rw.tickets}{rw.dumpday_bonus ? ' (배출일 보너스 포함)' : ''}</div> : null}
            {rw.region_restore ? <div className="r"><Icon name="type_paper" size={22} />우리 동네 청결도 +{rw.region_restore} → {rw.region_cleanliness}</div> : null}
            {rw.stamp_new && <div className="r"><Icon name="stamp" size={22} />새 수거장 스탬프!</div>}
            {rw.weekly && <div className="r">주간 목표 {rw.weekly.count}/{rw.weekly.goal}{rw.weekly.completed_now ? ' 달성!' : ''}</div>}
            {rw.evolution_ready && rw.evolution_ready.length > 0 && <div className="r"><b>진화 가능: {rw.evolution_ready.map((e) => e.name).join(', ')}</b></div>}
            {rw.region_suggest && <div className="r small">이 수거장은 {rw.region_suggest.name}이에요. 내 동네를 바꾸려면 내 정보에서 바꿀 수 있어요.</div>}
          </div>
          {rw.capsule && <Link className="btn block" to="/capsules">캡슐 열기</Link>}
          <Link className="btn ghost block" to="/">홈으로</Link>
        </div>
      )}
    </>
  );
}
