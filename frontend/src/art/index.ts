// 리사이클 앱 그림 (A 스티커 그림체). 외부 의존성 없음, 모두 SVG 문자열을 돌려준다.
// 사용: 앱 시작 시 ART_DEFS_SVG 를 body 에 한 번 넣고, 각 render* 결과를 innerHTML 로 그린다.

export { ART_DEFS_SVG, ART_CSS } from './defs';
export { TYPE_COLORS, REMON_TYPES, LINE } from './core';
export type { RemonType, Mood } from './core';
export { renderRemon, REMON_ART_KEYS, REMON_LINE_TYPE } from './remon';
export type { RemonOpts } from './remon';
export { renderBoss, BOSS_KEYS } from './boss';
export type { BossOpts } from './boss';
export { renderGarden } from './garden';
export type { GardenStage, GardenMood } from './garden';
export { renderIcon, ICON_KEYS } from './icons';
