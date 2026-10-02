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