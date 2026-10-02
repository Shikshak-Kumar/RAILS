import type {
  Transaction,
  Case,
  RegulatoryReport,
  Evidence,
  ChatMessage,
  AccountRisk,
  DashboardStats,
  RiskSignal,
  RiskLevel,
  LiquidityRisk,
  CreditRisk,
  RegulatorySource,
  SimulationType,
} from '@/types';

const now = new Date();
const iso = (offsetMin: number) =>
  new Date(now.getTime() - offsetMin * 60_000).toISOString();

export const dashboardStats: DashboardStats = {
  total_transactions: 3_147_892,
  high_risk_count: 8_421,
  critical_count: 1_247,
  open_cases: 34,
  pending_reports: 12,
  total_volume: 8_420_500_000,
  fraud_detected: 2_891,
  avg_risk_score: 0.23,
};

const banks = [
  'HDFC', 'ICICI', 'SBI', 'AXIS', 'KOTAK', 'YES', 'BARODA', 'PNB', 'IDFC', 'CITI',
];
const currencies = ['USD', 'EUR', 'GBP', 'INR', 'AED', 'SGD', 'CHF'];
const formats = ['ACH', 'WIRE', 'SWIFT', 'CHECK', 'CRYPTO', 'RTGS', 'NEFT'];
const riskLevels = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const;

function rand(min: number, max: number) {
  return Math.random() * (max - min) + min;
}
function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function makeSignals(txType: string, amount: number, isHigh: boolean): RiskSignal[] {
  const signals: RiskSignal[] = [];
  if (isHigh) {
    signals.push({
      id: 'sig-1',
      type: 'fraud',
      name: 'High Fraud Probability',
      description: `Fraud model flagged this ${txType} transaction with probability above threshold`,
      severity: 'HIGH',
      value: rand(0.75, 0.97),
      threshold: 0.7,
      triggered: true,
    });
    signals.push({
      id: 'sig-2',
      type: 'anomaly',
      name: 'Anomalous Transaction Pattern',
      description: 'Isolation Forest detected deviation from normal behavior',
      severity: 'HIGH',
      value: rand(0.8, 0.99),
      threshold: 0.75,
      triggered: true,
    });
    if (amount > 500_000) {
      signals.push({
        id: 'sig-3',
        type: 'rule',
        name: 'Large Transaction Alert',
        description: `Transaction amount ${amount.toLocaleString()} exceeds CTR threshold of 500,000`,
        severity: 'MEDIUM',
        value: amount,
        threshold: 500_000,
        triggered: true,
      });
    }
    if (txType === 'CRYPTO' || txType === 'WIRE') {
      signals.push({
        id: 'sig-4',
        type: 'graph',
        name: 'Fan-Out Pattern Detected',
        description: 'Sender account shows rapid fund dispersion to multiple recipients',
        severity: 'HIGH',
        value: 8,
        threshold: 5,
        triggered: true,
      });
    }
  } else {
    signals.push({
      id: 'sig-1',
      type: 'fraud',
      name: 'Fraud Probability',
      description: 'Transaction within normal fraud probability range',
      severity: 'LOW',
      value: rand(0.01, 0.25),
      threshold: 0.7,
      triggered: false,
    });
  }
  return signals;
}

