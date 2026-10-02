# Transaction Dataset Import

## Create the Supabase table

In the Supabase SQL Editor, run the contents of `database/schema.sql`. It creates the `transactions` table and the four indexes used for timestamp and account lookups.

## Install dependencies

From the project directory, install Python 3.10 or newer and run:

```sh
python3 -m pip install "psycopg[binary]" python-dotenv
```

## Configure `.env`

Copy `.env.example` to `.env` and replace `[YOUR-PASSWORD]` with the database password from Supabase. The importer reads `SUPABASE_DB_URL` from that file; keep the real `.env` private.

## Run the import

From the project directory, run:

```sh
python3 database/import_transactions.py
```

The script appends records. To replace existing rows before a fresh full import, run `python3 database/import_transactions.py --truncate`.

The CSV is read as a stream and processed in chunks of 50,000 records. Each valid chunk is bulk-loaded with PostgreSQL `COPY`; invalid records are skipped and counted. The terminal reports scan progress, then after each committed chunk prints imported/processed/failed counts, throughput, elapsed time, and an estimated time remaining. The original CSV is never modified. Timezone-free source timestamps are interpreted as UTC.

## Verify the import

Run:

```sh
python3 database/verify_transactions.py
```

The script reports the total row count, laundering count, timestamp range, NULL counts, and a sample of 10 rows. Compare the total transaction count with the importer's successful-row total.