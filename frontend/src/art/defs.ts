// 공유 SVG 필터. 페이지에 한 번만 넣는다 (예: document.body.insertAdjacentHTML('afterbegin', ART_DEFS_SVG)).
// rc-wob: 손그림처럼 살짝 떨리는 선 / rc-stk: 흰 스티커 테두리 + 옅은 그림자
// -m, -s 접미사는 좌표계가 작은 그림(정원 360폭, 아이콘 64폭)용 축소판이다.

export const ART_DEFS_SVG: string =
  '<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>' +
  '<filter id="rc-wob" x="-10%" y="-10%" width="120%" height="120%">' +
  '<feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="7" result="n"/>' +
  '<feDisplacementMap in="SourceGraphic" in2="n" scale="3.2" xChannelSelector="R" yChannelSelector="G"/>' +
  '</filter>' +
  '<filter id="rc-wob-s" x="-10%" y="-10%" width="120%" height="120%">' +
  '<feTurbulence type="fractalNoise" baseFrequency="0.09" numOctaves="2" seed="7" result="n"/>' +
  '<feDisplacementMap in="SourceGraphic" in2="n" scale="1.3" xChannelSelector="R" yChannelSelector="G"/>' +
  '</filter>' +
  stk('rc-stk', 5, 3, 0.16) +
  stk('rc-stk-m', 3.5, 2.2, 0.15) +
  stk('rc-stk-s', 2.2, 1.4, 0.16) +
  '</defs></svg>';

function stk(id: string, r: number, dy: number, op: number): string {
  return (
    `<filter id="${id}" x="-15%" y="-15%" width="130%" height="130%">` +
    `<feMorphology in="SourceAlpha" operator="dilate" radius="${r}" result="d"/>` +
    '<feFlood flood-color="#FFFFFF" result="w0"/><feComposite in="w0" in2="d" operator="in" result="w"/>' +
    `<feOffset in="d" dx="0" dy="${dy}" result="o"/>` +
    `<feFlood flood-color="#000000" flood-opacity="${op}" result="s0"/><feComposite in="s0" in2="o" operator="in" result="s"/>` +
    '<feMerge><feMergeNode in="s"/><feMergeNode in="w"/><feMergeNode in="SourceGraphic"/></feMerge>' +
    '</filter>'
  );
}

// 선택: 리몬/보스 그룹에 붙은 rc-bob(숨쉬기), rc-float(둥실), rc-shake(피격) 클래스용 CSS.
export const ART_CSS: string =
  '.rc-bob,.rc-float,.rc-shake{transform-box:fill-box}' +
  '.rc-bob{animation:rc-bob 2.6s ease-in-out infinite;transform-origin:50% 100%}' +
  '.rc-float{animation:rc-float 3.2s ease-in-out infinite}' +
  '.rc-shake{animation:rc-shake .35s linear 2;transform-origin:50% 100%}' +
  '@keyframes rc-bob{0%,100%{transform:translateY(0) scale(1,1)}50%{transform:translateY(-3px) scale(1.01,.99)}}' +
  '@keyframes rc-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}' +
  '@keyframes rc-shake{0%,100%{transform:translateX(0)}25%{transform:translateX(-4px)}75%{transform:translateX(4px)}}' +
  '@media (prefers-reduced-motion:reduce){.rc-bob,.rc-float,.rc-shake{animation:none}}';
