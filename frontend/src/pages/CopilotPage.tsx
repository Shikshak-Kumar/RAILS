import { useState, useRef, useEffect } from 'react';
import { Send, ShieldCheck, AlertCircle, FileText, Zap, Loader2, CheckCircle2, Clock, Cpu, BookOpen, Scale, X, ExternalLink } from 'lucide-react';
import type { ChatMessage, ToolCall, RegulatoryCitation } from '@/types';
import { api } from '@/lib/api';
import { timeAgo } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';


const remarkPlugin = (remarkGfm as any)?.default ?? remarkGfm;

const quickPrompts = [
  'Why was transaction 2928645 flagged and what regulatory guidance is relevant?',
  'What regulatory guidance is relevant to transaction 2928645?',
  'Why was transaction 2928645 flagged?',
  'Show me the highest-risk transactions from the database',
  'What is the risk profile of account 12345?',
  'What regulatory reporting requirements apply under FinCEN and FATF?',
];

const toolNames = [
  'get_transaction', 'list_transactions', 'fraud_check', 'anomaly_check',
  'account_risk_check', 'account_history', 'get_case', 'generate_report',
  'regulatory_search',
];

const COPILOT_STORAGE_KEY = 'rails.copilotMessages';
const ACTIVE_EXEC_KEY = 'rails.activeExecutionId';
const CONVERSATION_ID_KEY = 'rails.copilotConversationId';

