import { memo } from 'react';
import { renderBoss, renderGarden, renderIcon, renderRemon } from '../art';
import type { GardenMood, GardenStage } from '../art';

type Props = { className?: string; size?: number | string; label?: string };

function Svg({ html, className, size, label }: Props & { html: string }) {
  const style = size !== undefined ? { width: size, height: size } : undefined;
  return (
    <span
      className={`art ${className ?? ''}`}
      style={style}
      role="img"
      aria-label={label}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export const Remon = memo(function Remon(p: Props & { art: string; shiny?: boolean; mood?: 'normal' | 'hurt' | 'happy' }) {
  return <Svg {...p} html={renderRemon(p.art, { shiny: p.shiny, mood: p.mood })} />;
});

export const Boss = memo(function Boss(p: Props & { boss: string; hurt?: boolean }) {
  return <Svg {...p} html={renderBoss(p.boss, { hurt: p.hurt })} />;
});

export const Garden = memo(function Garden(p: Props & { stage: GardenStage; mood: GardenMood }) {
  return <Svg {...p} html={renderGarden(p.stage, p.mood)} />;
});

export const Icon = memo(function Icon(p: Props & { name: string }) {
  return <Svg {...p} size={p.size ?? 28} html={renderIcon(p.name)} />;
});
