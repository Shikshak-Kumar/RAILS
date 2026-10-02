import { useState } from 'react';
import { Play, Pause, RotateCcw, Activity, Zap, TrendingUp, AlertTriangle } from 'lucide-react';
import type { SimulationType, Transaction, SimulationSummary } from '@/types';
import { api } from '@/lib/api';

const simulationPresets: Record<SimulationType, { label: string; description: string; color: string }> = {
  normal: { label: 'Normal Activity', description: 'Standard baseline transactions', color: 'green' },
  high_velocity: { label: 'High Velocity', description: 'Rapid sequential transfers', color: 'red' },
  fan_in: { label: 'Fan-In', description: 'Multiple senders to one receiver', color: 'yellow' },
  fan_out: { label: 'Fan-Out', description: 'One sender to multiple receivers', color: 'red' },
  rapid_fund_movement: { label: 'Rapid Movement', description: 'Quick in/out of funds', color: 'red' },
  unusual_amount: { label: 'Unusual Amount', description: 'Large spikes in amounts', color: 'yellow' },
  liquidity_stress: { label: 'Liquidity Stress', description: 'High outflow ratio', color: 'red' },
  mixed_risk: { label: 'Mixed Risk', description: 'Combination of patterns', color: 'yellow' }
};
import { formatCurrency, timeAgo } from '@/lib/utils';
import { RiskBadge } from '@/components/RiskBadge';
import { RiskBar } from '@/components/RiskBar';

