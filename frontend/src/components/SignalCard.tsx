import type { RiskSignal } from '@/types';
import { RiskBadge } from './RiskBadge';

interface Props {
  signal: RiskSignal;
}

const typeIcon: Record<string, string> = {
  fraud: 'F',
  anomaly: 'A',
  graph: 'G',
  liquidity: 'L',
  credit: 'C',
  rule: 'R',
};

export function SignalCard({ signal }: Props) {
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-3 transition-colors hover:border-neutral-700">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-neutral-800 text-xs font-bold text-neutral-300">
          {typeIcon[signal.type] ?? 'S'}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h4 className="truncate text-sm font-semibold text-neutral-100">{signal.name}</h4>
            <RiskBadge level={signal.severity} />
          </div>
          <p className="mt-1 text-xs text-neutral-400">{signal.description}</p>
          <div className="mt-2 flex items-center gap-3 text-[10px] text-neutral-500">
            <span>Value: <span className="font-bold text-neutral-300">{signal.value}</span></span>
            <span>Threshold: <span className="font-bold text-neutral-300">{signal.threshold}</span></span>
            <span className={signal.triggered ? 'text-red-400 font-bold' : 'text-green-400 font-bold'}>
              {signal.triggered ? 'TRIGGERED' : 'OK'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
