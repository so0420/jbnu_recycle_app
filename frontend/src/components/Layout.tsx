import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useStore } from '../lib/store';
import { fmt } from '../lib/labels';
import { Icon } from './Art';

export default function Layout() {
  const { me } = useStore();
  const nav = useNavigate();
  return (
    <div className="shell">
      <header className="topbar">
        <button className="lv" onClick={() => nav('/me')} aria-label="내 정보">
          <span className="lv-num">Lv{me?.level}</span>
          <span className="lv-bar">
            <span style={{ width: `${me ? (me.xp_in_level / me.xp_need) * 100 : 0}%` }} />
          </span>
        </button>
        <div className="res">
          <span title="에코 코인"><Icon name="coin" size={20} />{fmt(me?.coins ?? 0)}</span>
          <span title="도전권"><Icon name="ticket" size={20} />{me?.tickets ?? 0}</span>
          <span title="정화의 결정"><Icon name="crystal" size={20} />{me?.crystals ?? 0}</span>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
      <nav className="tabbar" aria-label="주요 메뉴">
        <NavLink to="/" end><Icon name="type_paper" size={24} /><span>홈</span></NavLink>
        <NavLink to="/map"><Icon name="map_pin" size={24} /><span>지도</span></NavLink>
        <NavLink to="/scan" className="tab-scan"><span className="scan-btn"><Icon name="bag" size={30} /></span><span>스캔</span></NavLink>
        <NavLink to="/monsters"><Icon name="capsule_plastic" size={24} /><span>리몬</span></NavLink>
        <NavLink to="/raid"><Icon name="raid" size={24} /><span>레이드</span></NavLink>
      </nav>
    </div>
  );
}
