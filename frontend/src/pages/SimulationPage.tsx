import { useState, useEffect, useRef } from 'react';
import {
  Play,
  RotateCcw,
  Activity,
  Zap,
  TrendingUp,
  AlertTriangle,
  Download,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import type { SimulationType, Transaction, SimulationSummary } from '@/types';
import { api } from '@/lib/api';
import { formatCurrency, timeAgo } from '@/lib/utils';
import { RiskBadge } from '@/components/RiskBadge';

const LOCAL_STORAGE_KEY = 'rails.activeSimulationJob';

const simulationPresets: Record<SimulationType, { label: string; description: string; color: string }> = {
  normal: { label: 'Normal Activity', description: 'Standard baseline transfers', color: 'green' },
  high_velocity: { label: 'High Velocity', description: 'Rapid sequential bursts from single account', color: 'red' },
  fan_in: { label: 'Fan-In', description: 'Multiple senders aggregating to one receiver', color: 'yellow' },
  fan_out: { label: 'Fan-Out', description: 'One sender dispersing to multiple receivers', color: 'red' },
  rapid_fund_movement: { label: 'Rapid Movement', description: 'Immediate in/out pass-through flow', color: 'red' },
  unusual_amount: { label: 'Unusual Amount', description: 'Spikes 100x above account baseline', color: 'yellow' },
  liquidity_stress: { label: 'Liquidity Stress', description: 'High outflow ratio threatening reserve', color: 'red' },
  mixed_risk: { label: 'Mixed Risk', description: 'Realistic combination of retail & fraud patterns', color: 'yellow' },
};

type JobStatus = 'IDLE' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';

interface PersistedJob {
  job_id: string;
  scenario: SimulationType;
  total: number;
  started_at: string;
}

export function SimulationPage() {
  const [selectedType, setSelectedType] = useState<SimulationType>('normal');
  const [count, setCount] = useState(20);
  const [status, setStatus] = useState<JobStatus>('IDLE');
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [results, setResults] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<SimulationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const reattachToJob = async (jobId: string) => {
    stopPolling();
    setActiveJobId(jobId);
    setStatus('RUNNING');
    setError(null);

    const checkJob = async () => {
      try {
        const job = await api.getSimulationJob(jobId);
        if (!job) {
          localStorage.removeItem(LOCAL_STORAGE_KEY);
          stopPolling();
          setStatus('IDLE');
          setActiveJobId(null);
          return;
        }

        setProgress(job.progress || 0);
        if (job.current_step) {
          setCurrentStep(`Evaluating transaction ${job.completed || 0} of ${job.total || count}...`);
        }
        if (job.results && job.results.length > 0) {
          setResults(job.results);
        }

        if (job.status === 'COMPLETED') {
          stopPolling();
          setStatus('COMPLETED');
          setResults(job.results || []);
          if (job.summary) setSummary(job.summary);
        } else if (job.status === 'FAILED') {
          stopPolling();
          setStatus('FAILED');
          setError(job.error || 'Simulation failed in inference pipeline');
        } else {
          setStatus('RUNNING');
        }
      } catch (err: any) {
        if (err.message && err.message.includes('404')) {
          localStorage.removeItem(LOCAL_STORAGE_KEY);
          stopPolling();
          setStatus('IDLE');
          setActiveJobId(null);
        } else {
          setError('Unable to refresh simulation status. Retrying...');
        }
      }
    };

    await checkJob();
    pollRef.current = setInterval(checkJob, 600);
  };

  useEffect(() => {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (raw) {
      try {
        const persisted: PersistedJob = JSON.parse(raw);
        if (persisted.job_id) {
          if (persisted.scenario) setSelectedType(persisted.scenario);
          if (persisted.total) setCount(persisted.total);
          reattachToJob(persisted.job_id);
        }
      } catch {
        localStorage.removeItem(LOCAL_STORAGE_KEY);
      }
    }

    return () => {
      stopPolling();
    };
  }, []);

  const run = async () => {
    if (status === 'RUNNING' || status === 'QUEUED') {
      return;
    }

    stopPolling();
    setStatus('QUEUED');
    setError(null);
    setProgress(0);
    setCurrentStep('Queuing simulation job...');
    setResults([]);
    setSummary(null);

    try {
      const res = await api.startSimulation(selectedType, count);
      const jobId = res.job_id;

      if (!jobId) {
        throw new Error('Simulation job could not be queued');
      }

      const jobData: PersistedJob = {
        job_id: jobId,
        scenario: selectedType,
        total: count,
        started_at: new Date().toISOString(),
      };
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(jobData));
      reattachToJob(jobId);
    } catch (err: any) {
      setStatus('FAILED');
      setError(err.message || 'Simulation start failed');
    }
  };

  const reset = () => {
    stopPolling();
    localStorage.removeItem(LOCAL_STORAGE_KEY);
    setStatus('IDLE');
    setActiveJobId(null);
    setResults([]);
    setSummary(null);
    setError(null);
    setProgress(0);
    setCurrentStep('');
  };

  const handleDownload = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify({ scenario: selectedType, summary, transactions: results }, null, 2)
      );
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `simulation-${selectedType}-${count}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const isRunning = status === 'RUNNING' || status === 'QUEUED';

  return (
    <div className="space-y-6">
      
      <div>
        <h1 className="text-2xl font-bold text-white">Simulation Lab</h1>
        <p className="text-sm text-neutral-400 mt-1">
          Generate synthetic transaction scenarios through the production ML models, anomaly detection, AML rules, and verifier
        </p>
      </div>

      
      {isRunning && (
        <div className="rounded-xl border border-yellow-500/40 bg-yellow-500/10 p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <Loader2 className="h-4 w-4 text-yellow-400 animate-spin" />
              <span className="text-sm font-bold text-white">
                Active Simulation in Progress: <span className="uppercase text-yellow-400 font-mono">{selectedType}</span>
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-neutral-400">
                Job ID: {activeJobId}
              </span>
              <span className="px-2 py-0.5 rounded font-mono text-xs font-bold bg-yellow-400 text-black">
                {progress}%
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-neutral-300">
            <span className="font-mono">{currentStep || 'Evaluating risk pipeline...'}</span>
            <span className="font-bold text-white">
              {results.length} / {count} evaluated
            </span>
          </div>

          <div className="h-2 w-full bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-yellow-400 transition-all duration-300 rounded-full"
              style={{ width: `${Math.max(4, progress)}%` }}
            />
          </div>
        </div>
      )}

      
      {status === 'COMPLETED' && (
        <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="h-4 w-4 text-green-400" />
            <span className="text-sm font-semibold text-white">
              Simulation Completed ({count} / {count} transactions analyzed)
            </span>
          </div>
          {activeJobId && (
            <span className="font-mono text-xs text-neutral-400">Job: {activeJobId}</span>
          )}
        </div>
      )}

      
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
                onClick={() => !isRunning && setSelectedType(type)}
                disabled={isRunning}
                className={`rounded-lg border p-3 text-left transition-all ${
                  active
                    ? colorClass
                    : 'border-neutral-800 bg-neutral-900/40 hover:border-neutral-700'
                } ${isRunning ? 'opacity-60 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-bold ${active ? 'text-white' : 'text-neutral-300'}`}>
                    {preset.label}
                  </span>
                  <span
                    className={`h-2 w-2 rounded-full ${
                      preset.color === 'green'
                        ? 'bg-green-500'
                        : preset.color === 'yellow'
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                    }`}
                  />
                </div>
                <p className="text-[10px] text-neutral-500">{preset.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      
      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <div className="flex items-center gap-3">
            <label className="text-xs text-neutral-400">Transactions:</label>
            <input
              type="range"
              min="5"
              max="100"
              value={count}
              disabled={isRunning}
              onChange={(e) => setCount(Number(e.target.value))}
              className="w-32 accent-white disabled:opacity-50"
            />
            <span className="text-sm font-bold text-white tabular-nums w-8">{count}</span>
          </div>
          <div className="flex gap-2 ml-auto">
            <button
              onClick={run}
              disabled={isRunning}
              className="px-4 py-2 rounded-lg bg-white text-black text-sm font-bold hover:bg-neutral-200 disabled:opacity-40 transition-colors flex items-center gap-2"
            >
              {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {isRunning ? 'Simulation Running...' : 'Run Simulation'}
            </button>
            {(results.length > 0 || status === 'COMPLETED' || isRunning) && (
              <>
                <button
                  onClick={reset}
                  className="px-4 py-2 rounded-lg border border-neutral-800 text-neutral-400 text-sm font-bold hover:text-white hover:border-neutral-600 transition-colors flex items-center gap-2"
                >
                  <RotateCcw className="h-4 w-4" />
                  Reset
                </button>
                {results.length > 0 && (
                  <button
                    onClick={handleDownload}
                    className="px-3 py-2 rounded-lg border border-neutral-800 text-neutral-400 text-sm font-bold hover:text-white hover:border-neutral-600 transition-colors"
                    title="Download JSON results"
                  >
                    <Download className="h-4 w-4" />
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-red-600/30 bg-red-600/10 text-red-400 text-sm flex items-center gap-2">
          <XCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}

      
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
            <div className="flex items-center gap-2 text-neutral-400 text-xs mb-1">
              <Activity className="h-3.5 w-3.5" />
              <span>Total Evaluated</span>
            </div>
            <p className="text-xl font-bold text-white">{summary.total_evaluated}</p>
          </div>
          <div className="rounded-xl border border-red-900/30 bg-red-950/20 p-4">
            <div className="flex items-center gap-2 text-red-400 text-xs mb-1">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>High Risk / Critical</span>
            </div>
            <p className="text-xl font-bold text-red-400">{summary.high_risk_count}</p>
          </div>
          <div className="rounded-xl border border-yellow-900/30 bg-yellow-950/20 p-4">
            <div className="flex items-center gap-2 text-yellow-400 text-xs mb-1">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>Medium Risk</span>
            </div>
            <p className="text-xl font-bold text-yellow-400">{summary.medium_risk_count}</p>
          </div>
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
            <div className="flex items-center gap-2 text-neutral-400 text-xs mb-1">
              <Zap className="h-3.5 w-3.5" />
              <span>Avg Risk Score</span>
            </div>
            <p className="text-xl font-bold text-white">
              {((summary.average_risk_score ?? 0) * 100).toFixed(1)}%
            </p>
          </div>
        </div>
      )}

      
      {results.length > 0 && (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 overflow-hidden">
          <div className="p-4 border-b border-neutral-800 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">
              Evaluated Transactions ({results.length})
            </h3>
            <span className="text-xs text-neutral-500 font-mono">
              Production ML & Rules Pipeline
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-neutral-950 text-neutral-400 uppercase text-[10px] tracking-wider border-b border-neutral-800">
                <tr>
                  <th className="px-4 py-3 text-left">TX ID</th>
                  <th className="px-4 py-3 text-left">Sender</th>
                  <th className="px-4 py-3 text-left">Receiver</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3 text-center">Type</th>
                  <th className="px-4 py-3 text-center">Risk</th>
                  <th className="px-4 py-3 text-center">Fraud Prob</th>
                  <th className="px-4 py-3 text-center">Anomaly</th>
                  <th className="px-4 py-3 text-left">Signals</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/60 font-mono">
                {results.map((tx) => (
                  <tr key={tx.id || tx.transaction_id} className="hover:bg-neutral-800/30 transition-colors">
                    <td className="px-4 py-2.5 font-bold text-neutral-300">
                      {tx.id || tx.transaction_id}
                    </td>
                    <td className="px-4 py-2.5 text-neutral-400">{tx.sender_id}</td>
                    <td className="px-4 py-2.5 text-neutral-400">{tx.receiver_id}</td>
                    <td className="px-4 py-2.5 text-right font-bold text-white">
                      {formatCurrency(tx.amount, tx.currency)}
                    </td>
                    <td className="px-4 py-2.5 text-center text-neutral-400">{tx.transaction_type}</td>
                    <td className="px-4 py-2.5 text-center">
                      <RiskBadge level={tx.risk_level || 'LOW'} />
                    </td>
                    <td className="px-4 py-2.5 text-center text-neutral-300">
                      {tx.fraud_probability !== undefined ? (tx.fraud_probability * 100).toFixed(1) + '%' : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-center text-neutral-300">
                      {tx.anomaly_score !== undefined ? (tx.anomaly_score * 100).toFixed(1) + '%' : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-left font-sans">
                      {tx.signals && tx.signals.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {tx.signals.slice(0, 2).map((sig: string) => (
                            <span key={sig} className="px-1.5 py-0.5 rounded text-[10px] bg-neutral-800 text-neutral-300">
                              {sig}
                            </span>
                          ))}
                          {tx.signals.length > 2 && (
                            <span className="text-[10px] text-neutral-500">+{tx.signals.length - 2}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-neutral-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