export function generateTransaction(forceHigh?: boolean): Transaction {
  const isHigh = forceHigh ?? Math.random() < 0.15;
  const amount = isHigh ? rand(50_000, 2_500_000) : rand(100, 50_000);
  const txType = pick(formats);
  const currency = pick(currencies);
  const senderBank = pick(banks);
  const toBank = pick(banks);
  const senderId = `${senderBank}-${Math.floor(rand(100000, 999999))}`;
  const receiverId = `${toBank}-${Math.floor(rand(100000, 999999))}`;
  const fraudProb = isHigh ? rand(0.7, 0.98) : rand(0.01, 0.3);
  const anomalyScore = isHigh ? rand(0.75, 0.99) : rand(0.05, 0.4);
  const riskScore = (fraudProb + anomalyScore) / 2;
  const riskLevel = riskScore >= 0.85 ? 'CRITICAL' : riskScore >= 0.7 ? 'HIGH' : riskScore >= 0.4 ? 'MEDIUM' : 'LOW';
  const txId = `TXN-${Math.floor(rand(1_000_000, 9_999_999))}`;

  return {
    id: txId,
    transaction_id: txId,
    sender_id: senderId,
    receiver_id: receiverId,
    amount: Math.round(amount * 100) / 100,
    currency,
    timestamp: iso(Math.floor(rand(1, 10_000))),
    transaction_type: txType,
    from_bank: senderBank,
    to_bank: toBank,
    is_laundering: isHigh && Math.random() < 0.3,
    risk_assessment: {
      transaction_id: txId,
      fraud_probability: Math.round(fraudProb * 100) / 100,
      anomaly_score: Math.round(anomalyScore * 100) / 100,
      risk_score: Math.round(riskScore * 100) / 100,
      risk_level: riskLevel as RiskLevel,
      signals: makeSignals(txType, amount, isHigh),
      model_versions: [
        { model_name: 'fraud_model', version: 'v2.1.0', loaded_at: iso(120) },
        { model_name: 'anomaly_model', version: 'v1.3.0', loaded_at: iso(120) },
        { model_name: 'account_risk_model', version: 'v1.0.2', loaded_at: iso(120) },
      ],
      evidence_ids: [`EV-${txId.slice(-6)}`],
    },
  };
}

export const demoTransactions: Transaction[] = Array.from({ length: 48 }, () =>
  generateTransaction(),
).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

export const demoAccountRisks: AccountRisk[] = [
  {
    account_id: 'HDFC-482910',
    risk_score: 0.91,
    risk_level: 'CRITICAL',
    transaction_count: 1_847,
    total_volume: 42_500_000,
    fraud_transactions: 23,
    high_risk_transactions: 156,
    last_activity: iso(15),
    signals: [
      { id: 'as1', type: 'fraud', name: 'Repeated High Fraud Score', description: 'Account has 23 transactions with fraud probability > 0.7 in last 30 days', severity: 'CRITICAL', value: 23, threshold: 10, triggered: true },
      { id: 'as2', type: 'graph', name: 'Fan-Out Hub', description: 'Account disperses funds to 47 unique recipients', severity: 'HIGH', value: 47, threshold: 15, triggered: true },
    ],
  },
  {
    account_id: 'ICICI-193847',
    risk_score: 0.78,
    risk_level: 'HIGH',
    transaction_count: 934,
    total_volume: 18_200_000,
    fraud_transactions: 8,
    high_risk_transactions: 72,
    last_activity: iso(120),
    signals: [
      { id: 'as3', type: 'anomaly', name: 'Unusual Velocity', description: 'Transaction frequency 4x above account baseline', severity: 'HIGH', value: 4.2, threshold: 3, triggered: true },
    ],
  },
  {
    account_id: 'SBI-572039',
    risk_score: 0.45,
    risk_level: 'MEDIUM',
    transaction_count: 2_103,
    total_volume: 8_900_000,
    fraud_transactions: 2,
    high_risk_transactions: 19,
    last_activity: iso(480),
    signals: [
      { id: 'as4', type: 'rule', name: 'CTR Threshold Crossed', description: '3 transactions above 500K in 24 hours', severity: 'MEDIUM', value: 3, threshold: 1, triggered: true },
    ],
  },
  {
    account_id: 'AXIS-839204',
    risk_score: 0.12,
    risk_level: 'LOW',
    transaction_count: 342,
    total_volume: 1_200_000,
    fraud_transactions: 0,
    high_risk_transactions: 1,
    last_activity: iso(60),
    signals: [],
  },
];

