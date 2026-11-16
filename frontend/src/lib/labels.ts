export const TYPE_NAMES: Record<string, string> = {
  plastic: '플라스틱',
  paper: '종이',
  metal: '금속',
  glass: '유리',
  vinyl: '비닐',
  volt: '전지',
  fabric: '섬유',
  spirit: '정령',
  none: '일반쓰레기',
};

export const MAT_NAMES: Record<string, string> = {
  plastic: '플라스틱 칩',
  paper: '펄프',
  metal: '알루미늄',
  glass: '유리 조각',
  vinyl: '비닐 필름',
  volt: '볼트 코어',
  fabric: '섬유 실',
};

export const RARITY_NAMES: Record<string, string> = { common: '일반', rare: '희귀', epic: '에픽', legend: '전설' };

export const ROLE_NAMES: Record<string, string> = {
  tank: '탱커',
  dealer: '딜러',
  healer: '힐러',
  support: '서포터',
  disrupt: '방해',
  volt: '연쇄 딜러',
  fabric: '만능',
  spirit: '정령',
};

export const TIMING_NAMES: Record<string, string> = {
  now: '바로 사용',
  boss50: '보스 체력 50% 이하',
  ally30: '아군 체력 30% 이하',
};

export const STAGE_COLORS: Record<string, string> = {
  sparkle: '#1B7F4A',
  clean: '#3FA166',
  normal: '#D9A400',
  dirty: '#E07A2F',
  crisis: '#C8382B',
};

export const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

export function dumpDaysText(s: string | undefined | null): string {
  if (!s) return '배출 요일 정보 없음 (시·군·구청 안내 확인)';
  return s
    .split(',')
    .map((d) => WEEKDAYS[Number(d)])
    .join('·') + ' 수거';
}

export function fmt(n: number): string {
  return n.toLocaleString('ko-KR');
}
