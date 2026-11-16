import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Remon } from '../components/Art';
import { send } from '../lib/api';
import { errMsg, useStore } from '../lib/store';

export default function Login() {
  const { me, refresh } = useStore();
  const nav = useNavigate();
  const [id, setId] = useState('');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  if (me) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      await send('/auth/login', 'POST', { login_id: id, password: pw });
      await refresh();
      nav('/', { replace: true });
    } catch (e2) {
      setErr(errMsg(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-hero" aria-hidden="true">
        <Remon art="petring_1" />
        <Remon art="boxbear_1" />
        <Remon art="candol_1" />
      </div>
      <div className="center col" style={{ gap: 4 }}>
        <h1>리사이클</h1>
        <p className="muted">제대로 버린 쓰레기가 리몬이 되는 곳 · 전주</p>
      </div>
      <form className="card pop" onSubmit={submit}>
        <div className="field">
          <label htmlFor="login-id">아이디</label>
          <input id="login-id" autoComplete="username" value={id} onChange={(e) => setId(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="login-pw">비밀번호</label>
          <input id="login-pw" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required />
        </div>
        {err && <p className="err">{err}</p>}
        <button className="btn block" disabled={busy}>{busy ? '확인 중…' : '로그인'}</button>
      </form>
      <Link className="btn ghost block" to="/signup">처음이에요 · 회원가입</Link>
      <p className="center tiny muted">
        <Link to="/terms">이용약관</Link> · <Link to="/privacy">개인정보 처리방침</Link>
      </p>
    </div>
  );
}
