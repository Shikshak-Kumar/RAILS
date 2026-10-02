import { useState, useEffect } from 'react';
import {
  Cpu,
  CheckCircle2,
  Clock,
  ArrowDown,
  Layers,
  ShieldCheck,
  AlertCircle,
  RefreshCw,
  Terminal,
  FileCode,
  Zap,
} from 'lucide-react';
import { api } from '@/lib/api';
import { timeAgo } from '@/lib/utils';

interface Step {
  step_id: string;
  name: string;
  step_type: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  started_at: string;
  completed_at?: string;
  duration_ms: number;
  arguments: Record<string, any>;
  result_summary: string;
  evidence_id?: string;
  error?: string;
}

interface Execution {
  execution_id: string;
  name: string;
  status: 'RUNNING' | 'COMPLETED' | 'FAILED';
  started_at: string;
  input_query: string;
  completed_at?: string;
  duration_ms: number;
  steps: Step[];
  final_answer?: string;
  error?: string;
}

export function AutomationPage() {
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  const fetchExecutions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getExecutions(30);
      const items: Execution[] = Array.isArray(data) ? data : data.items || [];
      setExecutions(items);
      const activeExec = localStorage.getItem('rails.activeExecutionId');
      if (activeExec && items.some((e) => e.execution_id === activeExec)) {
        setSelectedId(activeExec);
      } else if (items.length > 0 && !selectedId) {
        setSelectedId(items[0].execution_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load execution traces');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExecutions();
    const interval = setInterval(fetchExecutions, 2500);
    return () => clearInterval(interval);
  }, [selectedId]);


  const selectedExecution = executions.find((e) => e.execution_id === selectedId) || executions[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Cpu className="h-6 w-6 text-white" />
            Automation & Agent Execution
          </h1>
          <p className="text-sm text-neutral-400 mt-1">
            Real-time auditable workflow traces across tool calls, ML model inferences, and cryptographic evidence verification
          </p>
        </div>
        <button
          onClick={fetchExecutions}
          className="px-3.5 py-1.5 rounded-lg border border-neutral-800 bg-neutral-900/60 text-neutral-300 text-xs font-semibold hover:border-neutral-700 hover:text-white transition-colors flex items-center gap-2 self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Traces
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-red-600/30 bg-red-600/10 text-red-400 text-sm flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Executions List Sidebar */}
        <div className="lg:col-span-4 space-y-3">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-xs font-bold uppercase tracking-wider text-neutral-400">Recent Executions</h2>
            <span className="text-[10px] text-neutral-500 font-mono">{executions.length} traces</span>
          </div>

          <div className="space-y-2 max-h-[750px] overflow-y-auto pr-1">
            {executions.length === 0 && !loading && (
              <div className="p-6 rounded-xl border border-neutral-800 bg-neutral-900/20 text-center text-xs text-neutral-500">
                No agent execution traces recorded yet. Ask a question in Risk Copilot to generate a trace.
              </div>
            )}

            {executions.map((exec) => {
              const active = exec.execution_id === selectedId;
              const isCompleted = exec.status === 'COMPLETED';
              const isFailed = exec.status === 'FAILED';

              return (
                <div
                  key={exec.execution_id}
                  onClick={() => setSelectedId(exec.execution_id)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                    active
                      ? 'border-neutral-500 bg-neutral-900/90 shadow-lg'
                      : 'border-neutral-800/80 bg-neutral-900/30 hover:border-neutral-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="font-mono text-[11px] font-bold text-white truncate">
                      {exec.execution_id}
                    </span>
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                        isCompleted
                          ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                          : isFailed
                          ? 'bg-red-500/10 text-red-400 border border-red-500/30'
                          : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30'
                      }`}
                    >
                      {exec.status}
                    </span>
                  </div>

                  <p className="text-xs text-neutral-300 font-medium truncate mb-2">
                    {exec.input_query || exec.name}
                  </p>

                  <div className="flex items-center justify-between text-[10px] text-neutral-500">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {exec.duration_ms ? `${exec.duration_ms} ms` : 'In progress'}
                    </span>
                    <span>{timeAgo(exec.started_at)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Execution Visual Workflow DAG */}
        <div className="lg:col-span-8 space-y-4">
          {selectedExecution ? (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-6 space-y-6">
              {/* Trace Metadata Overview */}
              <div className="border-b border-neutral-800 pb-5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <span className="font-mono text-xs text-neutral-500">EXECUTION WORKFLOW</span>
                    <h2 className="text-base font-bold text-white mt-0.5 flex items-center gap-2">
                      {selectedExecution.name}
                    </h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono px-2 py-1 rounded bg-neutral-800 text-neutral-300">
                      ID: {selectedExecution.execution_id}
                    </span>
                    <span
                      className={`text-xs px-2.5 py-1 rounded-md font-bold uppercase ${
                        selectedExecution.status === 'COMPLETED'
                          ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                          : selectedExecution.status === 'FAILED'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                          : 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                      }`}
                    >
                      {selectedExecution.status}
                    </span>
                  </div>
                </div>

                {selectedExecution.input_query && (
                  <div className="p-3 rounded-lg bg-neutral-950 border border-neutral-800">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">User Prompt</span>
                    <p className="text-xs text-neutral-200 mt-1 font-mono">{selectedExecution.input_query}</p>
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-6 text-xs text-neutral-400 pt-1">
                  <span>Started: <strong className="text-neutral-200">{new Date(selectedExecution.started_at).toLocaleTimeString()}</strong></span>
                  <span>Duration: <strong className="text-white">{selectedExecution.duration_ms} ms</strong></span>
                  <span>Steps: <strong className="text-white">{selectedExecution.steps?.length || 0} nodes</strong></span>
                </div>
              </div>

              {/* Workflow Pipeline Timeline (n8n-style auditable trace) */}
              <div className="space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-400">
                  Execution Trace Graph
                </h3>

                <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-neutral-800">
                  {selectedExecution.steps?.map((step, idx) => {
                    const isExpanded = expandedStep === step.step_id;
                    const isCompleted = step.status === 'COMPLETED';
                    const isFailed = step.status === 'FAILED';

                    return (
                      <div key={step.step_id} className="relative">
                        {/* Dot indicator on vertical spine */}
                        <div
                          className={`absolute -left-6 top-3 h-3 w-3 rounded-full border-2 ${
                            isCompleted
                              ? 'bg-green-500 border-neutral-950'
                              : isFailed
                              ? 'bg-red-500 border-neutral-950'
                              : 'bg-yellow-500 border-neutral-950'
                          }`}
                        />

                        {/* Step Node Card */}
                        <div
                          onClick={() => setExpandedStep(isExpanded ? null : step.step_id)}
                          className={`rounded-xl border p-4 cursor-pointer transition-all ${
                            isExpanded
                              ? 'border-neutral-600 bg-neutral-950'
                              : 'border-neutral-800 bg-neutral-900/60 hover:border-neutral-700'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-3">
                              <div className="h-8 w-8 rounded-lg bg-neutral-800 flex items-center justify-center text-white">
                                {step.step_type === 'planner' ? (
                                  <Layers className="h-4 w-4 text-blue-400" />
                                ) : step.step_type === 'verifier' ? (
                                  <ShieldCheck className="h-4 w-4 text-green-400" />
                                ) : (
                                  <Zap className="h-4 w-4 text-amber-400" />
                                )}
                              </div>
                              <div>
                                <span className="font-mono text-xs font-bold text-white block">
                                  {step.name}
                                </span>
                                <span className="text-[10px] text-neutral-400">
                                  {step.step_type.toUpperCase()} NODE
                                </span>
                              </div>
                            </div>

                            <div className="flex items-center gap-3">
                              {step.evidence_id && (
                                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-neutral-800 text-neutral-300 border border-neutral-700">
                                  {step.evidence_id}
                                </span>
                              )}
                              <span className="font-mono text-xs text-neutral-400">
                                {step.duration_ms} ms
                              </span>
                              <span
                                className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                                  isCompleted
                                    ? 'bg-green-500/10 text-green-400'
                                    : isFailed
                                    ? 'bg-red-500/10 text-red-400'
                                    : 'bg-yellow-500/10 text-yellow-400'
                                }`}
                              >
                                {step.status}
                              </span>
                            </div>
                          </div>

                          {step.result_summary && (
                            <p className="mt-2.5 text-xs text-neutral-300 font-mono bg-neutral-900/80 p-2.5 rounded-lg border border-neutral-800/80">
                              {step.result_summary}
                            </p>
                          )}

                          {step.error && (
                            <p className="mt-2 text-xs text-red-400 font-mono bg-red-950/30 p-2 rounded border border-red-800/40">
                              Error: {step.error}
                            </p>
                          )}

                          {/* Expandable Arguments & Details */}
                          {isExpanded && step.arguments && Object.keys(step.arguments).length > 0 && (
                            <div className="mt-3 pt-3 border-t border-neutral-800 space-y-2">
                              <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">
                                Input Arguments
                              </span>
                              <pre className="text-[11px] font-mono text-neutral-300 bg-neutral-950 p-2.5 rounded-lg border border-neutral-800 overflow-x-auto">
                                {JSON.stringify(step.arguments, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Final Grounded Output */}
              {selectedExecution.final_answer && (
                <div className="pt-4 border-t border-neutral-800 space-y-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-neutral-400 flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-400" />
                    Final Verified Answer
                  </span>
                  <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-neutral-200 whitespace-pre-wrap font-sans leading-relaxed">
                    {selectedExecution.final_answer}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/30 p-12 text-center text-neutral-500 text-sm">
              Select an execution trace on the left to inspect its workflow nodes.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
