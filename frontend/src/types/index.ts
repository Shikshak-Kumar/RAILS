export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type CaseStatus = 'OPEN' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED' | 'FILED';

export type ReportStatus = 'DRAFT' | 'IN_REVIEW' | 'APPROVED' | 'FILED' | 'REJECTED';

export type SimulationType =
  | 'normal'
  | 'high_velocity'
  | 'fan_in'
  | 'fan_out'
  | 'rapid_fund_movement'
  | 'unusual_amount'
  | 'liquidity_stress'
  | 'mixed_risk';

export interface RiskAssessment {
  transaction_id: string;
  fraud_probability: number;
  anomaly_score: number;
  risk_score: number;
  risk_level: RiskLevel;
  signals: RiskSignal[];
  model_versions: ModelVersion[];
  evidence_ids: string[];
}

export interface RiskSignal {
  id: string;
  type: 'fraud' | 'anomaly' | 'graph' | 'liquidity' | 'credit' | 'rule';
  name: string;
  description: string;
  severity: RiskLevel;
  value: number;
  threshold: number;
  triggered: boolean;
}

export interface ModelVersion {
  model_name: string;
  version: string;
  loaded_at: string;
}

export interface Transaction {
  id: string;
  transaction_id: string;
  sender_id: string;
  receiver_id: string;
  amount: number;
  currency: string;
  timestamp: string;
  transaction_type: string;
  from_bank: string;
  to_bank: string;
  risk_level?: RiskLevel;
  risk_score?: number;
  fraud_probability?: number;
  anomaly_score?: number;
  signals?: string[];
  risk_assessment?: RiskAssessment;
  is_laundering?: boolean;
}

export interface AccountRisk {
  account_id: string;
  risk_score: number;
  risk_level: RiskLevel;
  transaction_count: number;
  total_volume: number;
  fraud_transactions: number;
  high_risk_transactions: number;
  last_activity: string;
  signals: RiskSignal[];
}

export interface Case {
  id: string;
  case_id: string;
  transaction_id: string;
  title: string;
  description: string;
  status: CaseStatus;
  risk_level: RiskLevel;
  assigned_to: string;
  created_at: string;
  updated_at: string;
  evidence_ids: string[];
  signals: RiskSignal[];
}

export interface RegulatoryReport {
  id: string;
  report_id: string;
  case_id: string;
  type: 'STR' | 'SAR' | 'CTR' | 'AML_ALERT';
  title: string;
  status: ReportStatus;
  created_at: string;
  approved_by: string | null;
  body: string;
  evidence_ids: string[];
}

export interface Evidence {
  evidence_id: string;
  timestamp: string;
  request_id: string;
  session_id: string;
  tool_name: string;
  tool_arguments: Record<string, unknown>;
  tool_output: Record<string, unknown>;
  model_name: string;
  model_version: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  evidence_ids?: string[];
  verified?: boolean;
  tool_calls?: ToolCall[];
}

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  result_summary: string;
  evidence_id: string;
}

export interface SimulationConfig {
  type: SimulationType;
  transaction_count: number;
  interval_ms: number;
  amount_range: [number, number];
}

export interface SimulationResult {
  id: string;
  type: SimulationType;
  transactions: Transaction[];
  started_at: string;
  summary: SimulationSummary;
}

export interface SimulationSummary {
  total_transactions?: number;
  total_evaluated?: number;
  high_risk?: number;
  high_risk_count?: number;
  medium_risk_count?: number;
  critical?: number;
  cases_generated?: number;
  avg_fraud_probability?: number;
  avg_anomaly_score?: number;
  average_risk_score?: number;
}

export interface DashboardStats {
  total_transactions: number;
  high_risk_count: number;
  critical_count: number;
  open_cases: number;
  pending_reports: number;
  total_volume: number;
  fraud_detected: number;
  avg_risk_score: number;
}

export interface RegulatorySource {
  document_id: string;
  document_name: string;
  section: string;
  page: number;
  text: string;
  evidence_id: string;
}

export interface LiquidityRisk {
  account_id: string;
  inflow_30d: number;
  outflow_30d: number;
  net_flow: number;
  liquidity_ratio: number;
  risk_level: RiskLevel;
  stress_test_passed: boolean;
}

export interface CreditRisk {
  account_id: string;
  credit_score: number;
  default_probability: number;
  exposure: number;
  risk_level: RiskLevel;
  recommendation: string;
}
