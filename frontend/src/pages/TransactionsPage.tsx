import { useState, useMemo } from 'react';
import { Search, Filter, ArrowRight, X, Download } from 'lucide-react';
import type { Transaction, RiskLevel } from '@/types';
import { demoTransactions } from '@/data/demoData';
import { formatCurrency, timeAgo, formatDateTime } from '@/lib/utils';
import { RiskBadge } from '@/components/RiskBadge';
import { RiskBar } from '@/components/RiskBar';
import { SignalCard } from '@/components/SignalCard';

export function TransactionsPage() {
  const [search, setSearch] = useState('');
  const [riskFilter, setRiskFilter] = useState<RiskLevel | 'ALL'>('ALL');
  const [selected, setSelected] = useState<Transaction | null>(null);

  const filtered = useMemo(() => {
    return demoTransactions.filter((t) => {
      const matchesSearch =
        !search ||
        t.transaction_id.toLowerCase().includes(search.toLowerCase()) ||
        t.sender_id.toLowerCase().includes(search.toLowerCase()) ||
        t.receiver_id.toLowerCase().includes(search.toLowerCase());
      const matchesRisk = riskFilter === 'ALL' || t.risk_assessment?.risk_level === riskFilter;
      return matchesSearch && matchesRisk;
    });
  }, [search, riskFilter]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Transactions</h1>
        <p className="text-sm text-neutral-400 mt-1">
          {demoTransactions.length.toLocaleString()} transactions with ML risk assessments
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-500" />
          <input
            type="text"
            placeholder="Search by transaction ID, sender, or receiver..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-neutral-900 border border-neutral-800 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-neutral-600 transition-colors"
          />
        </div>
        <div className="flex gap-2">
          {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((level) => (
            <button
              key={level}
              onClick={() => setRiskFilter(level)}
              className={`px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                riskFilter === level
                  ? 'bg-white text-black'
                  : 'bg-neutral-900 border border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-700'
              }`}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-neutral-500 border-b border-neutral-800 bg-neutral-900/60">
                <th className="text-left font-medium py-3 px-4">Transaction ID</th>
                <th className="text-left font-medium py-3 px-4 hidden md:table-cell">Sender</th>
                <th className="text-left font-medium py-3 px-4 hidden lg:table-cell">Receiver</th>
                <th className="text-left font-medium py-3 px-4 hidden sm:table-cell">Type</th>
                <th className="text-right font-medium py-3 px-4">Amount</th>
                <th className="text-left font-medium py-3 px-4 hidden md:table-cell">Fraud %</th>
                <th className="text-left font-medium py-3 px-4">Risk</th>
                <th className="text-left font-medium py-3 px-4 hidden sm:table-cell">Time</th>
                <th className="py-3 px-4"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((tx) => (
                <tr
                  key={tx.id}
                  className="border-b border-neutral-800/50 hover:bg-neutral-800/30 cursor-pointer transition-colors"
                  onClick={() => setSelected(tx)}
                >
                  <td className="py-3 px-4 font-mono text-xs text-neutral-300">{tx.transaction_id}</td>
                  <td className="py-3 px-4 hidden md:table-cell text-xs text-neutral-400">{tx.sender_id}</td>
                  <td className="py-3 px-4 hidden lg:table-cell text-xs text-neutral-400">{tx.receiver_id}</td>
                  <td className="py-3 px-4 hidden sm:table-cell">
                    <span className="text-xs px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 font-mono">
                      {tx.transaction_type}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right text-sm font-medium text-neutral-200 tabular-nums">
                    {formatCurrency(tx.amount, tx.currency)}
                  </td>
                  <td className="py-3 px-4 hidden md:table-cell">
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
                  <td className="py-3 px-4">
                    {tx.risk_assessment && <RiskBadge level={tx.risk_assessment.risk_level} />}
                  </td>
                  <td className="py-3 px-4 hidden sm:table-cell text-xs text-neutral-500">
                    {timeAgo(tx.timestamp)}
                  </td>
                  <td className="py-3 px-4">
                    <ArrowRight className="h-4 w-4 text-neutral-600" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <div className="py-12 text-center text-sm text-neutral-500">No transactions match your filters.</div>
        )}
      </div>

      {/* Detail drawer */}
      {selected && <TransactionDetail tx={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function TransactionDetail({ tx, onClose }: { tx: Transaction; onClose: () => void }) {
  const ra = tx.risk_assessment;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-lg h-full bg-neutral-950 border-l border-neutral-800 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-neutral-800 bg-neutral-950 z-10">
          <div>
            <h2 className="text-sm font-bold text-white">Transaction Detail</h2>
            <p className="font-mono text-xs text-neutral-500 mt-0.5">{tx.transaction_id}</p>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Transaction info */}
          <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 space-y-3">
            <DetailRow label="Sender" value={tx.sender_id} />
            <DetailRow label="Receiver" value={tx.receiver_id} />
            <DetailRow label="Amount" value={`${formatCurrency(tx.amount, tx.currency)} ${tx.currency}`} />
            <DetailRow label="Type" value={tx.transaction_type} />
            <DetailRow label="From Bank" value={tx.from_bank} />
            <DetailRow label="To Bank" value={tx.to_bank} />
            <DetailRow label="Timestamp" value={formatDateTime(tx.timestamp)} />
            {tx.is_laundering !== undefined && (
              <DetailRow
                label="Is Laundering"
                value={tx.is_laundering ? 'YES' : 'NO'}
                valueClass={tx.is_laundering ? 'text-red-400 font-bold' : 'text-green-400'}
              />
            )}
          </div>

          {/* Risk assessment */}
          {ra && (
            <>
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-neutral-200">Risk Assessment</h3>
                <RiskBadge level={ra.risk_level} size="md" />
              </div>

              <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 space-y-4">
                <RiskBar score={ra.fraud_probability} label="Fraud Probability" />
                <RiskBar score={ra.anomaly_score} label="Anomaly Score" />
                <RiskBar score={ra.risk_score} label="Overall Risk Score" />

                <div className="pt-2 border-t border-neutral-800">
                  <div className="text-xs text-neutral-500 mb-2">Model Versions</div>
                  {ra.model_versions.map((mv) => (
                    <div key={mv.model_name} className="flex items-center justify-between py-1">
                      <span className="text-xs text-neutral-300">{mv.model_name}</span>
                      <span className="text-xs font-mono text-neutral-500">{mv.version}</span>
                    </div>
                  ))}
                </div>

                <div className="pt-2 border-t border-neutral-800">
                  <div className="text-xs text-neutral-500 mb-1">Evidence IDs</div>
                  <div className="flex flex-wrap gap-2">
                    {ra.evidence_ids.map((eid) => (
                      <span key={eid} className="text-xs font-mono px-2 py-0.5 rounded bg-neutral-800 text-neutral-300">
                        {eid}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Signals */}
              {ra.signals.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-neutral-200 mb-3">Risk Signals</h3>
                  <div className="space-y-2">
                    {ra.signals.map((sig) => (
                      <SignalCard key={sig.id} signal={sig} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <button className="flex-1 py-2.5 rounded-lg bg-white text-black text-sm font-bold hover:bg-neutral-200 transition-colors">
              Analyze Risk
            </button>
            <button className="flex-1 py-2.5 rounded-lg border border-red-600 text-red-500 text-sm font-bold hover:bg-red-600 hover:text-white transition-colors">
              Create Case
            </button>
            <button className="py-2.5 px-3 rounded-lg border border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-700 transition-colors">
              <Download className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-neutral-500">{label}</span>
      <span className={`text-sm text-neutral-200 ${valueClass ?? ''}`}>{value}</span>
    </div>
  );
}