export const demoCases: Case[] = [
  {
    id: 'case-1',
    case_id: 'CASE-2026-0018',
    transaction_id: 'TXN-3849201',
    title: 'Suspected Layering via Wire Transfers',
    description: 'Account HDFC-482910 received $1.2M from 7 sources within 2 hours, then dispersed via WIRE to 12 accounts across 4 banks. Pattern consistent with layering stage of money laundering.',
    status: 'OPEN',
    risk_level: 'CRITICAL',
    assigned_to: 'A. Sharma',
    created_at: iso(180),
    updated_at: iso(45),
    evidence_ids: ['EV-384920', 'EV-384921', 'EV-384922'],
    signals: makeSignals('WIRE', 1_200_000, true),
  },
  {
    id: 'case-2',
    case_id: 'CASE-2026-0017',
    transaction_id: 'TXN-2718394',
    title: 'Cryptocurrency Fun-Out Pattern',
    description: 'Sender account executed 18 CRYPTO transactions to distinct wallets within 30 minutes, each just below reporting threshold.',
    status: 'UNDER_REVIEW',
    risk_level: 'HIGH',
    assigned_to: 'R. Patel',
    created_at: iso(360),
    updated_at: iso(90),
    evidence_ids: ['EV-271839'],
    signals: makeSignals('CRYPTO', 480_000, true),
  },
  {
    id: 'case-3',
    case_id: 'CASE-2026-0016',
    transaction_id: 'TXN-1928374',
    title: 'Unusual Cross-Border SWIFT Transfer',
    description: 'SWIFT transfer of $850K to high-risk jurisdiction. Account had no prior cross-border activity in 12 months.',
    status: 'APPROVED',
    risk_level: 'HIGH',
    assigned_to: 'M. Iyer',
    created_at: iso(720),
    updated_at: iso(300),
    evidence_ids: ['EV-192837'],
    signals: makeSignals('SWIFT', 850_000, true),
  },
  {
    id: 'case-4',
    case_id: 'CASE-2026-0015',
    transaction_id: 'TXN-5829103',
    title: 'Rapid Fund Movement — Fan-In Detected',
    description: 'Account received 22 inbound NEFT transfers from unrelated accounts within 1 hour, totaling $2.1M.',
    status: 'FILED',
    risk_level: 'CRITICAL',
    assigned_to: 'S. Reddy',
    created_at: iso(1440),
    updated_at: iso(600),
    evidence_ids: ['EV-582910', 'EV-582911'],
    signals: makeSignals('NEFT', 2_100_000, true),
  },
  {
    id: 'case-5',
    case_id: 'CASE-2026-0014',
    transaction_id: 'TXN-7382910',
    title: 'Structuring Pattern — Sub-CTR Transactions',
    description: 'Account performed 15 CHECK transactions between $45K-$49K, avoiding CTR threshold.',
    status: 'OPEN',
    risk_level: 'HIGH',
    assigned_to: 'A. Sharma',
    created_at: iso(2880),
    updated_at: iso(1200),
    evidence_ids: ['EV-738291'],
    signals: makeSignals('CHECK', 720_000, true),
  },
];

