import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { send } from '../lib/api';
import { Modal } from '../components/common';
import { LocationTerms, Privacy, Terms } from './Legal';
import RegionPicker from '../components/RegionPicker';
import { errMsg, useStore } from '../lib/store';

export default function Signup() {
  const { refresh } = useStore();
  const nav = useNavigate();
  const [f, setF] = useState({ login_id: '', password: '', password2: '', nickname: '', region_code: '' });
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);
  const [agreeAge, setAgreeAge] = useState(false);
  const [agreeLoc, setAgreeLoc] = useState(false);
  const [agreeOverseas, setAgreeOverseas] = useState(false);
  const [doc, setDoc] = useState<null | 'terms' | 'privacy' | 'location'>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr('');
    if (f.password !== f.password2) return setErr('비밀번호가 서로 달라요');
    const nick = f.nickname.trim();
    if (nick.length < 2 || nick.length > 12) return setErr('닉네임은 2~12자로 만들어 주세요');
    if (!agreeTerms || !agreePrivacy || !agreeAge || !agreeLoc || !agreeOverseas) return setErr('필수 항목에 모두 동의해 주세요');
    setBusy(true);
    try {
      await send('/auth/signup', 'POST', {
        login_id: f.login_id, password: f.password, nickname: nick, region_code: f.region_code || null,
        agree_terms: agreeTerms, agree_privacy: agreePrivacy, agree_age: agreeAge, agree_location: agreeLoc,
        agree_overseas: agreeOverseas,
      });
      await refresh();
      nav('/starter', { replace: true });
    } catch (e2) {
      setErr(errMsg(e2));
    } finally {
      setBusy(false);
    }
  }

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
          <label htmlFor="su-sido">내 동네 (첫 배출 인증 때 확정돼요 · 확정 뒤 한 번은 바로 바꿀 수 있어요)</label>
          <RegionPicker idPrefix="su" value={f.region_code} onChange={(code) => setF({ ...f, region_code: code })} />
        </div>
        <div className="col" style={{ gap: 6 }}>
          <label className="check"><input type="checkbox" checked={agreeAge} onChange={(e) => setAgreeAge(e.target.checked)} /> <span>(필수) 만 14세 이상입니다</span></label>
          <label className="check"><input type="checkbox" checked={agreeTerms} onChange={(e) => setAgreeTerms(e.target.checked)} /> <span>(필수) 이용약관에 동의합니다 <button type="button" className="link-btn" onClick={() => setDoc('terms')}>보기</button></span></label>
          <label className="check"><input type="checkbox" checked={agreePrivacy} onChange={(e) => setAgreePrivacy(e.target.checked)} /> <span>(필수) 개인정보 수집·이용에 동의합니다 <button type="button" className="link-btn" onClick={() => setDoc('privacy')}>보기</button></span></label>
          <label className="check"><input type="checkbox" checked={agreeOverseas} onChange={(e) => setAgreeOverseas(e.target.checked)} /> <span>(필수) 개인정보 국외 이전(사진 판정 OpenAI·지도 OpenStreetMap·Cloudflare)에 동의합니다 <button type="button" className="link-btn" onClick={() => setDoc('privacy')}>보기</button></span></label>
          <label className="check"><input type="checkbox" checked={agreeLoc} onChange={(e) => setAgreeLoc(e.target.checked)} /> <span>(필수) 위치기반서비스 이용약관에 동의합니다 <button type="button" className="link-btn" onClick={() => setDoc('location')}>보기</button></span></label>
        </div>
        {err && <p className="err">{err}</p>}
        <button className="btn block" disabled={busy}>{busy ? '가입 중…' : '가입하기'}</button>
      </form>
      <Link className="center small" to="/login">이미 계정이 있어요</Link>
      {doc && (
        <Modal onClose={() => setDoc(null)}>
          {doc === 'terms' && <Terms embedded />}
          {doc === 'privacy' && <Privacy embedded />}
          {doc === 'location' && <LocationTerms embedded />}
          <button className="btn block" onClick={() => setDoc(null)}>닫기</button>
        </Modal>
      )}
    </div>
  );
}
