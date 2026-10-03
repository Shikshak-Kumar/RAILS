import { useState, useEffect } from 'react';
import { FileText, Download, CheckCircle2, Clock, AlertCircle, X, Loader2, Shield, ExternalLink } from 'lucide-react';
import type { RegulatoryReport, ReportStatus, STRDraft } from '@/types';
import { api } from '@/lib/api';
import { formatDateTime, timeAgo, formatCurrency } from '@/lib/utils';
import { RiskBadge } from '@/components/RiskBadge';

const statusConfig: Record<string, { color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  DRAFT: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: AlertCircle },
  IN_REVIEW: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', icon: Clock },
  APPROVED: { color: 'text-green-400', bg: 'bg-green-600/10', icon: CheckCircle2 },
  REJECTED: { color: 'text-red-400', bg: 'bg-red-500/10', icon: X },
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
  const [reports, setReports] = useState<RegulatoryReport[]>([]);
  const [statusFilter, setStatusFilter] = useState<ReportStatus | 'ALL'>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = async (statusOverride?: ReportStatus | 'ALL') => {
    try {
      setLoading(true);
      setError(null);
      const effectiveStatus = statusOverride !== undefined ? statusOverride : statusFilter;
      const res = await api.getReports(effectiveStatus);
      setReports(res || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports(statusFilter);
  }, [statusFilter]);

  const handleStatusFilterChange = (newStatus: ReportStatus | 'ALL') => {
    setStatusFilter(newStatus);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Regulatory Reports</h1>
        <p className="text-sm text-neutral-400 mt-1">
          Suspicious Transaction Reports (STR/SAR) with human-in-the-loop compliance review and legal audit trails
        </p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-neutral-800 pb-3">
        <div className="flex gap-2 flex-wrap items-center">
          {(['ALL', 'DRAFT', 'APPROVED', 'REJECTED'] as const).map((s) => (
            <button
              key={s}
              onClick={() => handleStatusFilterChange(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                statusFilter === s
                  ? 'bg-white text-black shadow-sm'
                  : 'bg-neutral-900 border border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-700'
              }`}
            >
              {s}
            </button>
          ))}
          {loading && (
            <div className="flex items-center gap-1.5 text-xs text-neutral-400 ml-2 animate-pulse">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-neutral-400" />
              <span>Updating...</span>
            </div>
          )}
        </div>
        <span className="text-xs text-neutral-500 font-mono">
          Showing {reports.length} {reports.length === 1 ? 'report' : 'reports'}
        </span>
      </div>

      <div className="space-y-3">
        {error && (
          <div className="py-12 text-center text-sm text-red-500">Error loading reports: {error}</div>
        )}
        {!loading && !error && reports.length === 0 && (
          <div className="py-12 text-center text-sm text-neutral-500">
            {statusFilter === 'APPROVED' ? (
              'No approved reports found.'
            ) : statusFilter === 'REJECTED' ? (
              'No rejected reports found.'
            ) : statusFilter === 'DRAFT' ? (
              'No draft reports found.'
            ) : (
              'No reports available. Generate an STR draft from any case in the Cases page.'
            )}
          </div>
        )}
        {reports.map((r) => {
          const sc = statusConfig[r.status] || statusConfig['DRAFT'];
          const StatusIcon = sc.icon;
          return (
            <div
              key={r.id || r.report_id}
              className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5 hover:border-neutral-700 cursor-pointer transition-colors"
              onClick={() => setSelected(r)}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-center gap-3">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${typeColors[r.type] || 'bg-neutral-700'} text-white`}>
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
              <p className="text-xs text-neutral-400 line-clamp-2">
                {r.structured_data?.executive_summary || r.body.replace(/\*\*/g, '').slice(0, 160)}
              </p>
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

      {selected && (
        <ReportDetail
          report={selected}
          onClose={() => setSelected(null)}
          onRefresh={() => {
            fetchReports();
            setSelected(null);
          }}
        />
      )}
    </div>
  );
}

function ReportDetail({
  report: initialReport,
  onClose,
  onRefresh,
}: {
  report: RegulatoryReport;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const [report, setReport] = useState<RegulatoryReport>(initialReport);
  const [processing, setProcessing] = useState(false);
  const [notice, setNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const sc = statusConfig[report.status] || statusConfig['DRAFT'];
  const StatusIcon = sc.icon;
  const sd: STRDraft | undefined = report.structured_data;

  const handleApprove = async () => {
    try {
      setProcessing(true);
      setNotice(null);
      const updated = await api.approveReport(report.report_id || report.id);
      setReport({ ...report, status: 'APPROVED', approved_by: updated.approved_by || 'Compliance Officer' });
      setNotice({ type: 'success', message: 'Report approved and validated for regulatory filing.' });
      onRefresh();
    } catch (err: any) {
      setNotice({ type: 'error', message: `Approval failed: ${err.message}` });
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    try {
      setProcessing(true);
      setNotice(null);
      await api.rejectReport(report.report_id || report.id);
      setReport({ ...report, status: 'REJECTED' });
      setNotice({ type: 'success', message: 'Report marked as REJECTED.' });
      onRefresh();
    } catch (err: any) {
      setNotice({ type: 'error', message: `Rejection failed: ${err.message}` });
    } finally {
      setProcessing(false);
    }
  };

  const handleExportDocx = async () => {
    try {
      setProcessing(true);
      setNotice(null);
      api.downloadReportFile(report.report_id || report.id);
      setNotice({ type: 'success', message: 'Report download initiated from backend.' });
    } catch (err: any) {
      setNotice({ type: 'error', message: `Export failed: ${err.message}` });
    } finally {
      setProcessing(false);
    }
  };

  const cleanBodyText = (text: string) => {
    return text.replace(/\*\*/g, '').replace(/###?\s*/g, '');
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-2xl h-full bg-neutral-950 border-l border-neutral-800 overflow-y-auto">
        <div className="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-neutral-800 bg-neutral-950 z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-neutral-900 border border-neutral-800">
              <FileText className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">STR Filing Draft</h2>
              <p className="text-xs text-neutral-500">Case: {report.case_id || sd?.case_id}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md ${sc.bg}`}>
              <StatusIcon className={`h-3 w-3 ${sc.color}`} />
              <span className={`text-[10px] font-bold uppercase ${sc.color}`}>{report.status.replace('_', ' ')}</span>
            </div>
            <button onClick={onClose} className="text-neutral-400 hover:text-white transition-colors">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-5 space-y-5">
          {notice && (
            <div
              className={`p-3 rounded-lg text-xs font-medium ${
                notice.type === 'success'
                  ? 'bg-green-600/10 text-green-400 border border-green-600/30'
                  : 'bg-red-600/10 text-red-400 border border-red-600/30'
              }`}
            >
              {notice.message}
            </div>
          )}

          <div>
            <h3 className="text-base font-bold text-white">{report.title}</h3>
            {report.approved_by && (
              <p className="text-xs text-green-400 mt-1">Approved by: {report.approved_by}</p>
            )}
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
            <h4 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Case Information</h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-neutral-500">Case ID:</span>
                <p className="font-mono text-neutral-200 mt-0.5">{report.case_id || sd?.case_id}</p>
              </div>
              <div>
                <span className="text-neutral-500">Report ID:</span>
                <p className="font-mono text-neutral-200 mt-0.5">{report.report_id || sd?.report_id}</p>
              </div>
              <div>
                <span className="text-neutral-500">Report Type:</span>
                <p className="text-neutral-200 mt-0.5">{report.type || sd?.report_type || 'STR'}</p>
              </div>
              <div>
                <span className="text-neutral-500">Created At:</span>
                <p className="text-neutral-200 mt-0.5">{formatDateTime(report.created_at)}</p>
              </div>
              <div className="col-span-2">
                <span className="text-neutral-500">Reporting Institution:</span>
                <p className="text-neutral-200 mt-0.5">
                  {sd?.reporting_institution || 'Reporting Financial Institution: Not configured'}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
            <h4 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Transaction Details</h4>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-neutral-500">Transaction ID:</span>
                <p className="font-mono text-neutral-200 mt-0.5">
                  {sd?.transaction_id || 'N/A'}
                </p>
              </div>
              <div>
                <span className="text-neutral-500">Transaction Date:</span>
                <p className="text-neutral-200 mt-0.5">
                  {sd?.transaction_date || 'Not available in source data'}
                </p>
              </div>
              <div>
                <span className="text-neutral-500">Amount:</span>
                <p className="text-neutral-200 font-semibold mt-0.5">
                  {sd?.transaction_amount !== undefined
                    ? formatCurrency(sd.transaction_amount, sd.currency || 'USD')
                    : 'N/A'}
                </p>
              </div>
              <div>
                <span className="text-neutral-500">Payment Method:</span>
                <p className="text-neutral-200 mt-0.5">{sd?.payment_method || 'Electronic Transfer'}</p>
              </div>
              <div>
                <span className="text-neutral-500">Sender Account:</span>
                <p className="font-mono text-neutral-300 mt-0.5">{sd?.sender_account || 'N/A'}</p>
              </div>
              <div>
                <span className="text-neutral-500">Receiver Account:</span>
                <p className="font-mono text-neutral-300 mt-0.5">{sd?.receiver_account || 'N/A'}</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
            <h4 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Risk Assessment</h4>
            <div className="flex items-center gap-4">
              <RiskBadge level={sd?.risk_level || 'HIGH'} size="md" />
              <div className="text-xs">
                <span className="text-neutral-500">Fraud Probability:</span>
                <span className="text-red-400 font-mono font-bold ml-1.5">
                  {sd?.fraud_probability !== undefined ? `${(sd.fraud_probability * 100).toFixed(1)}%` : 'N/A'}
                </span>
              </div>
              <div className="text-xs">
                <span className="text-neutral-500">Anomaly Score:</span>
                <span className="text-red-400 font-mono font-bold ml-1.5">
                  {sd?.anomaly_score !== undefined ? sd.anomaly_score.toFixed(3) : 'N/A'}
                </span>
              </div>
            </div>

            {(sd?.risk_signals && sd.risk_signals.length > 0) && (
              <div className="pt-2">
                <span className="text-[11px] text-neutral-500 block mb-1.5">Triggered Risk Indicators:</span>
                <div className="flex flex-wrap gap-1.5">
                  {sd.risk_signals.map((sig, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-red-950/60 border border-red-800/40 text-red-300 text-[11px] font-mono"
                    >
                      {sig}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-2">
            <h4 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Executive Summary</h4>
            <p className="text-xs text-neutral-300 leading-relaxed">
              {sd?.executive_summary || cleanBodyText(report.body).slice(0, 300)}
            </p>
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-2">
            <h4 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Suspicious Activity Description</h4>
            <p className="text-xs text-neutral-300 leading-relaxed whitespace-pre-wrap">
              {sd?.suspicious_activity_description || cleanBodyText(report.body)}
            </p>
          </div>

          {sd?.regulatory_context && sd.regulatory_context.length > 0 && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
              <h4 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Regulatory Guidance</h4>
              <div className="space-y-2">
                {sd.regulatory_context.map((c, i) => (
                  <div key={i} className="p-3 rounded-lg bg-neutral-950/80 border border-neutral-800 text-xs space-y-1">
                    <div className="flex items-center justify-between text-neutral-400">
                      <span className="font-bold text-neutral-200">
                        {c.authority} • {c.document_name}
                      </span>
                      <span className="font-mono text-[10px] text-neutral-500">
                        {c.jurisdiction} {c.section ? `• ${c.section}` : ''} {c.page_number ? `• p.${c.page_number}` : ''}
                      </span>
                    </div>
                    <p className="text-neutral-400 text-[11px]">{c.summary}</p>
                    <div className="text-[10px] font-mono text-neutral-600">ID: {c.citation_id}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {sd?.supporting_evidence && sd.supporting_evidence.length > 0 && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-2">
              <h4 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Supporting Evidence</h4>
              <div className="flex flex-wrap gap-2">
                {sd.supporting_evidence.map((ev, i) => (
                  <div key={i} className="px-2.5 py-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs">
                    <span className="font-mono text-neutral-200">{ev.evidence_id}</span>
                    <span className="text-neutral-500 text-[10px] ml-1.5">— {ev.purpose}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-1.5">
            <h4 className="text-xs font-bold text-neutral-300 uppercase tracking-wider">Analyst Review & Recommended Next Step</h4>
            <p className="text-xs text-neutral-300">{sd?.analyst_notes || 'Compliance review required before filing.'}</p>
            <p className="text-xs text-neutral-400">
              <span className="text-neutral-500">Next Action:</span> {sd?.recommended_next_step || 'Verify counterparty KYC profiles and finalize determination.'}
            </p>
          </div>

          <div className="space-y-2 pt-2">
            {report.status === 'DRAFT' || report.status === 'IN_REVIEW' ? (
              <>
                <button
                  onClick={handleApprove}
                  disabled={processing}
                  className="w-full py-2.5 rounded-lg bg-green-600 text-white text-sm font-bold hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2 shadow-sm"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Approve Report
                </button>
                <button
                  onClick={handleExportDocx}
                  disabled={processing}
                  className="w-full py-2.5 rounded-lg border border-neutral-700 bg-neutral-900 text-neutral-200 text-sm font-bold hover:bg-neutral-800 hover:text-white disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  <Download className="h-4 w-4" />
                  Export as DOCX / Text
                </button>
                <button
                  onClick={handleReject}
                  disabled={processing}
                  className="w-full py-2.5 rounded-lg border border-red-800/80 bg-red-950/20 text-red-400 text-sm font-bold hover:bg-red-900/40 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  <X className="h-4 w-4" />
                  Reject Report
                </button>
              </>
            ) : (
              <button
                onClick={handleExportDocx}
                disabled={processing}
                className="w-full py-2.5 rounded-lg bg-white text-black text-sm font-bold hover:bg-neutral-200 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="h-4 w-4" />
                Download Report File
              </button>
            )}
          </div>

          <div className="rounded-lg border border-yellow-600/30 bg-yellow-500/5 p-3.5">
            <p className="text-xs text-yellow-400/90 leading-relaxed">
              This report is a DRAFT generated from verified ML surveillance signals and authoritative regulatory guidance. Regulatory filings require human review and approval. No report is automatically submitted.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