export const demoReports: RegulatoryReport[] = [
  {
    id: 'rpt-1',
    report_id: 'STR-2026-0012',
    case_id: 'CASE-2026-0015',
    type: 'STR',
    title: 'Suspicious Transaction Report — Fan-In Pattern',
    status: 'FILED',
    created_at: iso(600),
    approved_by: 'S. Reddy',
    body: 'This report documents a suspected layering operation involving 22 inbound NEFT transfers totaling USD 2.1M received by account SBI-572039 within a 60-minute window. All sender accounts were unrelated individuals with no prior transactional relationship. Funds were subsequently dispersed via 14 WIRE transfers to accounts in 3 jurisdictions. The pattern is consistent with the placement-to-layering transition described in FATF Recommendation 20. The ML fraud model assigned a probability of 0.94, and the anomaly model returned a score of 0.97. Evidence IDs: EV-582910, EV-582911.',
    evidence_ids: ['EV-582910', 'EV-582911'],
  },
  {
    id: 'rpt-2',
    report_id: 'STR-2026-0011',
    case_id: 'CASE-2026-0016',
    type: 'STR',
    title: 'Suspicious Transaction Report — Cross-Border SWIFT',
    status: 'APPROVED',
    created_at: iso(300),
    approved_by: 'M. Iyer',
    body: 'Account ICICI-193847 executed a SWIFT transfer of USD 850K to a bank in a high-risk jurisdiction. The account had no cross-border activity in the prior 12 months. Fraud model probability: 0.81. Anomaly score: 0.89. Evidence ID: EV-192837.',
    evidence_ids: ['EV-192837'],
  },
  {
    id: 'rpt-3',
    report_id: 'AML-2026-0008',
    case_id: 'CASE-2026-0018',
    type: 'AML_ALERT',
    title: 'AML Alert — Suspected Layering via Wire Transfers',
    status: 'DRAFT',
    created_at: iso(45),
    approved_by: null,
    body: 'Draft report pending review. Account HDFC-482910 received USD 1.2M from 7 sources and dispersed to 12 accounts across 4 banks within 2 hours. Fraud probability: 0.92. Anomaly score: 0.95. Evidence IDs: EV-384920, EV-384921, EV-384922.',
    evidence_ids: ['EV-384920', 'EV-384921', 'EV-384922'],
  },
  {
    id: 'rpt-4',
    report_id: 'SAR-2026-0005',
    case_id: 'CASE-2026-0017',
    type: 'SAR',
    title: 'Suspicious Activity Report — Crypto Fan-Out',
    status: 'IN_REVIEW',
    created_at: iso(90),
    approved_by: null,
    body: 'Account executed 18 CRYPTO transactions to distinct wallets within 30 minutes, each below the reporting threshold of USD 50K. Total volume: USD 480K. This structuring pattern is indicative of smurfing. Fraud probability: 0.85. Anomaly score: 0.91. Evidence ID: EV-271839.',
    evidence_ids: ['EV-271839'],
  },
];

export const demoEvidence: Evidence[] = [
  {
    evidence_id: 'EV-384920',
    timestamp: iso(175),
    request_id: 'REQ-001',
    session_id: 'SES-001',
    tool_name: 'get_transaction_risk',
    tool_arguments: { transaction_id: 'TXN-3849201' },
    tool_output: { fraud_probability: 0.92, anomaly_score: 0.95, risk_level: 'CRITICAL' },
    model_name: 'fraud_model',
    model_version: 'v2.1.0',
  },
  {
    evidence_id: 'EV-384921',
    timestamp: iso(174),
    request_id: 'REQ-001',
    session_id: 'SES-001',
    tool_name: 'get_graph_signals',
    tool_arguments: { account_id: 'HDFC-482910' },
    tool_output: { fan_out_count: 12, fan_in_count: 7, pattern: 'layering' },
    model_name: 'graph_analyzer',
    model_version: 'v1.0.0',
  },
  {
    evidence_id: 'EV-384922',
    timestamp: iso(173),
    request_id: 'REQ-001',
    session_id: 'SES-001',
    tool_name: 'get_fraud_signals',
    tool_arguments: { transaction_id: 'TXN-3849201' },
    tool_output: { signals: ['high_velocity', 'large_amount', 'cross_bank_dispersion'] },
    model_name: 'fraud_model',
    model_version: 'v2.1.0',
  },
  {
    evidence_id: 'EV-271839',
    timestamp: iso(355),
    request_id: 'REQ-002',
    session_id: 'SES-002',
    tool_name: 'get_transaction_risk',
    tool_arguments: { transaction_id: 'TXN-2718394' },
    tool_output: { fraud_probability: 0.85, anomaly_score: 0.91, risk_level: 'HIGH' },
    model_name: 'fraud_model',
    model_version: 'v2.1.0',
  },
  {
    evidence_id: 'EV-582910',
    timestamp: iso(1435),
    request_id: 'REQ-003',
    session_id: 'SES-003',
    tool_name: 'get_account_risk',
    tool_arguments: { account_id: 'SBI-572039' },
    tool_output: { risk_score: 0.93, risk_level: 'CRITICAL', fan_in_count: 22 },
    model_name: 'account_risk_model',
    model_version: 'v1.0.2',
  },
];

