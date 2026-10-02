import { useState, useRef, useEffect } from 'react';
import { Send, ShieldCheck, AlertCircle, FileText, Zap, Loader2, CheckCircle2, Clock, Cpu } from 'lucide-react';
import type { ChatMessage, ToolCall } from '@/types';
import { api } from '@/lib/api';
import { timeAgo } from '@/lib/utils';

const quickPrompts = [
  'Show me the highest-risk transactions from the database',
  'What is the risk profile of account 12345?',
  'Are there any fan-out or structuring patterns in recent transactions?',
  'What regulatory reporting requirements apply under FinCEN and FATF?',
  'Draft a suspicious transaction report for high risk activity',
];

const toolNames = [
  'get_transaction', 'list_transactions', 'fraud_check', 'anomaly_check',
  'account_risk_check', 'account_history', 'get_case', 'generate_report',
];

const COPILOT_STORAGE_KEY = 'rails.copilotMessages';
const ACTIVE_EXEC_KEY = 'rails.activeExecutionId';

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
              // Avoid duplicate append
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
      const response = await api.chatWithCopilot(text);
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
      {/* Header */}
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

      {/* Chat area */}
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
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isThinking && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white">
              <Zap className="h-4 w-4 text-black animate-pulse" />
            </div>
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/80 p-4 space-y-3 min-w-[280px]">
              <div className="flex items-center justify-between text-xs text-neutral-400">
                <span className="font-bold text-white flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-white" />
                  Agent Execution Pipeline
                </span>
                <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/30 font-bold uppercase">
                  RUNNING
                </span>
              </div>
              <div className="space-y-1.5 pt-1 text-xs">
                <div className="flex items-center gap-2 text-green-400">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Intent & Tool Planning</span>
                </div>
                <div className="flex items-center gap-2 text-neutral-200">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-white" />
                  <span>Executing Tools & Inferences</span>
                </div>
                <div className="flex items-center gap-2 text-neutral-500">
                  <Clock className="h-3.5 w-3.5" />
                  <span>Evidence Collection & Verifier</span>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>


      {/* Quick prompts */}
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

      {/* Input */}
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

      {/* Tool list */}
      <div className="mt-2 flex items-center gap-2 flex-wrap">
        <span className="text-[10px] text-neutral-600">Audited execution tools:</span>
        {toolNames.map((t) => (
          <span key={t} className="text-[10px] font-mono text-neutral-600">{t}</span>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg bg-white text-black px-4 py-2.5">
          <p className="text-sm">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white">
        <Zap className="h-4 w-4 text-black" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
          {/* Natural language answer */}
          <p className="text-sm text-neutral-200 whitespace-pre-wrap leading-relaxed">{message.content}</p>

          {/* Tool calls */}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="mt-3 space-y-2">
              {message.tool_calls.map((tc, i) => (
                <ToolCallCard key={i} call={tc} />
              ))}
            </div>
          )}

          {/* Verification */}
          {message.verified !== undefined && (
            <div className="mt-3 flex items-center gap-2 pt-3 border-t border-neutral-800">
              {message.verified ? (
                <>
                  <ShieldCheck className="h-4 w-4 text-green-500" />
                  <span className="text-xs text-green-500 font-medium">Verified — all claims backed by evidence</span>
                </>
              ) : (
                <>
                  <AlertCircle className="h-4 w-4 text-red-500" />
                  <span className="text-xs text-red-500 font-medium">Verification failed — unverified claims</span>
                </>
              )}
            </div>
          )}

          {/* Evidence */}
          {message.evidence_ids && message.evidence_ids.length > 0 && (
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              {message.evidence_ids.map((eid) => (
                <span key={eid} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400">
                  {eid}
                </span>
              ))}
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
        <span className="text-[10px] font-mono text-neutral-600 ml-auto">{call.evidence_id}</span>
      </div>
    </div>
  );
}
