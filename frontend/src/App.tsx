import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Layout from './components/Layout';
import { useStore } from './lib/store';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Starter from './pages/Starter';
import Home from './pages/Home';
import Scan from './pages/Scan';
import Verify from './pages/Verify';
import Monsters from './pages/Monsters';
import MonsterDetail from './pages/MonsterDetail';
import Party from './pages/Party';
import Capsules from './pages/Capsules';
import Bag from './pages/Bag';
import Dex from './pages/Dex';
import Raid from './pages/Raid';
import Regions from './pages/Regions';
import Missions from './pages/Missions';
import MePage from './pages/MePage';
import Admin from './pages/Admin';
import { Privacy, Terms } from './pages/Legal';

const MapPage = lazy(() => import('./pages/MapPage'));

function Guard({ children }: { children: JSX.Element }) {
  const { me, loading } = useStore();
  const loc = useLocation();
  if (loading) return <div className="splash">불러오는 중…</div>;
  if (!me) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (!me.starter_done && loc.pathname !== '/starter') return <Navigate to="/starter" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/starter" element={<Guard><Starter /></Guard>} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route path="/" element={<Home />} />
        <Route path="/scan" element={<Scan />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="/map" element={<Suspense fallback={<div className="splash">지도 불러오는 중…</div>}><MapPage /></Suspense>} />
        <Route path="/monsters" element={<Monsters />} />
        <Route path="/monsters/:id" element={<MonsterDetail />} />
        <Route path="/party" element={<Party />} />
        <Route path="/capsules" element={<Capsules />} />
        <Route path="/bag" element={<Bag />} />
        <Route path="/dex" element={<Dex />} />
        <Route path="/raid" element={<Raid />} />
        <Route path="/regions" element={<Regions />} />
        <Route path="/missions" element={<Missions />} />
        <Route path="/me" element={<MePage />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
