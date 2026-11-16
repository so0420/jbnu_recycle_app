import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Garden } from '../components/Art';
import { Modal, PageHead } from '../components/common';
import { get, send } from '../lib/api';
import { dumpDaysText } from '../lib/labels';
import { errMsg, useStore } from '../lib/store';

interface RegionRow { code: string; name: string; gu: string }

export default function MePage() {
  const { me, refresh, toast } = useStore();
  const nav = useNavigate();
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [region, setRegion] = useState('');
  const [pw, setPw] = useState({ current: '', new: '' });
  const [del, setDel] = useState(false);
  const [delPw, setDelPw] = useState('');

  useEffect(() => { get<RegionRow[]>('/regions/list').then(setRegions); }, []);
  useEffect(() => { setRegion(me?.region?.code ?? ''); }, [me]);
  if (!me) return null;

  async function run(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn();
      toast(ok);
      await refresh();
    } catch (e) {
      toast(errMsg(e), 'err');
    }
  }

  const levels = me.unlock_levels;
  const UNLOCK_NAMES: Record<string, string> = { expedition: '탐사', missions: '미션', raid: '레이드', exchange: '재료 교환', bag10: '가방 10칸', expedition2: '탐사 2칸', bag15: '가방 15칸' };

  return (
    <>
      <PageHead title="내 정보" />
      <div className="card pop">
        <Garden stage={me.garden_stage} mood="bright" />
        <div className="row between">
          <h2>{me.nickname}</h2>
          <span className="chip ok">정원 Lv{me.level}</span>
        </div>
        <div className="bar"><span style={{ width: `${(me.xp_in_level / me.xp_need) * 100}%` }} /></div>
        <p className="tiny muted">다음 레벨까지 {me.xp_need - me.xp_in_level} XP</p>
        <div className="row wrap" style={{ gap: 6 }}>
          {Object.entries(levels).map(([k, lv]) => (
            <span key={k} className={`chip ${me.level >= lv ? 'ok' : 'common'}`}>{UNLOCK_NAMES[k] ?? k} Lv{lv}</span>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>내 동네</h3>
        {me.region && <p className="small muted">{me.region.gu} {me.region.name} · {dumpDaysText(me.region.dump_weekdays)} · {me.region.confirmed ? '확정됨' : '첫 인증 때 확정'}</p>}
        <div className="field">
          <label htmlFor="me-region">동네 바꾸기 (확정 뒤에는 30일에 한 번, 남은 도전권은 사라져요)</label>
          <select id="me-region" value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="">선택</option>
            {regions.map((r) => <option key={r.code} value={r.code}>{r.gu} {r.name}</option>)}
          </select>
        </div>
        <button className="btn ghost" disabled={!region || region === me.region?.code} onClick={() => run(() => send('/me/region', 'PATCH', { region_code: region }), '동네를 바꿨어요')}>저장</button>
      </div>

      <div className="card">
        <h3>바로가기</h3>
        <div className="grid2">
          <Link className="btn ghost sm" to="/regions">동네 청결도</Link>
          <Link className="btn ghost sm" to="/missions">미션</Link>
          <Link className="btn ghost sm" to="/dex">도감</Link>
          <Link className="btn ghost sm" to="/bag">분리 가방</Link>
          {me.role === 'admin' && <Link className="btn warn sm" to="/admin">관리자</Link>}
        </div>
      </div>

      <div className="card">
        <h3>비밀번호 바꾸기</h3>
        <div className="field"><label htmlFor="pw-cur">지금 비밀번호</label><input id="pw-cur" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></div>
        <div className="field"><label htmlFor="pw-new">새 비밀번호 (영문+숫자 8자 이상)</label><input id="pw-new" type="password" autoComplete="new-password" value={pw.new} onChange={(e) => setPw({ ...pw, new: e.target.value })} /></div>
        <button className="btn ghost" disabled={!pw.current || pw.new.length < 8} onClick={() => run(() => send('/me/password', 'POST', pw), '비밀번호를 바꿨어요').then(() => setPw({ current: '', new: '' }))}>바꾸기</button>
      </div>

      <div className="card">
        <div className="col">
          <button className="btn ghost" onClick={async () => { await send('/auth/logout', 'POST'); await refresh(); nav('/login'); }}>로그아웃</button>
          <button className="btn danger" onClick={() => setDel(true)}>회원 탈퇴</button>
        </div>
        <p className="tiny muted center"><Link to="/terms">이용약관</Link> · <Link to="/privacy">개인정보 처리방침</Link></p>
      </div>

      {del && (
        <Modal onClose={() => setDel(false)}>
          <h2>정말 탈퇴할까요?</h2>
          <p className="small">찍은 사진은 바로 지워지고, 위치 기록과 아이디·닉네임은 알아볼 수 없게 바뀌어요. 리몬과 재료는 되살릴 수 없어요.</p>
          <div className="field"><label htmlFor="del-pw">비밀번호 확인</label><input id="del-pw" type="password" value={delPw} onChange={(e) => setDelPw(e.target.value)} /></div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn ghost grow" onClick={() => setDel(false)}>취소</button>
            <button className="btn danger grow" disabled={!delPw} onClick={async () => {
              try {
                await send('/me/delete', 'POST', { password: delPw });
                await send('/auth/logout', 'POST');
                await refresh();
                nav('/login');
              } catch (e) { toast(errMsg(e), 'err'); }
            }}>탈퇴하기</button>
          </div>
        </Modal>
      )}
    </>
  );
}