export const demoChatMessages: ChatMessage[] = [
  {
    id: 'msg-1',
    role: 'user',
    content: 'Show me the highest-risk transactions from the last 24 hours.',
    timestamp: iso(30),
  },
  {
    id: 'msg-2',
    role: 'assistant',
    content: 'I found 3 CRITICAL and 5 HIGH risk transactions in the last 24 hours. The most severe is TXN-3849201 with a fraud probability of 0.92 and anomaly score of 0.95. This transaction involves a $1.2M wire transfer from HDFC-482910 that was dispersed to 12 accounts across 4 banks, consistent with a layering pattern. Case CASE-2026-0018 has been opened for this transaction.',
    timestamp: iso(29),
    evidence_ids: ['EV-384920', 'EV-384921'],
    verified: true,
    tool_calls: [
      { tool_name: 'get_recent_transactions', arguments: { time_window: '24h' }, result_summary: '8 high-risk transactions found', evidence_id: 'EV-384920' },
      { tool_name: 'get_graph_signals', arguments: { account_id: 'HDFC-482910' }, result_summary: 'Fan-out to 12 accounts detected', evidence_id: 'EV-384921' },
    ],
  },
];

export const demoLiquidityRisks: LiquidityRisk[] = [
  {
    account_id: 'HDFC-482910',
    inflow_30d: 15_200_000,
    outflow_30d: 14_800_000,
    net_flow: 400_000,
    liquidity_ratio: 1.03,
    risk_level: 'MEDIUM',
    stress_test_passed: true,
  },
  {
    account_id: 'ICICI-193847',
    inflow_30d: 3_100_000,
    outflow_30d: 5_400_000,
    net_flow: -2_300_000,
    liquidity_ratio: 0.57,
    risk_level: 'HIGH',
    stress_test_passed: false,
  },
  {
    account_id: 'SBI-572039',
    inflow_30d: 8_900_000,
    outflow_30d: 2_100_000,
    net_flow: 6_800_000,
    liquidity_ratio: 4.24,
    risk_level: 'LOW',
    stress_test_passed: true,
  },
  {
    account_id: 'AXIS-839204',
    inflow_30d: 1_200_000,
    outflow_30d: 900_000,
    net_flow: 300_000,
    liquidity_ratio: 1.33,
    risk_level: 'LOW',
    stress_test_passed: true,
  },
];

export const demoCreditRisks: CreditRisk[] = [
  {
    account_id: 'HDFC-482910',
    credit_score: 620,
    default_probability: 0.18,
    exposure: 4_200_000,
    risk_level: 'HIGH',
    recommendation: 'Increase provisioning by 2.5%. Recommend enhanced monitoring.',
  },
  {
    account_id: 'ICICI-193847',
    credit_score: 580,
    default_probability: 0.24,
    exposure: 2_800_000,
    risk_level: 'HIGH',
    recommendation: 'Increase provisioning by 3%. Consider exposure reduction.',
  },
  {
    account_id: 'SBI-572039',
    credit_score: 740,
    default_probability: 0.05,
    exposure: 1_500_000,
    risk_level: 'LOW',
    recommendation: 'Maintain current provisioning. No action required.',
  },
  {
    account_id: 'AXIS-839204',
    credit_score: 780,
    default_probability: 0.03,
    exposure: 800_000,
    risk_level: 'LOW',
    recommendation: 'Low risk. Maintain standard monitoring.',
  },
];