export function SimulationPage() {
  const [selectedType, setSelectedType] = useState<SimulationType>('normal');
  const [count, setCount] = useState(20);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<SimulationSummary | null>(null);

  const run = async () => {
    setRunning(true);
    setResults([]);
    setSummary(null);

    try {
      await api.startSimulation(selectedType, count);
      // Wait for background tasks to process
      await new Promise(resolve => setTimeout(resolve, 2000));
      const res = await api.getTransactions(count);
      const txns = res.items || [];
      setResults(txns);
      
      const highRisk = txns.filter((t: Transaction) => t.risk_assessment && (t.risk_assessment.risk_level === 'HIGH' || t.risk_assessment.risk_level === 'CRITICAL')).length;
      const critical = txns.filter((t: Transaction) => t.risk_assessment && t.risk_assessment.risk_level === 'CRITICAL').length;
      setSummary({
        total_transactions: txns.length,
        high_risk: highRisk,
        critical: critical,
        cases_generated: critical, // Approx logic for UI
        avg_fraud_probability: txns.reduce((a: number, b: Transaction) => a + (b.risk_assessment?.fraud_probability || 0), 0) / (txns.length || 1),
        avg_anomaly_score: txns.reduce((a: number, b: Transaction) => a + (b.risk_assessment?.anomaly_score || 0), 0) / (txns.length || 1)
      });
    } catch (err: any) {
      alert('Simulation failed: ' + err.message);
    } finally {
      setRunning(false);
    }
  };

  const reset = () => {
    setResults([]);
    setSummary(null);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Simulation Lab</h1>
        <p className="text-sm text-neutral-400 mt-1">
          Generate synthetic transaction scenarios through the same production ML inference pipeline
        </p>
      </div>

      {/* Scenario picker */}
      <div>
        <h2 className="text-sm font-semibold text-neutral-200 mb-3">Select Scenario</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(Object.keys(simulationPresets) as SimulationType[]).map((type) => {
            const preset = simulationPresets[type];
            const active = selectedType === type;
            const colorClass =
              preset.color === 'green'
                ? 'border-green-600 bg-green-600/10'
                : preset.color === 'yellow'
                  ? 'border-yellow-500 bg-yellow-500/10'
                  : 'border-red-600 bg-red-600/10';
            return (
              <button
                key={type}
                onClick={() => setSelectedType(type)}
                className={`rounded-lg border p-3 text-left transition-all ${
                  active
                    ? colorClass
                    : 'border-neutral-800 bg-neutral-900/40 hover:border-neutral-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-bold ${active ? 'text-white' : 'text-neutral-300'}`}>
                    {preset.label}
                  </span>
                  <span
                    className={`h-2 w-2 rounded-full ${
                      preset.color === 'green' ? 'bg-green-500' : preset.color === 'yellow' ? 'bg-yellow-500' : 'bg-red-500'
                    }`}
                  />
                </div>
                <p className="text-[10px] text-neutral-500">{preset.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Controls */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex items-center gap-3">
            <label className="text-xs text-neutral-400">Transactions:</label>
            <input
              type="range"
              min="5"
              max="100"
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="w-32 accent-white"
            />
            <span className="text-sm font-bold text-white tabular-nums w-8">{count}</span>
          </div>
          <div className="flex gap-2 ml-auto">
            <button
              onClick={run}
              disabled={running}
              className="px-4 py-2 rounded-lg bg-white text-black text-sm font-bold hover:bg-neutral-200 disabled:opacity-40 transition-colors flex items-center gap-2"
            >
              {running ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              {running ? 'Running...' : 'Run Simulation'}
            </button>
            {results.length > 0 && (
              <button
                onClick={reset}
                className="px-4 py-2 rounded-lg border border-neutral-800 text-neutral-400 text-sm font-bold hover:text-white hover:border-neutral-600 transition-colors flex items-center gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                Reset
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Running indicator */}
      {running && (
        <div className="rounded-xl border border-yellow-600/30 bg-yellow-500/5 p-4 flex items-center gap-3">
          <Activity className="h-5 w-5 text-yellow-400 animate-pulse" />
          <span className="text-sm text-yellow-400">
            Generating {count} {simulationPresets[selectedType].label} transactions through ML inference pipeline...
          </span>
        </div>
      )}

      {/* Results */}
      {summary && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <SummaryCard label="Total Transactions" value={String(summary.total_transactions)} icon={Activity} color="text-white" />
            <SummaryCard label="High Risk" value={String(summary.high_risk)} icon={AlertTriangle} color="text-red-400" />
            <SummaryCard label="Critical" value={String(summary.critical)} icon={Zap} color="text-red-500" />
            <SummaryCard label="Cases Generated" value={String(summary.cases_generated)} icon={TrendingUp} color="text-yellow-400" />
          </div>

          {/* Avg scores */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
              <RiskBar score={summary.avg_fraud_probability} label="Avg Fraud Probability" />
            </div>
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
              <RiskBar score={summary.avg_anomaly_score} label="Avg Anomaly Score" />
            </div>
          </div>

          {/* Transaction list */}
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 overflow-hidden">
            <div className="px-5 py-3 border-b border-neutral-800">
              <h3 className="text-sm font-semibold text-neutral-200">Generated Transactions</h3>
            </div>
            <div className="overflow-x-auto max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0">
                  <tr className="text-xs text-neutral-500 border-b border-neutral-800 bg-neutral-900">
                    <th className="text-left font-medium py-2 px-4">Transaction ID</th>
                    <th className="text-left font-medium py-2 px-4 hidden md:table-cell">Sender</th>
                    <th className="text-right font-medium py-2 px-4">Amount</th>
                    <th className="text-left font-medium py-2 px-4 hidden sm:table-cell">Type</th>
                    <th className="text-left font-medium py-2 px-4 hidden sm:table-cell">Fraud %</th>
                    <th className="text-left font-medium py-2 px-4">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((tx) => (
                    <tr key={tx.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                      <td className="py-2 px-4 font-mono text-xs text-neutral-300">{tx.transaction_id}</td>
                      <td className="py-2 px-4 hidden md:table-cell text-xs text-neutral-400">{tx.sender_id}</td>
                      <td className="py-2 px-4 text-right text-xs text-neutral-300 tabular-nums">
                        {formatCurrency(tx.amount, tx.currency)}
                      </td>
                      <td className="py-2 px-4 hidden sm:table-cell">
                        <span className="text-[10px] px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 font-mono">
                          {tx.transaction_type}
                        </span>
                      </td>
                      <td className="py-2 px-4 hidden sm:table-cell">
                        {tx.risk_assessment && (
                          <span
                            className={`text-xs font-bold tabular-nums ${
                              tx.risk_assessment.fraud_probability >= 0.7
                                ? 'text-red-400'
                                : tx.risk_assessment.fraud_probability >= 0.4
                                  ? 'text-yellow-400'
                                  : 'text-green-400'
                            }`}
                          >
                            {Math.round(tx.risk_assessment.fraud_probability * 100)}%
                          </span>
                        )}
                      </td>
                      <td className="py-2 px-4">
                        {tx.risk_assessment && <RiskBadge level={tx.risk_assessment.risk_level} />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!running && !summary && (
        <div className="py-16 text-center">
          <Activity className="h-10 w-10 text-neutral-700 mx-auto mb-3" />
          <p className="text-sm text-neutral-500">
            Select a scenario and click "Run Simulation" to generate transactions through the ML pipeline.
          </p>
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-neutral-400">{label}</span>
        <Icon className={`h-4 w-4 ${color}`} />
      </div>
      <div className={`text-xl font-bold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}
