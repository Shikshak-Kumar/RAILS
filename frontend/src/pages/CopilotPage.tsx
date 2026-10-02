import { useState, useRef, useEffect } from 'react';
import { Send, ShieldCheck, AlertCircle, FileText, Zap, Loader2 } from 'lucide-react';
import type { ChatMessage, ToolCall } from '@/types';
import { api } from '@/lib/api';
import { formatCurrency, timeAgo } from '@/lib/utils';
import { RiskBadge } from '@/components/RiskBadge';

const quickPrompts = [
  'Show me the highest-risk transactions from the last 24 hours',
  'What is the risk profile of account HDFC-482910?',
  'Are there any fan-out patterns in recent transactions?',
  'What regulatory requirements apply to this case?',
  'Generate an STR draft for case CASE-2026-0018',
];

const toolNames = [
  'get_transaction', 'get_account_transactions', 'get_transaction_risk', 'get_account_risk',
  'get_fraud_signals', 'get_anomaly_signals', 'get_graph_signals', 'get_liquidity_risk',
  'get_credit_risk', 'search_regulation', 'search_policy', 'create_case', 'get_case',
  'generate_str_draft', 'generate_regulatory_report', 'get_evidence', 'simulate_transactions',
];

export function CopilotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

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
      setMessages((m) => [...m, {
        ...response,
        id: response.id || `msg-${Date.now()}`,
        timestamp: response.timestamp || new Date().toISOString(),
        role: 'assistant'
      }]);
    } catch (err: any) {
      setMessages((m) => [...m, {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `Error connecting to copilot: ${err.message}`,
        timestamp: new Date().toISOString()
      } as ChatMessage]);
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
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isThinking && (
          <div className="flex items-center gap-3 text-neutral-500">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white">
              <Loader2 className="h-4 w-4 text-black animate-spin" />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm">Analyzing with ML models</span>
              <span className="flex gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-neutral-600 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="h-1.5 w-1.5 rounded-full bg-neutral-600 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="h-1.5 w-1.5 rounded-full bg-neutral-600 animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
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
              className="px-3 py-1.5 rounded-lg border border-neutral-800 bg-neutral-900/50 text-xs text-neutral-400 hover:text-white hover:border-neutral-600 transition-colors"
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
        <span className="text-[10px] text-neutral-600">Available tools:</span>
        {toolNames.slice(0, 8).map((t) => (
          <span key={t} className="text-[10px] font-mono text-neutral-600">{t}</span>
        ))}
        <span className="text-[10px] text-neutral-700">+{toolNames.length - 8} more</span>
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
          <p className="text-sm text-neutral-200 whitespace-pre-wrap">{message.content}</p>

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


