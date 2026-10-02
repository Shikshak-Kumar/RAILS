import { useEffect, useState } from 'react';
import {
  TrendingUp,
  AlertTriangle,
  FolderOpen,
  FileText,
  DollarSign,
  ShieldAlert,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
} from 'lucide-react';
import type { DashboardStats } from '@/types';
import { dashboardStats, demoTransactions, demoCases } from '@/data/demoData';
import { formatCurrency, formatNumber, timeAgo, riskBarColor } from '@/lib/utils';
import { RiskBadge } from '@/components/RiskBadge';
import { RiskBar } from '@/components/RiskBar';

interface Props {
  onNavigate: (page: 'transactions' | 'cases' | 'reports' | 'copilot') => void;
}

export function DashboardPage({ onNavigate }: Props) {
  const [stats, setStats] = useState<DashboardStats>(dashboardStats);
  const [tickCount, setTickCount] = useState(0);

  useEffect(() => {
    const t = setInterval(() => {
      setStats((s) => ({
        ...s,
        total_transactions: s.total_transactions + Math.floor(Math.random() * 15) + 3,
        fraud_detected: s.fraud_detected + (Math.random() < 0.1 ? 1 : 0),
      }));
      setTickCount((c) => c + 1);
    }, 3000);
    return () => clearInterval(t);
  }, []);

  const recentHighRisk = demoTransactions
    .filter((t) => t.risk_assessment && (t.risk_assessment.risk_level === 'HIGH' || t.risk_assessment.risk_level === 'CRITICAL'))
    .slice(0, 6);

  const recentCases = demoCases.slice(0, 4);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Risk Intelligence Overview</h1>
        <p className="text-sm text-neutral-400 mt-1">
          Real-time fraud, liquidity, credit, and regulatory monitoring across 3.1M transactions
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Transactions"
          value={formatNumber(stats.total_transactions)}
          icon={Activity}
          trend="+1.2%"
          trendUp
          accent="text-white"
        />
        <StatCard
          label="High Risk"
          value={formatNumber(stats.high_risk_count)}
          icon={ShieldAlert}
          trend="+0.4%"
          trendUp
          accent="text-red-400"
        />
        <StatCard
          label="Critical Alerts"
          value={formatNumber(stats.critical_count)}
          icon={AlertTriangle}
          trend="+3"
          trendUp
          accent="text-red-500"
          pulse
        />
        <StatCard
          label="Total Volume"
          value={formatCurrency(stats.total_volume)}
          icon={DollarSign}
          accent="text-green-400"
        />
        <StatCard
          label="Fraud Detected"
          value={formatNumber(stats.fraud_detected)}
          icon={Zap}
          trend="+2"
          trendUp
          accent="text-yellow-400"
        />
        <StatCard
          label="Open Cases"
          value={String(stats.open_cases)}
          icon={FolderOpen}
          accent="text-yellow-400"
          onClick={() => onNavigate('cases')}
        />
        <StatCard
          label="Pending Reports"
          value={String(stats.pending_reports)}
          icon={FileText}
          accent="text-yellow-400"
          onClick={() => onNavigate('reports')}
        />
        <StatCard
          label="Avg Risk Score"
          value={`${Math.round(stats.avg_risk_score * 100)}%`}
          icon={TrendingUp}
          trend="-0.1%"
          accent="text-green-400"
        />
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk distribution */}
        <div className="lg:col-span-2 rounded-xl border border-neutral-800 bg-neutral-900/40 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-neutral-200">Risk Level Distribution</h2>
            <span className="text-xs text-neutral-500">Last 24 hours</span>
          </div>
          <div className="space-y-3">
            <RiskDistRow label="Critical" count={1247} total={3147892} color="bg-red-600" />
            <RiskDistRow label="High" count={8421} total={3147892} color="bg-red-500" />
            <RiskDistRow label="Medium" count={47820} total={3147892} color="bg-yellow-500" />
            <RiskDistRow label="Low" count={3090404} total={3147892} color="bg-green-600" />
          </div>
        </div>

        {/* Model status */}
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5">
          <h2 className="text-sm font-semibold text-neutral-200 mb-4">ML Model Status</h2>
          <div className="space-y-3">
            <ModelStatusRow name="Fraud Model" version="v2.1.0" status="active" />
            <ModelStatusRow name="Anomaly Model" version="v1.3.0" status="active" />
            <ModelStatusRow name="Account Risk" version="v1.0.2" status="active" />
            <ModelStatusRow name="Liquidity Model" version="v0.9.1" status="active" />
            <ModelStatusRow name="Credit Model" version="v1.1.0" status="active" />
          </div>
        </div>
      </div>

      {/* Recent high-risk transactions */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-neutral-200">Recent High-Risk Transactions</h2>
          <button
            onClick={() => onNavigate('transactions')}
            className="text-xs text-neutral-400 hover:text-white flex items-center gap-1 transition-colors"
          >
            View all <ArrowUpRight className="h-3 w-3" />
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-neutral-500 border-b border-neutral-800">
                <th className="text-left font-medium py-2 pr-4">Transaction ID</th>
                <th className="text-left font-medium py-2 pr-4 hidden md:table-cell">Sender</th>
                <th className="text-left font-medium py-2 pr-4 hidden md:table-cell">Amount</th>
                <th className="text-left font-medium py-2 pr-4 hidden sm:table-cell">Fraud %</th>
                <th className="text-left font-medium py-2 pr-4 hidden sm:table-cell">Anomaly</th>
                <th className="text-left font-medium py-2 pr-4">Risk</th>
                <th className="text-left font-medium py-2">Time</th>
              </tr>
            </thead>
            <tbody>
              {recentHighRisk.map((tx) => (
                <tr
                  key={tx.id}
                  className="border-b border-neutral-800/50 hover:bg-neutral-800/30 cursor-pointer transition-colors"
                  onClick={() => onNavigate('transactions')}
                >
                  <td className="py-2.5 pr-4 font-mono text-xs text-neutral-300">{tx.transaction_id}</td>
                  <td className="py-2.5 pr-4 hidden md:table-cell text-xs text-neutral-400">{tx.sender_id}</td>
                  <td className="py-2.5 pr-4 hidden md:table-cell text-xs text-neutral-300">
                    {formatCurrency(tx.amount, tx.currency)}
                  </td>
                  <td className="py-2.5 pr-4 hidden sm:table-cell">
                    <span className="text-xs font-bold text-red-400 tabular-nums">
                      {Math.round((tx.risk_assessment?.fraud_probability ?? 0) * 100)}%
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 hidden sm:table-cell">
                    <span className="text-xs font-bold text-red-400 tabular-nums">
                      {Math.round((tx.risk_assessment?.anomaly_score ?? 0) * 100)}%
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <RiskBadge level={tx.risk_assessment!.risk_level} />
                  </td>
                  <td className="py-2.5 text-xs text-neutral-500">{timeAgo(tx.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent cases */}
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-neutral-200">Active Cases</h2>
          <button
            onClick={() => onNavigate('cases')}
            className="text-xs text-neutral-400 hover:text-white flex items-center gap-1 transition-colors"
          >
            View all <ArrowUpRight className="h-3 w-3" />
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {recentCases.map((c) => (
            <div
              key={c.id}
              className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 hover:border-neutral-700 cursor-pointer transition-colors"
              onClick={() => onNavigate('cases')}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="font-mono text-xs text-neutral-500">{c.case_id}</span>
                <RiskBadge level={c.risk_level} />
              </div>
              <h3 className="text-sm font-semibold text-neutral-100 mb-1 line-clamp-1">{c.title}</h3>
              <p className="text-xs text-neutral-400 line-clamp-2">{c.description}</p>
              <div className="mt-2 flex items-center justify-between text-[10px] text-neutral-500">
                <span>{c.assigned_to}</span>
                <span>{timeAgo(c.updated_at)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Copilot CTA */}
      <div className="rounded-xl border border-neutral-800 bg-gradient-to-br from-neutral-900 to-neutral-950 p-6">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white">
            <Zap className="h-6 w-6 text-black" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-bold text-white">Ask the Risk Copilot</h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Natural language queries with ML-backed evidence, verification, and audit-ready outputs
            </p>
          </div>
          <button
            onClick={() => onNavigate('copilot')}
            className="px-4 py-2 rounded-lg bg-white text-black text-sm font-bold hover:bg-neutral-200 transition-colors"
          >
            Open Copilot
          </button>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  trendUp,
  accent,
  pulse,
  onClick,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  trend?: string;
  trendUp?: boolean;
  accent: string;
  pulse?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      className={`rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 ${onClick ? 'cursor-pointer hover:border-neutral-700 transition-colors' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-neutral-400">{label}</span>
        <Icon className={`h-4 w-4 ${accent} ${pulse ? 'animate-pulse' : ''}`} />
      </div>
      <div className={`text-xl font-bold tabular-nums ${accent}`}>{value}</div>
      {trend && (
        <div className="mt-1 flex items-center gap-1 text-[10px]">
          {trendUp ? (
            <ArrowUpRight className="h-3 w-3 text-red-400" />
          ) : (
            <ArrowDownRight className="h-3 w-3 text-green-400" />
          )}
          <span className={trendUp ? 'text-red-400' : 'text-green-400'}>{trend}</span>
          <span className="text-neutral-600">vs yesterday</span>
        </div>
      )}
    </div>
  );
}

function RiskDistRow({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  const pct = (count / total) * 100;
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-neutral-300">{label}</span>
        <span className="text-xs text-neutral-500 tabular-nums">{formatNumber(count)} ({pct.toFixed(1)}%)</span>
      </div>
      <div className="h-2.5 w-full rounded-full bg-neutral-800 overflow-hidden">
        <div className={`h-2.5 ${color} rounded-full transition-all duration-1000`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

function ModelStatusRow({ name, version, status }: { name: string; version: string; status: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${status === 'active' ? 'bg-green-500' : 'bg-neutral-600'}`} />
        <span className="text-sm text-neutral-200">{name}</span>
      </div>
      <span className="text-xs font-mono text-neutral-500">{version}</span>
    </div>
  );
}
