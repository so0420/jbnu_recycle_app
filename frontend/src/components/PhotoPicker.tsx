import { useRef } from 'react';
import { Icon } from './Art';

// 카메라 촬영 (웹: capture 속성, 앱: WebView 파일 선택기 → 카메라)
export default function PhotoPicker({ onPick, title, hint, icon = 'bag' }: { onPick: (f: File) => void; title: string; hint: string; icon?: string }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <button type="button" className="camera-cta" onClick={() => ref.current?.click()}>
        <Icon name={icon} size={96} />
        <h2>{title}</h2>
        <p className="small muted">{hint}</p>
      </button>
      <input
        ref={ref}
        className="hidden-input"
        type="file"
        accept="image/*"
        capture="environment"
        aria-label={title}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onPick(f);
          e.target.value = '';
        }}
      />
    </>
  );
}
