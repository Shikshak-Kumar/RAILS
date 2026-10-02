import { useState } from 'react';
import { FileText, Download, CheckCircle2, Clock, AlertCircle, X, BookOpen, Search } from 'lucide-react';
import type { RegulatoryReport, ReportStatus, RegulatorySource } from '@/types';
import { demoReports, demoRegulatorySources } from '@/data/demoData';
import { formatDateTime, timeAgo } from '@/lib/utils';

const statusConfig: Record<ReportStatus, { color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  DRAFT: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: AlertCircle },
  IN_REVIEW: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: Clock },
  APPROVED: { color: 'text-green-400', bg: 'bg-green-600/10', icon: CheckCircle2 },
  FILED: { color: 'text-green-400', bg: 'bg-green-600/10', icon: CheckCircle2 },
};

const typeColors: Record<string, string> = {
  STR: 'bg-red-600',
  SAR: 'bg-red-500',
  CTR: 'bg-yellow-500',
  AML_ALERT: 'bg-yellow-500',
};

export function ReportsPage() {
  const [selected, setSelected] = useState<RegulatoryReport | null>(null);
  const [tab, setTab] = useState<'reports' | 'regulations'>('reports');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Regulatory Reports</h1>
        <p className="text-sm text-neutral-400 mt-1">
          STR, SAR, and AML alert reports with human-in-the-loop approval workflow
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-neutral-800">
        <button
          onClick={() => setTab('reports')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'reports' ? 'border-white text-white' : 'border-transparent text-neutral-500 hover:text-neutral-300'
          }`}
        >
          Reports
        </button>
        <button
          onClick={() => setTab('regulations')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'regulations' ? 'border-white text-white' : 'border-transparent text-neutral-500 hover:text-neutral-300'
          }`}
        >
          Regulatory Sources (RAG)
        </button>
      </div>

      {tab === 'reports' ? (
        <div className="space-y-3">
          {demoReports.map((r) => {
            const sc = statusConfig[r.status];
            const StatusIcon = sc.icon;
            return (
              <div
                key={r.id}
                className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5 hover:border-neutral-700 cursor-pointer transition-colors"
                onClick={() => setSelected(r)}
              >
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${typeColors[r.type]} text-white`}>
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <span className="font-mono text-xs text-neutral-500">{r.report_id}</span>
                      <h3 className="text-sm font-semibold text-neutral-100 mt-0.5">{r.title}</h3>
                    </div>
                  </div>
                  <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md ${sc.bg}`}>
                    <StatusIcon className={`h-3 w-3 ${sc.color}`} />
                    <span className={`text-[10px] font-bold uppercase ${sc.color}`}>{r.status.replace('_', ' ')}</span>
                  </div>
                </div>
                <p className="text-xs text-neutral-400 line-clamp-2">{r.body}</p>
                <div className="mt-3 flex items-center justify-between text-[10px] text-neutral-500">
                  <div className="flex items-center gap-3">
                    <span>Case: {r.case_id}</span>
                    <span>Type: {r.type}</span>
                    {r.approved_by && <span>Approved by: {r.approved_by}</span>}
                  </div>
                  <span>{timeAgo(r.created_at)}</span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <RegulatorySourcesTab sources={demoRegulatorySources} />
      )}

      {selected && <ReportDetail report={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function RegulatorySourcesTab({ sources }: { sources: RegulatorySource[] }) {
  const [search, setSearch] = useState('');
  const filtered = sources.filter(
    (s) =>
      !search ||
      s.document_name.toLowerCase().includes(search.toLowerCase()) ||
      s.text.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-500" />
        <input
          type="text"
          placeholder="Search regulatory documents..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-neutral-900 border border-neutral-800 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-neutral-600 transition-colors"
        />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((src) => (
          <div key={src.evidence_id} className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
            <div className="flex items-start gap-3 mb-2">
              <BookOpen className="h-4 w-4 text-neutral-400 mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-neutral-100">{src.document_name}</h3>
                <p className="text-xs text-neutral-500 mt-0.5">{src.section} — p.{src.page}</p>
              </div>
            </div>
            <p className="text-xs text-neutral-400 leading-relaxed">{src.text}</p>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-[10px] font-mono text-neutral-600">{src.document_id}</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400">
                {src.evidence_id}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReportDetail({ report, onClose }: { report: RegulatoryReport; onClose: () => void }) {
  const sc = statusConfig[report.status];
  const StatusIcon = sc.icon;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-2xl h-full bg-neutral-950 border-l border-neutral-800 overflow-y-auto">
        <div className="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-neutral-800 bg-neutral-950 z-10">
          <div>
            <h2 className="text-sm font-bold text-white">{report.report_id}</h2>
            <p className="text-xs text-neutral-500 mt-0.5">{report.type} — Case {report.case_id}</p>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div className="flex items-center gap-3">
            <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${typeColors[report.type]} text-white`}>
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">{report.title}</h3>
              <div className="mt-1 flex items-center gap-2">
                <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md ${sc.bg}`}>
                  <StatusIcon className={`h-3 w-3 ${sc.color}`} />
                  <span className={`text-[10px] font-bold uppercase ${sc.color}`}>{report.status.replace('_', ' ')}</span>
                </div>
                {report.approved_by && (
                  <span className="text-xs text-neutral-500">by {report.approved_by}</span>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
            <div className="text-xs text-neutral-500 mb-2">Report Body</div>
            <p className="text-sm text-neutral-200 leading-relaxed whitespace-pre-wrap">{report.body}</p>
          </div>

          <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
            <div className="text-xs text-neutral-500 mb-2">Evidence Chain</div>
            <div className="flex flex-wrap gap-2">
              {report.evidence_ids.map((eid) => (
                <span key={eid} className="text-xs font-mono px-2 py-1 rounded bg-neutral-800 text-neutral-300">
                  {eid}
                </span>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-neutral-500">
            <span>Created: {formatDateTime(report.created_at)}</span>
          </div>

          {/* Actions */}
          <div className="space-y-2">
            {report.status === 'DRAFT' || report.status === 'IN_REVIEW' ? (
              <>
                <button className="w-full py-2.5 rounded-lg bg-green-600 text-white text-sm font-bold hover:bg-green-700 transition-colors flex items-center justify-center gap-2">
                  <CheckCircle2 className="h-4 w-4" />
                  Approve Report
                </button>
                <button className="w-full py-2.5 rounded-lg border border-neutral-700 text-neutral-400 text-sm font-bold hover:text-white hover:border-neutral-600 transition-colors flex items-center justify-center gap-2">
                  <Download className="h-4 w-4" />
                  Export as DOCX
                </button>
                <button className="w-full py-2.5 rounded-lg border border-red-600 text-red-500 text-sm font-bold hover:bg-red-600 hover:text-white transition-colors flex items-center justify-center gap-2">
                  <X className="h-4 w-4" />
                  Reject Report
                </button>
              </>
            ) : (
              <button className="w-full py-2.5 rounded-lg bg-white text-black text-sm font-bold hover:bg-neutral-200 transition-colors flex items-center justify-center gap-2">
                <Download className="h-4 w-4" />
                Download DOCX
              </button>
            )}
          </div>

          <div className="rounded-lg border border-yellow-600/30 bg-yellow-500/5 p-3">
            <p className="text-xs text-yellow-400/80">
              This report was generated from ML evidence and regulatory RAG sources. Human review and approval are required before any regulatory filing. No report is automatically submitted.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
