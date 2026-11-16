import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { get, send } from '../lib/api';
import { errMsg, useStore } from '../lib/store';

interface RegionRow { code: string; name: string; gu: string; zone: string | null }

export default function Signup() {
  const { refresh } = useStore();
  const nav = useNavigate();
  const [regions, setRegions] = useState<RegionRow[]>([]);
  const [f, setF] = useState({ login_id: '', password: '', password2: '', nickname: '', region_code: '' });
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);
  const [agreeAge, setAgreeAge] = useState(false);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get<RegionRow[]>('/regions/list').then(setRegions).catch(() => setRegions([]));
  }, []);

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr('');
    if (f.password !== f.password2) return setErr('비밀번호가 서로 달라요');
    if (!agreeTerms || !agreePrivacy || !agreeAge) return setErr('필수 항목에 모두 동의해 주세요');
    setBusy(true);
    try {
      await send('/auth/signup', 'POST', {
        login_id: f.login_id, password: f.password, nickname: f.nickname, region_code: f.region_code || null,
        agree_terms: agreeTerms, agree_privacy: agreePrivacy,
      });
      await refresh();
      nav('/starter', { replace: true });
    } catch (e2) {
      setErr(errMsg(e2));
    } finally {
      setBusy(false);
    }
  }

  const byGu = regions.reduce<Record<string, RegionRow[]>>((a, r) => ((a[r.gu] ||= []).push(r), a), {});

  return (
    <div className="auth-wrap">
      <h1>회원가입</h1>
      <form className="card pop" onSubmit={submit}>
        <div className="field">
          <label htmlFor="su-id">아이디</label>
          <input id="su-id" value={f.login_id} onChange={set('login_id')} autoComplete="username" placeholder="영문 소문자·숫자 4~20자" required minLength={4} maxLength={20} />
        </div>
        <div className="field">
          <label htmlFor="su-pw">비밀번호</label>
          <input id="su-pw" type="password" value={f.password} onChange={set('password')} autoComplete="new-password" placeholder="영문+숫자 8자 이상" required minLength={8} />
        </div>
        <div className="field">
          <label htmlFor="su-pw2">비밀번호 확인</label>
          <input id="su-pw2" type="password" value={f.password2} onChange={set('password2')} autoComplete="new-password" required />
        </div>
        <div className="field">
          <label htmlFor="su-nick">닉네임 (다른 사람에게 보여요)</label>
          <input id="su-nick" value={f.nickname} onChange={set('nickname')} placeholder="2~12자" required minLength={2} maxLength={12} />
        </div>
        <div className="field">
          <label htmlFor="su-region">내 동네 (첫 배출 인증 위치로 확정돼요)</label>
          <select id="su-region" value={f.region_code} onChange={set('region_code')}>
            <option value="">나중에 정할게요</option>
            {Object.entries(byGu).map(([gu, rs]) => (
              <optgroup key={gu} label={gu}>
                {rs.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
              </optgroup>
            ))}
          </select>
        </div>
        <div className="col" style={{ gap: 6 }}>
          <label className="check"><input type="checkbox" checked={agreeAge} onChange={(e) => setAgreeAge(e.target.checked)} /> <span>(필수) 만 14세 이상입니다</span></label>
          <label className="check"><input type="checkbox" checked={agreeTerms} onChange={(e) => setAgreeTerms(e.target.checked)} /> <span>(필수) <Link to="/terms" target="_blank">이용약관</Link>에 동의합니다</span></label>
          <label className="check"><input type="checkbox" checked={agreePrivacy} onChange={(e) => setAgreePrivacy(e.target.checked)} /> <span>(필수) <Link to="/privacy" target="_blank">개인정보 수집·이용</Link>에 동의합니다 (사진·위치, 애매한 사진의 국외 판정 포함)</span></label>
        </div>
        {err && <p className="err">{err}</p>}
        <button className="btn block" disabled={busy}>{busy ? '가입 중…' : '가입하기'}</button>
      </form>
      <Link className="center small" to="/login">이미 계정이 있어요</Link>
    </div>
  );
}
