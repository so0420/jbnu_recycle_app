import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ART_CSS, ART_DEFS_SVG } from './art';
import App from './App';
import { App as CapApp } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';
import { StoreProvider } from './lib/store';
import { closeTopModal } from './components/common';
// 글꼴은 서버에서 직접 제공 (외부 글꼴 서비스로 접속 정보가 나가지 않게)
import '@fontsource/jua/400.css';
import '@fontsource/ibm-plex-sans-kr/400.css';
import '@fontsource/ibm-plex-sans-kr/600.css';
import '@fontsource/ibm-plex-sans-kr/700.css';
import 'leaflet/dist/leaflet.css';
import './styles.css';

// 그림 공용 필터·애니메이션을 한 번만 넣는다
const defs = document.createElement('div');
defs.innerHTML = ART_DEFS_SVG;
document.body.prepend(defs);
const style = document.createElement('style');
style.textContent = ART_CSS;
document.head.appendChild(style);

if (Capacitor.isNativePlatform()) {
  void CapApp.addListener('backButton', ({ canGoBack }) => {
    if (closeTopModal()) return;
    if (canGoBack && window.location.pathname !== '/') window.history.back();
    else void CapApp.minimizeApp();
  });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <StoreProvider>
        <App />
      </StoreProvider>
    </BrowserRouter>
  </StrictMode>,
);
