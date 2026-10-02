const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function fetcher(endpoint: string, options: RequestInit = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 45000); // 45s timeout

  try {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      let errorDetail = '';
      try {
        const errBody = await response.json();
        errorDetail = errBody.detail || JSON.stringify(errBody);
      } catch {
        errorDetail = await response.text();
      }
      throw new Error(errorDetail || `API Error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out. Please retry.');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export const api = {
  getOverview: async () => {
    const data = await fetcher('/overview');
    return {
      total_transactions: data.total_transactions || 0,
      high_risk_count: data.high_risk_transactions || 0,
      critical_count: data.critical_alerts || 0,
      open_cases: data.open_cases || 0,
      count_cases: data.count_cases || data.open_cases || 0,
      count_reports: data.count_reports || 0,
      pending_reports: data.pending_reports || 0,
      total_volume: data.total_volume || 0,
      fraud_detected: data.fraud_detected || 0,
      avg_risk_score: data.avg_risk_score || 0,
      risk_distribution: data.risk_distribution || { critical: 0, high: 0, medium: 0, low: 0 },
      model_status: data.model_status || {},
    };
  },

  getTransactions: async (limit = 50, offset = 0, search = '') => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (search && search.trim()) {
      params.set('search', search.trim());
    }

    const data = await fetcher(`/transactions?${params.toString()}`);
    const normalize = (tx: any) => ({
      ...tx,
      id: tx.id || tx.transaction_id,
      currency: tx.currency?.length > 4
        ? tx.currency.split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 3)
        : (tx.currency || 'USD'),
      from_bank: tx.from_bank || tx.sender_id || '',
      to_bank: tx.to_bank || tx.receiver_id || '',
    });

    return {
      ...data,
      total: data.total !== undefined ? Number(data.total) : undefined,
      items: (data.items || []).map(normalize),
    };
  },

  getTransaction: (id: string) => fetcher(`/transactions/${id}`),

  getRiskSignals: () => fetcher('/risk/signals'),

  getAccountRisk: (id: string) => fetcher(`/risk/accounts/${id}`),

  getCases: async (status?: string, search?: string) => {
    const params = new URLSearchParams();
    if (status && status !== 'ALL') params.set('status', status);
    if (search && search.trim()) params.set('search', search.trim());
    const query = params.toString() ? `?${params.toString()}` : '';

    const data = await fetcher(`/cases${query}`);
    const cases = Array.isArray(data) ? data : (data.cases || data.items || []);
    return cases.map((c: any) => ({
      id: c.id || c.case_id,
      case_id: c.case_id || c.id,
      transaction_id: c.transaction_id || '',
      title: c.title || c.summary || c.case_id,
      description: c.description || c.summary || '',
      status: c.status || 'OPEN',
      risk_level: c.risk_level || 'MEDIUM',
      assigned_to: c.assigned_to || 'Compliance Officer',
      created_at: c.created_at || new Date().toISOString(),
      updated_at: c.updated_at || c.created_at || new Date().toISOString(),
      evidence_ids: c.evidence_ids || [],
      signals: c.signals || [],
    }));
  },

  getCase: (id: string) => fetcher(`/cases/${id}`),

  updateCaseStatus: (id: string, status: string) => fetcher(`/cases/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status })
  }),

  createCase: (summary: string, status = 'OPEN', transactionId?: string) => {
    return fetcher('/cases', {
      method: 'POST',
      body: JSON.stringify({
        summary,
        title: summary,
        status,
        transaction_id: transactionId,
      }),
    });
  },

  getReports: async (status?: string, caseId?: string) => {
    const params = new URLSearchParams();
    if (status && status !== 'ALL') params.set('status', status);
    if (caseId) params.set('case_id', caseId);
    const query = params.toString() ? `?${params.toString()}` : '';

    const data = await fetcher(`/regulatory/reports${query}`);
    const list = Array.isArray(data) ? data : (data.reports || data.items || []);
    return list.map((r: any) => ({
      id: r.id || r.report_id,
      report_id: r.report_id || r.id,
      case_id: r.case_id || '',
      type: r.type || 'STR',
      title: r.title || r.report_id || 'Regulatory Report',
      status: r.status || 'DRAFT',
      created_at: r.created_at || new Date().toISOString(),
      approved_by: r.approved_by || null,
      body: r.body || r.narrative || r.summary || '',
      evidence_ids: r.evidence_ids || [],
    }));
  },

  getReport: (id: string) => fetcher(`/regulatory/reports/${id}`),

  generateSTRDraft: (caseId: string, transactionId?: string, narrative?: string) => {
    return fetcher('/reports/generate-str', {
      method: 'POST',
      body: JSON.stringify({
        case_id: caseId,
        transaction_id: transactionId,
        narrative,
      }),
    });
  },

  approveReport: (reportId: string, approvedBy = 'Compliance Officer') => {
    return fetcher(`/reports/${reportId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    });
  },

  rejectReport: (reportId: string) => {
    return fetcher(`/reports/${reportId}/reject`, {
      method: 'POST',
    });
  },

  generateReport: (title: string, body: string) => {
    return fetcher(`/reports/generate?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`, {
      method: 'POST',
    });
  },

  downloadReportFile: (reportId: string) => {
    const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
    const a = document.createElement('a');
    a.href = `${base}/reports/${reportId}/download`;
    a.download = `${reportId}_SAR_Report.docx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  },


  chatWithCopilot: async (
    message: string,
    intent?: string,
    account_id?: string,
    transaction_id?: string,
    conversation_id?: string,
  ) => {
    const payload: Record<string, any> = { message };
    if (intent) payload.intent = intent;
    if (account_id) payload.account_id = account_id;
    if (transaction_id) payload.transaction_id = transaction_id;
    if (conversation_id) payload.conversation_id = conversation_id;

    const res = await fetcher('/copilot/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    return {
      ...res,
      content: res.response || res.answer || res.content || '',
      tool_calls: (res.tool_calls || []).map((tc: any) => ({
        tool_name: tc.tool || tc.tool_name || 'tool',
        arguments: tc.arguments || tc.args || {},
        result_summary: tc.result_summary || (typeof tc.result === 'object' ? JSON.stringify(tc.result).slice(0, 60) : String(tc.result || '')),
        evidence_id: tc.evidence_id || '',
      })),
    };
  },

  analyzeTransaction: (id: string) => fetcher(`/risk/transactions/${id}/analyze`, { method: 'POST' }),

  startSimulation: (type: string, count: number) => {
    return fetcher('/simulation/start', {
      method: 'POST',
      body: JSON.stringify({ type, count }),
    });
  },

  getSimulationJob: (jobId: string) => {
    return fetcher(`/simulation/${jobId}`);
  },

  getExecutions: (limit: number = 50) => {
    return fetcher(`/executions?limit=${limit}`);
  },

  getExecution: (executionId: string) => {
    return fetcher(`/executions/${executionId}`);
  },

  getExecutionSteps: (executionId: string) => {
    return fetcher(`/executions/${executionId}/steps`);
  },
};

