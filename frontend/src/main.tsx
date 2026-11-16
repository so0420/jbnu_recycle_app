import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ART_CSS, ART_DEFS_SVG } from './art';
import App from './App';
import { StoreProvider } from './lib/store';
import 'leaflet/dist/leaflet.css';
import './styles.css';

// 그림 공용 필터·애니메이션을 한 번만 넣는다
const defs = document.createElement('div');
defs.innerHTML = ART_DEFS_SVG;
document.body.prepend(defs);
const style = document.createElement('style');
style.textContent = ART_CSS;
document.head.appendChild(style);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <StoreProvider>
        <App />
      </StoreProvider>
    </BrowserRouter>
  </StrictMode>,
);
