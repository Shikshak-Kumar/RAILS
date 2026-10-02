#!/usr/bin/env python3
"""Stream the IBM AML transaction CSV into PostgreSQL using COPY."""

import argparse
import csv
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import psycopg
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_PATH = ROOT_DIR / "HI-Small_Trans.csv"
CHUNK_SIZE = 50_000
EXPECTED_HEADER = [
    "Timestamp",
    "From Bank",
    "Account",
    "To Bank",
    "Account",
    "Amount Received",
    "Receiving Currency",
    "Amount Paid",
    "Payment Currency",
    "Payment Format",
    "Is Laundering",
]
COPY_SQL = """
    COPY transactions (
        timestamp, from_bank, sender_account, to_bank, receiver_account,
        amount_received, receiving_currency, amount_paid, payment_currency,
        payment_format, is_laundering
    ) FROM STDIN
"""


def parse_timestamp(value: str) -> datetime:
    value = value.strip()
    for date_format in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"invalid timestamp: {value!r}")


def optional_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    number = int(value)
    if not -(2**31) <= number < 2**31:
        raise ValueError(f"integer outside PostgreSQL INTEGER range: {value!r}")
    return number


def optional_amount(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    amount = float(value)
    if not math.isfinite(amount) or amount < 0:
        raise ValueError(f"invalid amount: {value!r}")
    return amount


def required_text(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"missing {field_name}")
    return value


def optional_text(value: str) -> str | None:
    value = value.strip()
    return value or None


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def parse_row(row: list[str]) -> tuple:
    if len(row) != len(EXPECTED_HEADER):
        raise ValueError(f"expected {len(EXPECTED_HEADER)} fields, got {len(row)}")

    amount_paid = optional_amount(row[7])
    if amount_paid is None:
        raise ValueError("missing amount paid")

    label = row[10].strip().lower()
    if label not in {"0", "1", "false", "true"}:
        raise ValueError(f"invalid laundering label: {row[10]!r}")

    return (
        parse_timestamp(row[0]),
        optional_int(row[1]),
        required_text(row[2], "sender account"),
        optional_int(row[3]),
        required_text(row[4], "receiver account"),
        optional_amount(row[5]),
        optional_text(row[6]),
        amount_paid,
        optional_text(row[8]),
        optional_text(row[9]),
        label in {"1", "true"},
    )


def count_data_rows(csv_path: Path) -> int:
    with csv_path.open("r", newline="", encoding="utf-8-sig") as source:
        reader = csv.reader(source, strict=True)
        header = next(reader, None)
        if header != EXPECTED_HEADER:
            raise ValueError(f"unexpected CSV header: {header!r}")
        total_rows = 0
        for _ in reader:
            total_rows += 1
            if total_rows % 500_000 == 0:
                print(f"Scanned {total_rows:,} CSV rows...", flush=True)
        return total_rows


def get_database_url() -> str:
    load_dotenv(ROOT_DIR / ".env")
    database_url = os.getenv("SUPABASE_DB_URL") or os.getenv("SUPABASE_URL")
    if not database_url:
        raise ValueError("Set SUPABASE_DB_URL in the environment or project .env file")
    return database_url


def import_csv(csv_path: Path, database_url: str, truncate: bool) -> tuple[int, int]:
    print(f"Counting CSV rows in {csv_path.name}...", flush=True)
    total_rows = count_data_rows(csv_path)
    print(f"Found {total_rows:,} CSV rows; starting import.", flush=True)
    imported_rows = 0
    failed_rows = 0
    processed_rows = 0
    import_started_at = monotonic()

    def report_progress() -> None:
        elapsed = max(monotonic() - import_started_at, 0.001)
        rate = processed_rows / elapsed
        remaining = (total_rows - processed_rows) / rate if rate else 0
        print(
            f"Imported {imported_rows:,} / {total_rows:,} rows | "
            f"processed {processed_rows:,} | failed {failed_rows:,} | "
            f"{rate:,.0f} rows/s | elapsed {format_duration(elapsed)} | "
            f"ETA {format_duration(remaining)}",
            flush=True,
        )

    with psycopg.connect(database_url) as connection:
        if truncate:
            with connection.transaction():
                connection.execute("TRUNCATE TABLE transactions RESTART IDENTITY")

        with csv_path.open("r", newline="", encoding="utf-8-sig") as source:
            reader = csv.reader(source, strict=True)
            next(reader)
            chunk: list[tuple] = []
            rows_in_chunk = 0

            def write_chunk() -> None:
                nonlocal imported_rows
                if chunk:
                    with connection.transaction():
                        with connection.cursor() as cursor:
                            with cursor.copy(COPY_SQL) as copy:
                                for values in chunk:
                                    copy.write_row(values)
                    imported_rows += len(chunk)

            for row in reader:
                rows_in_chunk += 1
                try:
                    chunk.append(parse_row(row))
                except (ValueError, OverflowError):
                    failed_rows += 1

                if rows_in_chunk == CHUNK_SIZE:
                    write_chunk()
                    processed_rows += rows_in_chunk
                    report_progress()
                    chunk.clear()
                    rows_in_chunk = 0

            if rows_in_chunk:
                write_chunk()
                processed_rows += rows_in_chunk
                report_progress()

    return imported_rows, failed_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"CSV input path (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="remove existing transactions before importing",
    )
    args = parser.parse_args()

    try:
        if not args.csv.is_file():
            raise FileNotFoundError(f"CSV file not found: {args.csv}")
        imported_rows, failed_rows = import_csv(
            args.csv, get_database_url(), args.truncate
        )
        print(f"Total imported rows: {imported_rows}")
        print(f"Total failed rows: {failed_rows}")
    except (OSError, ValueError, csv.Error, psycopg.Error) as error:
        print(f"Import failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())