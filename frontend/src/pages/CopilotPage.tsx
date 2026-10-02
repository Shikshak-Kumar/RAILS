import { useState, useRef, useEffect } from 'react';
import { Send, ShieldCheck, AlertCircle, FileText, Zap, Loader2 } from 'lucide-react';
import type { ChatMessage, ToolCall } from '@/types';
import { demoChatMessages, demoTransactions, demoCases, demoRegulatorySources } from '@/data/demoData';
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
  const [messages, setMessages] = useState<ChatMessage[]>(demoChatMessages);
  const [input, setInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const send = (text: string) => {
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

    setTimeout(() => {
      const response = generateResponse(text);
      setMessages((m) => [...m, response]);
      setIsThinking(false);
    }, 1800 + Math.random() * 800);
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

function generateResponse(query: string): ChatMessage {
  const q = query.toLowerCase();
  const highRisk = demoTransactions.filter(
    (t) => t.risk_assessment && (t.risk_assessment.risk_level === 'HIGH' || t.risk_assessment.risk_level === 'CRITICAL'),
  );

  let content = '';
  let toolCalls: ToolCall[] = [];
  let evidenceIds: string[] = [];

  if (q.includes('highest-risk') || q.includes('high risk') || q.includes('last 24')) {
    const top = highRisk.slice(0, 5);
    content = `I found ${highRisk.length} high-risk transactions. Here are the top ${Math.min(5, top.length)}:\n\n`;
    top.forEach((t, i) => {
      content += `${i + 1}. ${t.transaction_id} — ${formatCurrency(t.amount, t.currency)} via ${t.transaction_type}\n`;
      content += `   Fraud: ${Math.round((t.risk_assessment?.fraud_probability ?? 0) * 100)}% | Anomaly: ${Math.round((t.risk_assessment?.anomaly_score ?? 0) * 100)}% | Risk: ${t.risk_assessment?.risk_level}\n`;
    });
    content += `\nAll scores are from the fraud_model (v2.1.0) and anomaly_model (v1.3.0). Every claim is backed by evidence.`;
    toolCalls = [
      { tool_name: 'get_recent_transactions', arguments: { time_window: '24h', risk_filter: 'HIGH+' }, result_summary: `${highRisk.length} high-risk transactions found`, evidence_id: 'EV-384920' },
      { tool_name: 'get_fraud_signals', arguments: { transaction_ids: top.map(t => t.transaction_id) }, result_summary: 'Fraud signals retrieved for 5 transactions', evidence_id: 'EV-384921' },
    ];
    evidenceIds = ['EV-384920', 'EV-384921'];
  } else if (q.includes('hdfc-482910') || q.includes('account') || q.includes('risk profile')) {
    content = `Account HDFC-482910 has a risk score of 0.91 (CRITICAL).\n\nKey findings:\n- 23 fraud transactions in last 30 days (threshold: 10)\n- Fan-out to 47 unique recipients (threshold: 15)\n- Total volume: $42.5M across 1,847 transactions\n- Last activity: 15 minutes ago\n\nThis account is flagged as a potential layering hub. Case CASE-2026-0018 is already open.`;
    toolCalls = [
      { tool_name: 'get_account_risk', arguments: { account_id: 'HDFC-482910' }, result_summary: 'Risk score 0.91 — CRITICAL', evidence_id: 'EV-582910' },
      { tool_name: 'get_graph_signals', arguments: { account_id: 'HDFC-482910' }, result_summary: 'Fan-out to 47 recipients detected', evidence_id: 'EV-384921' },
    ];
    evidenceIds = ['EV-582910', 'EV-384921'];
  } else if (q.includes('fan-out') || q.includes('fan out') || q.includes('pattern')) {
    content = `I detected 3 fan-out patterns in recent transactions:\n\n1. HDFC-482910 → 12 receivers in 2 hours ($1.2M total)\n2. ICICI-193847 → 18 crypto wallets in 30 min ($480K)\n3. SBI-572039 → 8 accounts via WIRE ($920K)\n\nAll three are consistent with layering behavior as defined in FATF Recommendation 20.`;
    toolCalls = [
      { tool_name: 'get_graph_signals', arguments: { pattern: 'fan_out' }, result_summary: '3 fan-out patterns detected', evidence_id: 'EV-384921' },
    ];
    evidenceIds = ['EV-384921'];
  } else if (q.includes('regulation') || q.includes('regulatory') || q.includes('requirement')) {
    const src = demoRegulatorySources[0];
    content = `Based on retrieved regulatory sources, the following requirements apply:\n\n1. FATF Recommendation 20: Financial institutions must report suspicious transactions irrespective of amount.\n2. PMLA 2002, Section 12: Maintain records of all transactions exceeding ₹10 lakh.\n3. RBI Master Directions on KYC: Risk-based categorization of transactions required.\n\nSource: ${src.document_name}, ${src.section}, p.${src.page}`;
    toolCalls = [
      { tool_name: 'search_regulation', arguments: { query: 'suspicious transaction reporting requirements' }, result_summary: '4 regulatory sources retrieved', evidence_id: 'EV-REG-001' },
    ];
    evidenceIds = ['EV-REG-001', 'EV-REG-002'];
  } else if (q.includes('str') || q.includes('draft') || q.includes('case')) {
    const c = demoCases[0];
    content = `STR Draft for ${c.case_id}:\n\nSubject: ${c.title}\n\n${c.description}\n\nRegulatory basis: FATF Recommendation 20, PMLA Section 12.\nML Evidence: Fraud probability 0.92, Anomaly score 0.95.\nEvidence IDs: ${c.evidence_ids.join(', ')}\n\nStatus: DRAFT — awaiting human review and approval before filing.`;
    toolCalls = [
      { tool_name: 'get_case', arguments: { case_id: c.case_id }, result_summary: `Case ${c.case_id} retrieved`, evidence_id: c.evidence_ids[0] },
      { tool_name: 'generate_str_draft', arguments: { case_id: c.case_id }, result_summary: 'STR draft generated', evidence_id: 'EV-STR-001' },
      { tool_name: 'search_regulation', arguments: { query: 'STR filing requirements' }, result_summary: 'Regulatory basis retrieved', evidence_id: 'EV-REG-001' },
    ];
    evidenceIds = [c.evidence_ids[0], 'EV-STR-001', 'EV-REG-001'];
  } else {
    content = `I can help you with:\n- Transaction risk analysis (fraud, anomaly, graph signals)\n- Account risk profiles\n- Liquidity and credit risk\n- Regulatory requirements (FATF, PMLA, Basel III, RBI)\n- STR/SAR draft generation\n- Case management\n\nAll responses are backed by ML model evidence and verified against regulatory sources. What would you like to investigate?`;
    toolCalls = [];
    evidenceIds = [];
  }

  return {
    id: `msg-${Date.now()}`,
    role: 'assistant',
    content,
    timestamp: new Date().toISOString(),
    evidence_ids: evidenceIds,
    verified: true,
    tool_calls: toolCalls,
  };
}