export const demoRegulatorySources: RegulatorySource[] = [
  {
    document_id: 'DOC-FATF-REC20',
    document_name: 'FATF Recommendations 2012',
    section: 'Recommendation 20 — Reporting of Suspicious Transactions',
    page: 47,
    text: 'Financial institutions should be required to report to the financial intelligence unit, irrespective of the amount of funds, any transaction they suspect to be related to money laundering or terrorist financing.',
    evidence_id: 'EV-REG-001',
  },
  {
    document_id: 'DOC-PMLA-2002',
    document_name: 'Prevention of Money Laundering Act, 2002 (India)',
    section: 'Section 12 — Obligation to Maintain Records',
    page: 14,
    text: 'Every banking company, financial institution and intermediary shall maintain a record of all transactions exceeding rupees ten lakh or its equivalent in foreign currency.',
    evidence_id: 'EV-REG-002',
  },
  {
    document_id: 'DOC-BASEL-III',
    document_name: 'Basel III Liquidity Framework',
    section: 'Liquidity Coverage Ratio (LCR)',
    page: 23,
    text: 'Banks must hold sufficient high-quality liquid assets to cover total net cash outflows over a 30-day stress period. The minimum LCR requirement is 100%.',
    evidence_id: 'EV-REG-003',
  },
  {
    document_id: 'DOC-RBI-MASTER',
    document_name: 'RBI Master Directions on KYC, 2016',
    section: 'Part C — Transaction Monitoring',
    page: 31,
    text: 'Banks should put in place a system of risk-based categorization of transactions and accounts to identify suspicious patterns including structuring, layering, and rapid fund movements.',
    evidence_id: 'EV-REG-004',
  },
];

export const simulationPresets: Record<
  SimulationType,
  { label: string; description: string; color: 'green' | 'yellow' | 'red' }
> = {
  normal: { label: 'Normal Traffic', description: 'Typical day-to-day transaction flow', color: 'green' },
  high_velocity: { label: 'High Velocity', description: 'Rapid burst of transactions from single account', color: 'yellow' },
  fan_in: { label: 'Fan-In', description: 'Many senders converging on one receiver', color: 'red' },
  fan_out: { label: 'Fan-Out', description: 'One sender dispersing to many receivers', color: 'red' },
  rapid_fund_movement: { label: 'Rapid Fund Movement', description: 'Quick chain of transfers across accounts', color: 'yellow' },
  unusual_amount: { label: 'Unusual Amount', description: 'Transactions with abnormally large amounts', color: 'yellow' },
  liquidity_stress: { label: 'Liquidity Stress', description: 'Large outflows creating liquidity pressure', color: 'red' },
  mixed_risk: { label: 'Mixed Risk', description: 'Combination of multiple risk patterns', color: 'red' },
};

