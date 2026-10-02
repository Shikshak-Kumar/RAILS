interface Props {
  score: number;
  label?: string;
  showValue?: boolean;
  height?: string;
}

import { riskBarColor } from '@/lib/utils';

export function RiskBar({ score, label, showValue = true, height = 'h-2' }: Props) {
  const pct = Math.round(score * 100);
  return (
    <div className="w-full">
      {(label || showValue) && (
        <div className="mb-1 flex items-center justify-between">
          {label && <span className="text-xs font-medium text-neutral-400">{label}</span>}
          {showValue && <span className="text-xs font-bold text-neutral-200 tabular-nums">{pct}%</span>}
        </div>
      )}
      <div className={`w-full ${height} rounded-full bg-neutral-800 overflow-hidden`}>
        <div
          className={`${height} ${riskBarColor(score)} rounded-full transition-all duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
