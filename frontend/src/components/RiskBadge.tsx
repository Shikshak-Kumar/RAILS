import type { RiskLevel } from '@/types';
import { riskColor } from '@/lib/utils';

interface Props {
  level: RiskLevel;
  size?: 'sm' | 'md' | 'lg';
  showDot?: boolean;
}

export function RiskBadge({ level, size = 'sm', showDot = false }: Props) {
  const c = riskColor(level);
  const sizeClass =
    size === 'lg' ? 'px-4 py-1.5 text-sm' : size === 'md' ? 'px-3 py-1 text-xs' : 'px-2 py-0.5 text-[10px]';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md font-bold uppercase tracking-wider ${c.bg} text-white ${sizeClass}`}
    >
      {showDot && <span className={`h-1.5 w-1.5 rounded-full bg-white/80 ${level === 'CRITICAL' ? 'animate-pulse' : ''}`} />}
      {c.label}
    </span>
  );
}
