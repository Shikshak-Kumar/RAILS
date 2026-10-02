const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function fetcher(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
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
}

export const api = {
  getOverview: async () => {
    const data = await fetcher('/overview');
    return {
      total_transactions: data.total_transactions || 0,
      high_risk_count: data.high_risk_transactions || 0,
      critical_count: data.critical_alerts || 0,
      open_cases: data.open_cases || 0,
      pending_reports: data.pending_reports || 0, // Mocked to 0 if missing from backend
      total_volume: data.total_volume || 0,
      fraud_detected: data.fraud_detected || 0,
      avg_risk_score: data.avg_risk_score || 0,
    };
  },
  getTransactions: async (limit = 50, offset = 0) => {
    const data = await fetcher(`/transactions?limit=${limit}&offset=${offset}`);
    const normalize = (tx: any) => ({
      ...tx,
      id: tx.id || tx.transaction_id,                        // ensure id exists
      currency: tx.currency?.length > 4                      // normalize "US Dollar" → "USD"
        ? tx.currency.split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 3)
        : (tx.currency || 'USD'),
      from_bank: tx.from_bank || tx.sender_id || '',
      to_bank: tx.to_bank || tx.receiver_id || '',
    });
    return { ...data, items: (data.items || []).map(normalize) };
  },
  getTransaction: (id: string) => fetcher(`/transactions/${id}`),
  getRiskSignals: () => fetcher('/risk/signals'),
  getAccountRisk: (id: string) => fetcher(`/risk/accounts/${id}`),
  getCases: async () => {
    const data = await fetcher('/cases');
    const cases = Array.isArray(data) ? data : (data.cases || data.items || []);
    return cases.map((c: any) => ({
      id: c.id || c.case_id,
      case_id: c.case_id || c.id,
      transaction_id: c.transaction_id || '',
      title: c.title || c.summary || c.case_id,
      description: c.description || c.summary || '',
      status: c.status || 'OPEN',
      risk_level: c.risk_level || 'MEDIUM',
      assigned_to: c.assigned_to || 'Unassigned',
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
  createCase: (summary: string, status = 'OPEN') => fetcher(`/cases?summary=${encodeURIComponent(summary)}&status=${encodeURIComponent(status)}`, {
    method: 'POST'
  }),
  getReports: async () => {
    const data = await fetcher('/regulatory/reports');
    // Backend returns { reports: [] } — unwrap it
    const list = Array.isArray(data) ? data : (data.reports || data.items || []);
    return list.map((r: any) => ({
      id: r.id || r.report_id,
      report_id: r.report_id || r.id,
      case_id: r.case_id || '',
      type: r.type || 'STR',
      title: r.title || r.report_id || 'Report',
      status: r.status || 'DRAFT',
      created_at: r.created_at || new Date().toISOString(),
      approved_by: r.approved_by || null,
      body: r.body || r.narrative || r.summary || '',
      evidence_ids: r.evidence_ids || [],
    }));
  },
  generateReport: (title: string, body: string) => fetcher(`/reports/generate?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`, {
    method: 'POST'
  }),
  chatWithCopilot: (message: string, intent?: string, account_id?: string, transaction_id?: string) => {
    const payload: Record<string, any> = { message };
    if (intent) payload.intent = intent;
    if (account_id) payload.account_id = account_id;
    if (transaction_id) payload.transaction_id = transaction_id;
    return fetcher('/copilot/chat', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  analyzeTransaction: (id: string) => fetcher(`/risk/transactions/${id}/analyze`, { method: 'POST' }),
  startSimulation: (type: string, count: number) => fetcher('/simulation/start', { method: 'POST', body: JSON.stringify({ type, count }) }),
};
