import { useState } from 'react';
import { Search, X, FileText, CheckCircle2, Clock, AlertCircle, User } from 'lucide-react';
import type { Case, CaseStatus } from '@/types';
import { demoCases } from '@/data/demoData';
import { timeAgo, formatDateTime } from '@/lib/utils';
import { RiskBadge } from '@/components/RiskBadge';
import { SignalCard } from '@/components/SignalCard';

const statusConfig: Record<CaseStatus, { color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  OPEN: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: AlertCircle },
  UNDER_REVIEW: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: Clock },
  APPROVED: { color: 'text-green-400', bg: 'bg-green-600/10', icon: CheckCircle2 },
  REJECTED: { color: 'text-red-400', bg: 'bg-red-500/10', icon: X },
  FILED: { color: 'text-green-400', bg: 'bg-green-600/10', icon: CheckCircle2 },
};

export function CasesPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<CaseStatus | 'ALL'>('ALL');
  const [selected, setSelected] = useState<Case | null>(null);

  const filtered = demoCases.filter((c) => {
    const matchesSearch =
      !search ||
      c.case_id.toLowerCase().includes(search.toLowerCase()) ||
      c.title.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Cases</h1>
        <p className="text-sm text-neutral-400 mt-1">
          {demoCases.length} cases — suspicious activity investigations and regulatory filings
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-500" />
          <input
            type="text"
            placeholder="Search by case ID or title..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-neutral-900 border border-neutral-800 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-neutral-600 transition-colors"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          {(['ALL', 'OPEN', 'UNDER_REVIEW', 'APPROVED', 'FILED'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                statusFilter === s
                  ? 'bg-white text-black'
                  : 'bg-neutral-900 border border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-700'
              }`}
            >
              {s.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Case cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((c) => {
          const sc = statusConfig[c.status];
          const StatusIcon = sc.icon;
          return (
            <div
              key={c.id}
              className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5 hover:border-neutral-700 cursor-pointer transition-colors"
              onClick={() => setSelected(c)}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <span className="font-mono text-xs text-neutral-500">{c.case_id}</span>
                  <h3 className="text-sm font-semibold text-neutral-100 mt-1">{c.title}</h3>
                </div>
                <RiskBadge level={c.risk_level} />
              </div>
              <p className="text-xs text-neutral-400 line-clamp-2 mb-3">{c.description}</p>
              <div className="flex items-center justify-between">
                <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md ${sc.bg}`}>
                  <StatusIcon className={`h-3 w-3 ${sc.color}`} />
                  <span className={`text-[10px] font-bold uppercase ${sc.color}`}>{c.status.replace('_', ' ')}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-neutral-500">
                  <span className="flex items-center gap-1">
                    <User className="h-3 w-3" /> {c.assigned_to}
                  </span>
                  <span>{timeAgo(c.updated_at)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="py-12 text-center text-sm text-neutral-500">No cases match your filters.</div>
      )}

      {selected && <CaseDetail caseData={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function CaseDetail({ caseData, onClose }: { caseData: Case; onClose: () => void }) {
  const sc = statusConfig[caseData.status];
  const StatusIcon = sc.icon;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-lg h-full bg-neutral-950 border-l border-neutral-800 overflow-y-auto">
        <div className="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-neutral-800 bg-neutral-950 z-10">
          <div>
            <h2 className="text-sm font-bold text-white">{caseData.case_id}</h2>
            <p className="text-xs text-neutral-500 mt-0.5">{caseData.transaction_id}</p>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <RiskBadge level={caseData.risk_level} size="md" />
              <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md ${sc.bg}`}>
                <StatusIcon className={`h-3 w-3 ${sc.color}`} />
                <span className={`text-[10px] font-bold uppercase ${sc.color}`}>{caseData.status.replace('_', ' ')}</span>
              </div>
            </div>
            <h3 className="text-base font-bold text-white mt-3">{caseData.title}</h3>
            <p className="text-sm text-neutral-400 mt-2">{caseData.description}</p>
          </div>

          <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Assigned to</span>
              <span className="text-sm text-neutral-200">{caseData.assigned_to}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Created</span>
              <span className="text-sm text-neutral-200">{formatDateTime(caseData.created_at)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-500">Last updated</span>
              <span className="text-sm text-neutral-200">{formatDateTime(caseData.updated_at)}</span>
            </div>
            <div className="pt-2 border-t border-neutral-800">
              <span className="text-xs text-neutral-500">Evidence IDs</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {caseData.evidence_ids.map((eid) => (
                  <span key={eid} className="text-xs font-mono px-2 py-0.5 rounded bg-neutral-800 text-neutral-300">
                    {eid}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {caseData.signals.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-neutral-200 mb-3">Risk Signals</h3>
              <div className="space-y-2">
                {caseData.signals.map((sig) => (
                  <SignalCard key={sig.id} signal={sig} />
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="space-y-2">
            <button className="w-full py-2.5 rounded-lg bg-white text-black text-sm font-bold hover:bg-neutral-200 transition-colors flex items-center justify-center gap-2">
              <FileText className="h-4 w-4" />
              Generate STR Draft
            </button>
            {caseData.status === 'OPEN' || caseData.status === 'UNDER_REVIEW' ? (
              <>
                <button className="w-full py-2.5 rounded-lg border border-green-600 text-green-500 text-sm font-bold hover:bg-green-600 hover:text-white transition-colors flex items-center justify-center gap-2">
                  <CheckCircle2 className="h-4 w-4" />
                  Approve & File
                </button>
                <button className="w-full py-2.5 rounded-lg border border-red-600 text-red-500 text-sm font-bold hover:bg-red-600 hover:text-white transition-colors flex items-center justify-center gap-2">
                  <X className="h-4 w-4" />
                  Reject Case
                </button>
              </>
            ) : null}
          </div>

          <div className="rounded-lg border border-yellow-600/30 bg-yellow-500/5 p-3">
            <p className="text-xs text-yellow-400/80">
              Regulatory filings require human review and approval. No report is automatically submitted.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
