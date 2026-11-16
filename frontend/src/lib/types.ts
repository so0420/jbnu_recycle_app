export type MatKey = 'plastic' | 'paper' | 'metal' | 'glass' | 'vinyl' | 'volt' | 'fabric';

export interface Me {
  id: number;
  login_id: string;
  nickname: string;
  role: string;
  level: number;
  xp: number;
  xp_in_level: number;
  xp_need: number;
  garden_stage: 1 | 2 | 3 | 4;
  coins: number;
  tickets: number;
  ticket_cap: number;
  crystals: number;
  materials: Record<MatKey, number>;
  bag: { count: number; capacity: number };
  starter_done: boolean;
  region: null | {
    code: string;
    name: string;
    gu: string;
    sido: string;
    confirmed: boolean;
    unit: string | null;
    unit_name: string | null;
    cleanliness: number | null;
    stage: { key: string; name: string } | null;
    dump_weekdays: string;
  };
  today: {
    verify_count: number;
    verify_reward_left: number;
    scan_xp_left: number;
    free_raid: boolean;
    dumpday_ticket_taken: boolean;
    dump_time_now: boolean;
    next_dump_at: string | null;
  };
  unlocks: Record<string, boolean>;
  unlock_levels: Record<string, number>;
  economy_multiplier: number;
}

export interface Monster {
  id: number;
  species: string;
  name: string;
  type: string;
  rarity: string;
  role: string;
  stage: number;
  level: number;
  level_cap: number;
  stars: number;
  is_shiny: boolean;
  slot: number | null;
  skill_timing: string;
  art: string;
  stats: { hp: number; atk: number; def: number; spd: number };
  power: number;
  skill: { name: string; desc: string };
  desc: string;
  on_expedition: boolean;
  expedition_until: string | null;
  levelup_cost: { material: MatKey; materials: number; coins: number } | null;
  evolve?: { to_stage: number; level: number; materials: number; habits: number; crystals: number; habit_now: number };
}

export interface Place {
  id: number;
  kind: string;
  kind_name: string;
  name: string;
  address: string;
  detail: string;
  lat: number;
  lng: number;
  hours: string;
  items: string;
  region_code: string | null;
  is_active: boolean;
  distance_m: number | null;
  can_verify: boolean;
  in_range?: boolean;
}

export interface Guide {
  category: string;
  category_name: string;
  type: string;
  recyclable: boolean;
  item: null | { label: string; name: string; method: string; caution: string };
  habit_name: string | null;
}

export interface BattleEvent {
  r?: number;
  a?: string;
  act: string;
  t?: string;
  dmg?: number;
  heal?: number;
  crit?: boolean;
  kill?: boolean;
  skill?: string;
  shield_hit?: number;
  absorbed?: number;
  amount?: number;
}

export interface BattleUnit {
  id: string;
  name: string;
  side: 'ally' | 'enemy';
  type: string;
  hp: number;
  max_hp: number;
  front: boolean;
  art: string;
}
