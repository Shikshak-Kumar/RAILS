CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    from_bank INTEGER,
    sender_account TEXT NOT NULL CHECK (sender_account <> ''),
    to_bank INTEGER,
    receiver_account TEXT NOT NULL CHECK (receiver_account <> ''),
    amount_received DOUBLE PRECISION CHECK (amount_received IS NULL OR amount_received >= 0),
    receiving_currency TEXT,
    amount_paid DOUBLE PRECISION NOT NULL CHECK (amount_paid >= 0),
    payment_currency TEXT,
    payment_format TEXT,
    is_laundering BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_timestamp
    ON transactions (timestamp);

CREATE INDEX IF NOT EXISTS idx_transactions_sender_timestamp
    ON transactions (sender_account, timestamp);

CREATE INDEX IF NOT EXISTS idx_transactions_receiver_timestamp
    ON transactions (receiver_account, timestamp);

CREATE INDEX IF NOT EXISTS idx_transactions_sender_receiver
    ON transactions (sender_account, receiver_account);

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    fraud_probability DOUBLE PRECISION,
    anomaly_score DOUBLE PRECISION,
    signals JSONB DEFAULT '[]'::jsonb,
    evidence_ids JSONB DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'OPEN',
    case_id TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_transaction_id
    ON alerts (transaction_id);

CREATE INDEX IF NOT EXISTS idx_alerts_risk_level
    ON alerts (risk_level);

CREATE INDEX IF NOT EXISTS idx_alerts_case_id
    ON alerts (case_id);

CREATE INDEX IF NOT EXISTS idx_alerts_status
    ON alerts (status);

CREATE INDEX IF NOT EXISTS idx_alerts_created_at
    ON alerts (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cases_status
    ON cases (status);

CREATE INDEX IF NOT EXISTS idx_cases_created_at
    ON cases (created_at DESC);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'STR',
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    body TEXT NOT NULL,
    evidence_ids JSONB DEFAULT '[]'::jsonb,
    approved_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reports_case_id
    ON reports (case_id);

CREATE INDEX IF NOT EXISTS idx_reports_created_at
    ON reports (created_at DESC);

CREATE TABLE IF NOT EXISTS simulation_jobs (
    job_id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    status TEXT NOT NULL,
    total INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    progress INTEGER NOT NULL DEFAULT 0,
    current_step TEXT,
    current_transaction_id TEXT,
    alerts_created INTEGER DEFAULT 0,
    results JSONB DEFAULT '[]'::jsonb,
    summary JSONB DEFAULT '{}'::jsonb,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_simulation_jobs_status
    ON simulation_jobs (status);

CREATE INDEX IF NOT EXISTS idx_simulation_jobs_created_at
    ON simulation_jobs (created_at DESC);