export function simulateTransactions(type: SimulationType, count: number): Transaction[] {
  const transactions: Transaction[] = [];
  const baseTime = Date.now();

  for (let i = 0; i < count; i++) {
    const tx = generateTransaction();
    tx.timestamp = new Date(baseTime - i * 5000).toISOString();

    switch (type) {
      case 'normal':
        tx.risk_assessment = tx.risk_assessment;
        break;
      case 'high_velocity': {
        tx.sender_id = 'SIM-HV-001';
        tx.transaction_type = 'ACH';
        tx.amount = Math.round(rand(5_000, 25_000) * 100) / 100;
        const fp = rand(0.6, 0.85);
        const as = rand(0.7, 0.9);
        tx.risk_assessment = {
          ...tx.risk_assessment!,
          fraud_probability: Math.round(fp * 100) / 100,
          anomaly_score: Math.round(as * 100) / 100,
          risk_score: Math.round(((fp + as) / 2) * 100) / 100,
          risk_level: 'HIGH',
          signals: makeSignals('ACH', tx.amount, true),
        };
        break;
      }
      case 'fan_in': {
        tx.receiver_id = 'SIM-FI-001';
        tx.transaction_type = 'NEFT';
        tx.amount = Math.round(rand(80_000, 200_000) * 100) / 100;
        const fp = rand(0.75, 0.95);
        const as = rand(0.8, 0.97);
        tx.risk_assessment = {
          ...tx.risk_assessment!,
          fraud_probability: Math.round(fp * 100) / 100,
          anomaly_score: Math.round(as * 100) / 100,
          risk_score: Math.round(((fp + as) / 2) * 100) / 100,
          risk_level: 'CRITICAL',
          signals: makeSignals('NEFT', tx.amount, true),
        };
        break;
      }
      case 'fan_out': {
        tx.sender_id = 'SIM-FO-001';
        tx.transaction_type = 'WIRE';
        tx.amount = Math.round(rand(90_000, 180_000) * 100) / 100;
        const fp = rand(0.78, 0.96);
        const as = rand(0.82, 0.98);
        tx.risk_assessment = {
          ...tx.risk_assessment!,
          fraud_probability: Math.round(fp * 100) / 100,
          anomaly_score: Math.round(as * 100) / 100,
          risk_score: Math.round(((fp + as) / 2) * 100) / 100,
          risk_level: 'CRITICAL',
          signals: makeSignals('WIRE', tx.amount, true),
        };
        break;
      }
      case 'rapid_fund_movement': {
        tx.transaction_type = 'SWIFT';
        tx.amount = Math.round(rand(200_000, 800_000) * 100) / 100;
        const fp = rand(0.65, 0.88);
        const as = rand(0.7, 0.92);
        tx.risk_assessment = {
          ...tx.risk_assessment!,
          fraud_probability: Math.round(fp * 100) / 100,
          anomaly_score: Math.round(as * 100) / 100,
          risk_score: Math.round(((fp + as) / 2) * 100) / 100,
          risk_level: 'HIGH',
          signals: makeSignals('SWIFT', tx.amount, true),
        };
        break;
      }
      case 'unusual_amount': {
        tx.amount = Math.round(rand(500_000, 3_000_000) * 100) / 100;
        const fp = rand(0.55, 0.8);
        const as = rand(0.65, 0.88);
        tx.risk_assessment = {
          ...tx.risk_assessment!,
          fraud_probability: Math.round(fp * 100) / 100,
          anomaly_score: Math.round(as * 100) / 100,
          risk_score: Math.round(((fp + as) / 2) * 100) / 100,
          risk_level: 'HIGH',
          signals: makeSignals(tx.transaction_type, tx.amount, true),
        };
        break;
      }
      case 'liquidity_stress': {
        tx.transaction_type = 'RTGS';
        tx.amount = Math.round(rand(1_000_000, 5_000_000) * 100) / 100;
        tx.risk_assessment = {
          ...tx.risk_assessment!,
          risk_level: 'MEDIUM',
          signals: [
            { id: 'liq1', type: 'liquidity', name: 'Liquidity Drain', description: 'Large outflow reducing account liquidity ratio below 1.0', severity: 'HIGH', value: tx.amount, threshold: 1_000_000, triggered: true },
          ],
        };
        break;
      }
      case 'mixed_risk': {
        const isHigh = Math.random() < 0.6;
        if (isHigh) {
          const fp = rand(0.7, 0.97);
          const as = rand(0.75, 0.99);
          tx.risk_assessment = {
            ...tx.risk_assessment!,
            fraud_probability: Math.round(fp * 100) / 100,
            anomaly_score: Math.round(as * 100) / 100,
            risk_score: Math.round(((fp + as) / 2) * 100) / 100,
            risk_level: 'CRITICAL',
            signals: makeSignals(tx.transaction_type, tx.amount, true),
          };
        }
        break;
      }
    }
    transactions.push(tx);
  }
  return transactions;
}

export function getSimulationSummary(transactions: Transaction[]) {
  const high = transactions.filter(t => t.risk_assessment?.risk_level === 'HIGH').length;
  const critical = transactions.filter(t => t.risk_assessment?.risk_level === 'CRITICAL').length;
  const avgFp = transactions.reduce((s, t) => s + (t.risk_assessment?.fraud_probability ?? 0), 0) / transactions.length;
  const avgAs = transactions.reduce((s, t) => s + (t.risk_assessment?.anomaly_score ?? 0), 0) / transactions.length;
  return {
    total_transactions: transactions.length,
    high_risk: high,
    critical,
    cases_generated: critical + Math.floor(high / 3),
    avg_fraud_probability: Math.round(avgFp * 100) / 100,
    avg_anomaly_score: Math.round(avgAs * 100) / 100,
  };
}