export function CopilotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const raw = localStorage.getItem(COPILOT_STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem(COPILOT_STORAGE_KEY, JSON.stringify(messages));
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  useEffect(() => {
    const activeExecId = localStorage.getItem(ACTIVE_EXEC_KEY);
    if (!activeExecId) return;

    setIsThinking(true);
    const pollInterval = setInterval(async () => {
      try {
        const exec = await api.getExecution(activeExecId);
        if (exec.status === 'COMPLETED' || exec.status === 'FAILED') {
          clearInterval(pollInterval);
          localStorage.removeItem(ACTIVE_EXEC_KEY);
          setIsThinking(false);

          if (exec.final_answer) {
            setMessages((prev) => {
              
              if (prev.some((m) => m.content === exec.final_answer)) return prev;
              return [
                ...prev,
                {
                  id: `msg-${Date.now()}`,
                  role: 'assistant',
                  content: exec.final_answer,
                  timestamp: exec.completed_at || new Date().toISOString(),
                  verified: exec.status === 'COMPLETED',
                  tool_calls: (exec.steps || []).filter((s: any) => s.step_type === 'tool').map((s: any) => ({
                    tool_name: s.name,
                    arguments: s.arguments,
                    result_summary: s.result_summary,
                    evidence_id: s.evidence_id || '',
                  })),
                },
              ];
            });
          }
        }
      } catch {
        clearInterval(pollInterval);
        localStorage.removeItem(ACTIVE_EXEC_KEY);
        setIsThinking(false);
      }
    }, 800);

    return () => clearInterval(pollInterval);
  }, []);

  const send = async (text: string) => {
    if (!text.trim() || isThinking) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setIsThinking(true);

    try {
      let convId = localStorage.getItem(CONVERSATION_ID_KEY);
      if (!convId) {
        convId = `conv-${Date.now()}`;
        localStorage.setItem(CONVERSATION_ID_KEY, convId);
      }
      const response = await api.chatWithCopilot(text, undefined, undefined, undefined, convId);
      if (response.conversation_id) {
        localStorage.setItem(CONVERSATION_ID_KEY, response.conversation_id);
      }
      if (response.execution_id) {
        localStorage.setItem(ACTIVE_EXEC_KEY, response.execution_id);
      }

      setMessages((m) => [
        ...m,
        {
          ...response,
          id: response.id || `msg-${Date.now()}`,
          content: response.content || response.answer || 'Response generated from tools.',
          timestamp: response.timestamp || new Date().toISOString(),
          role: 'assistant',
          tool_calls: response.tool_calls || [],
          evidence_ids: response.evidence_ids || [],
          verified: response.verified !== undefined ? response.verified : true,
          regulatory_citations: response.regulatory_citations || [],
          regulatory_citation_ids: response.regulatory_citation_ids || [],
          investigation: response.investigation || null,
          transactions: response.transactions || [],
        },
      ]);
      localStorage.removeItem(ACTIVE_EXEC_KEY);
    } catch (err: any) {
      localStorage.removeItem(ACTIVE_EXEC_KEY);
      setMessages((m) => [
        ...m,
        {
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: `Unable to complete Copilot query: ${err.message}`,
          timestamp: new Date().toISOString(),
          verified: false,
        },
      ]);
    } finally {
      setIsThinking(false);
    }
  };


  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      
      <div className="mb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white">
            <Zap className="h-5 w-5 text-black" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Risk Copilot</h1>
            <p className="text-xs text-neutral-400">ML-backed natural language queries with evidence & verification</p>
          </div>
        </div>
      </div>

      
      <div className="flex-1 overflow-y-auto rounded-xl border border-neutral-800 bg-neutral-900/30 p-4 space-y-4">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center p-8">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white text-black mb-3">
              <Zap className="h-6 w-6" />
            </div>
            <h2 className="text-base font-semibold text-white">Risk, Fraud & AML Copilot</h2>
            <p className="text-xs text-neutral-400 max-w-md mt-1 mb-6">
              Ask about transaction risks, inspect account histories, analyze anomalies, or generate verified STR drafts. All claims are grounded in tool execution and logged evidence.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onSelectChunk={setSelectedChunkId}
            onSelectTransaction={(tid) => send(`Investigate transaction ${tid}`)}
          />
        ))}

        {isThinking && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white">
              <Zap className="h-4 w-4 text-black animate-pulse" />
            </div>
            <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 px-4 py-3 flex items-center gap-2.5">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-white" />
              <span className="text-xs text-neutral-300">Risk Analysis Copilot is analyzing verified records...</span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>


      
      {messages.length <= 2 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {quickPrompts.map((p) => (
            <button
              key={p}
              onClick={() => send(p)}
              disabled={isThinking}
              className="px-3 py-1.5 rounded-lg border border-neutral-800 bg-neutral-900/50 text-xs text-neutral-400 hover:text-white hover:border-neutral-600 disabled:opacity-50 transition-colors text-left"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      
      <div className="mt-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send(input)}
          placeholder="Ask about transactions, risks, regulations, or generate reports..."
          className="flex-1 px-4 py-3 rounded-lg bg-neutral-900 border border-neutral-800 text-sm text-neutral-100 placeholder-neutral-600 focus:outline-none focus:border-neutral-600 transition-colors"
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim() || isThinking}
          className="px-4 py-3 rounded-lg bg-white text-black font-bold hover:bg-neutral-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>

      
      <div className="mt-2 flex items-center gap-2 flex-wrap">
        <span className="text-[10px] text-neutral-600">Audited execution tools:</span>
        {toolNames.map((t) => (
          <span key={t} className="text-[10px] font-mono text-neutral-600">{t}</span>
        ))}
      </div>

      
      {selectedChunkId && (
        <RegulatoryChunkModal
          chunkId={selectedChunkId}
          onClose={() => setSelectedChunkId(null)}
        />
      )}
    </div>
  );
}

function MessageBubble({
  message,
  onSelectChunk,
  onSelectTransaction,
}: {
  message: ChatMessage;
  onSelectChunk?: (chunkId: string) => void;
  onSelectTransaction?: (txId: string) => void;
}) {
  const isUser = message.role === 'user';
  const [showDetails, setShowDetails] = useState(false);

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg bg-white text-black px-4 py-2.5">
          <p className="text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  const hasTools = message.tool_calls && message.tool_calls.length > 0;
  const citations = message.regulatory_citations || [];
  const citationIds = message.regulatory_citation_ids || [];
  const hasCitations = citations.length > 0 || citationIds.length > 0;
  const hasTransactions = message.transactions && message.transactions.length > 0;

  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white">
        <Zap className="h-4 w-4 text-black" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
          
          <div className="text-sm text-neutral-200 leading-relaxed [&>ul]:list-disc [&>ul]:pl-5 [&>ol]:list-decimal [&>ol]:pl-5 [&>h1]:text-base [&>h1]:font-semibold [&>h2]:text-sm [&>h2]:font-semibold [&>h3]:text-sm [&>h3]:font-medium [&>p]:mb-2 [&>ul]:mb-2 [&>ol]:mb-2 [&>code]:bg-neutral-800 [&>code]:px-1 [&>code]:rounded [&>pre]:bg-neutral-800 [&>pre]:p-2 [&>pre]:rounded [&>table]:w-full [&>table]:border-collapse [&>table]:my-3 [&>table_th]:border [&>table_th]:border-neutral-700 [&>table_th]:p-2 [&>table_th]:bg-neutral-800/80 [&>table_th]:text-left [&>table_th]:text-xs [&>table_td]:border [&>table_td]:border-neutral-800 [&>table_td]:p-2 [&>table_td]:text-xs">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {typeof message.content === "string"
                ? message.content
                : String(message.content ?? "")}
            </ReactMarkdown>
          </div>

          
          {hasTransactions && (
            <div className="mt-4 pt-3 border-t border-neutral-800">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-xs font-semibold text-neutral-200">
                  Retrieved Transactions ({message.transactions!.length})
                </span>
                <span className="text-[10px] text-neutral-500">
                  Click any transaction to investigate
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {message.transactions!.map((tx: any, idx: number) => {
                  const tid = String(tx.transaction_id || tx.id || 'N/A');
                  const risk = String(tx.risk_level || tx.risk_assessment?.risk_level || 'LOW');
                  const amt = Number(tx.amount || 0);
                  const fprob = Number(tx.fraud_probability !== undefined ? tx.fraud_probability : (tx.risk_assessment?.fraud_probability || 0));
                  const anom = Number(tx.anomaly_score !== undefined ? tx.anomaly_score : (tx.risk_assessment?.anomaly_score || 0));
                  const sigs = tx.signals || tx.risk_assessment?.signals || [];
                  return (
                    <div
                      key={idx}
                      onClick={() => onSelectTransaction?.(tid)}
                      className="p-3 rounded-lg border border-neutral-800 bg-neutral-950/70 hover:border-neutral-500 hover:bg-neutral-900 cursor-pointer transition-all flex flex-col justify-between gap-1.5 group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-white group-hover:underline">
                          TX #{tid}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            risk === 'CRITICAL'
                              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                              : risk === 'HIGH'
                              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                              : risk === 'MEDIUM'
                              ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                              : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          }`}
                        >
                          {risk}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] text-neutral-400">
                        <div>
                          Amount: <span className="text-neutral-200 font-medium">${amt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        </div>
                        <div>
                          Fraud: <span className="text-neutral-200 font-medium">{fprob > 0 && fprob < 0.001 ? (fprob * 100).toFixed(3) : (fprob * 100).toFixed(1)}%</span>
                        </div>
                        {anom > 0 && (
                          <div>
                            Anomaly: <span className="text-neutral-200 font-medium">{(anom * 100).toFixed(1)}%</span>
                          </div>
                        )}
                        {sigs.length > 0 && (
                          <div className="col-span-2 text-[10px] text-neutral-500 truncate">
                            Signal: {sigs.join(', ')}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          
          {hasCitations && (
            <div className="mt-4 pt-3 border-t border-neutral-800">
              <div className="flex items-center gap-2 mb-2">
                <BookOpen className="h-4 w-4 text-sky-400" />
                <span className="text-xs font-semibold text-neutral-200">Authoritative Regulatory Guidance</span>
                <span className="text-[10px] text-neutral-500">(Click citation to inspect verified source passage)</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {citations.length > 0
                  ? citations.map((c) => (
                      <button
                        key={c.chunk_id}
                        type="button"
                        onClick={() => onSelectChunk?.(c.chunk_id)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-950/40 border border-sky-800/60 text-xs text-sky-200 hover:bg-sky-900/60 hover:border-sky-500 hover:text-white transition-all cursor-pointer text-left shadow-sm group"
                        title={`Inspect ${c.document_name} (${c.authority})`}
                      >
                        <Scale className="h-3.5 w-3.5 text-sky-400 group-hover:scale-110 transition-transform shrink-0" />
                        <span className="font-mono text-[11px] font-bold text-sky-300">{c.chunk_id}</span>
                        <span className="text-[10px] text-neutral-400 font-sans">
                          {c.authority} • {c.jurisdiction} (p.{c.page_number})
                        </span>
                        <ExternalLink className="h-3 w-3 text-sky-400/70 ml-0.5" />
                      </button>
                    ))
                  : citationIds.map((cid) => (
                      <button
                        key={cid}
                        type="button"
                        onClick={() => onSelectChunk?.(cid)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-950/40 border border-sky-800/60 text-xs text-sky-200 hover:bg-sky-900/60 hover:border-sky-500 hover:text-white transition-all cursor-pointer text-left shadow-sm group"
                      >
                        <Scale className="h-3.5 w-3.5 text-sky-400 group-hover:scale-110 transition-transform shrink-0" />
                        <span className="font-mono text-[11px] font-bold text-sky-300">{cid}</span>
                        <ExternalLink className="h-3 w-3 text-sky-400/70 ml-0.5" />
                      </button>
                    ))}
              </div>
            </div>
          )}

          
          {hasTools && (
            <div className="mt-4 pt-3 border-t border-neutral-800">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  {message.verified !== false ? (
                    <>
                      <ShieldCheck className="h-4 w-4 text-green-500" />
                      <span className="text-xs text-green-400 font-medium">Verified ✓</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="h-4 w-4 text-red-500" />
                      <span className="text-xs text-red-400 font-medium">Unverified ⚠</span>
                    </>
                  )}
                  <span className="text-xs text-neutral-500">•</span>
                  <span className="text-xs text-neutral-400">
                    {message.tool_calls!.length} backend {message.tool_calls!.length === 1 ? 'tool' : 'tools'} executed
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowDetails(!showDetails)}
                  className="text-xs font-mono text-neutral-400 hover:text-white underline decoration-neutral-700 underline-offset-4 transition-colors"
                >
                  {showDetails ? '[Hide execution details]' : '[View execution details]'}
                </button>
              </div>

              {showDetails && (
                <div className="mt-3 space-y-2 pt-2 border-t border-neutral-800/60">
                  {message.tool_calls!.map((tc, i) => (
                    <ToolCallCard key={i} call={tc} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        <span className="text-[10px] text-neutral-600 mt-1 ml-1">{timeAgo(message.timestamp)}</span>
      </div>
    </div>
  );
}

function ToolCallCard({ call }: { call: ToolCall }) {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950/60 p-2.5">
      <div className="flex items-center gap-2">
        <FileText className="h-3 w-3 text-neutral-500" />
        <span className="text-xs font-mono font-bold text-neutral-300">{call.tool_name}</span>
        <span className="text-[10px] text-neutral-600">→</span>
        <span className="text-xs text-neutral-400">{call.result_summary}</span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className="text-[10px] text-neutral-600">args:</span>
        <code className="text-[10px] font-mono text-neutral-500 truncate">
          {JSON.stringify(call.arguments)}
        </code>
      </div>
    </div>
  );
}

function RegulatoryChunkModal({
  chunkId,
  onClose,
}: {
  chunkId: string;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chunkData, setChunkData] = useState<any>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    api
      .getRegulatoryChunk(chunkId)
      .then((data) => {
        if (!cancelled) {
          setChunkData(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.message || 'Failed to load regulatory chunk');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [chunkId]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-xl border border-neutral-700 bg-neutral-900 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        
        <div className="flex items-center justify-between border-b border-neutral-800 px-5 py-4 bg-neutral-950/70">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-950 border border-sky-800 text-sky-400">
              <Scale className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <span>Regulatory Authority Passage</span>
                <span className="font-mono text-xs font-normal text-sky-400 bg-sky-950/60 px-2 py-0.5 rounded border border-sky-800/60">
                  {chunkId}
                </span>
              </h2>
              <p className="text-[11px] text-neutral-400">Authoritative grounded compliance source chunk</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading && (
            <div className="flex flex-col items-center justify-center py-12 text-neutral-400 gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-sky-400" />
              <span className="text-xs">Fetching verified regulatory chunk...</span>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-800 bg-red-950/40 p-4 text-xs text-red-300">
              <p className="font-semibold mb-1">Error Loading Regulatory Chunk</p>
              <p>{error}</p>
            </div>
          )}

          {chunkData && (
            <>
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-2.5">
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wider block">Document</span>
                  <span className="text-xs font-medium text-neutral-200 truncate block mt-0.5" title={chunkData.document_name}>
                    {chunkData.document_name || chunkData.document_id}
                  </span>
                </div>
                <div className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-2.5">
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wider block">Authority</span>
                  <span className="text-xs font-semibold text-sky-300 block mt-0.5">
                    {chunkData.authority}
                  </span>
                </div>
                <div className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-2.5">
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wider block">Jurisdiction</span>
                  <span className="text-xs font-semibold text-neutral-200 block mt-0.5">
                    {chunkData.jurisdiction}
                  </span>
                </div>
                <div className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-2.5">
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wider block">Location</span>
                  <span className="text-xs font-mono text-neutral-300 block mt-0.5">
                    Page {chunkData.page_number}
                  </span>
                </div>
              </div>

              {chunkData.section && (
                <div className="rounded-lg border border-neutral-800 bg-neutral-950/30 px-3 py-2 text-xs">
                  <span className="text-[10px] text-neutral-500 uppercase tracking-wider block">Section</span>
                  <span className="text-xs text-neutral-200 font-medium">{chunkData.section}</span>
                </div>
              )}

              
              <div>
                <span className="text-xs font-semibold text-neutral-300 block mb-1.5">
                  Authoritative Source Passage:
                </span>
                <div className="rounded-lg border border-neutral-800 bg-neutral-950 p-4 font-mono text-xs text-neutral-200 leading-relaxed whitespace-pre-wrap selection:bg-sky-800 max-h-80 overflow-y-auto">
                  {chunkData.chunk_text}
                </div>
              </div>
            </>
          )}
        </div>

        
        <div className="flex items-center justify-between border-t border-neutral-800 px-5 py-3 bg-neutral-950/70">
          <div className="flex items-center gap-1.5 text-[11px] text-neutral-400">
            <ShieldCheck className="h-3.5 w-3.5 text-green-500" />
            <span>Verified in regulatory intelligence corpus</span>
          </div>
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-xs font-medium text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
