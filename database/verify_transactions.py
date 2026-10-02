#!/usr/bin/env python3
"""Print basic row-count, label, timestamp, null, and sample checks."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent


def get_database_url() -> str:
    load_dotenv(ROOT_DIR / ".env")
    database_url = os.getenv("SUPABASE_DB_URL") or os.getenv("SUPABASE_URL")
    if not database_url:
        raise ValueError("Set SUPABASE_DB_URL in the environment or project .env file")
    return database_url


def main() -> None:
    with psycopg.connect(get_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_transactions,
                    COUNT(*) FILTER (WHERE is_laundering) AS laundering_transactions,
                    MIN(timestamp) AS minimum_timestamp,
                    MAX(timestamp) AS maximum_timestamp,
                    COUNT(*) FILTER (WHERE sender_account IS NULL) AS null_senders,
                    COUNT(*) FILTER (WHERE receiver_account IS NULL) AS null_receivers,
                    COUNT(*) FILTER (WHERE amount_paid IS NULL) AS null_amounts
                FROM transactions
                """
            )
            stats = cursor.fetchone()
            print(f"Total transactions: {stats[0]}")
            print(f"Laundering transactions: {stats[1]}")
            print(f"Minimum timestamp: {stats[2]}")
            print(f"Maximum timestamp: {stats[3]}")
            print(f"Rows with NULL sender_account: {stats[4]}")
            print(f"Rows with NULL receiver_account: {stats[5]}")
            print(f"Rows with NULL amount_paid: {stats[6]}")

            cursor.execute(
                """
                SELECT id, timestamp, sender_account, receiver_account,
                       amount_received, amount_paid, is_laundering
                FROM transactions
                ORDER BY id
                LIMIT 10
                """
            )
            print("Sample transactions:")
            for transaction in cursor.fetchall():
                print(transaction)


if __name__ == "__main__":
    main()