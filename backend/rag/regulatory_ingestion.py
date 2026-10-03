from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import PyPDF2

from backend.snowflake.connection import get_snowflake_connection

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parents[1] / "regulatory_docs"
CORPUS_CACHE_FILE = DOCS_DIR / "regulatory_corpus.json"

REGULATORY_DOCUMENTS_META = [
    {
        "document_id": "fatf_recommendations",
        "document_name": "FATF Recommendations (Updated June 2026)",
        "file_name": "fatf-recommendations-2012.pdf",
        "authority": "FATF",
        "jurisdiction": "GLOBAL",
        "document_type": "AML_CFT_STANDARD",
        "publication_date": "2012 (Updated June 2026)",
        "source_url": "https://www.fatf-gafi.org/publications/fatfrecommendations/documents/fatf-recommendations.html",
        "description": "International Standards on Combating Money Laundering and the Financing of Terrorism & Proliferation: The FATF Recommendations (Adopted Feb 2012, Updated June 2026).",
        "page_count": 151,
    },
    {
        "document_id": "fincen_sar_efiling",
        "document_name": "FinCEN SAR Electronic Filing Instructions",
        "file_name": "FinCEN SAR ElectronicFilingInstructions- Stand Alone doc.pdf",
        "authority": "FinCEN",
        "jurisdiction": "US",
        "document_type": "SAR_FILING_GUIDANCE",
        "publication_date": "October 2012 (Version 1.2)",
        "source_url": "https://www.fincen.gov/base-efiling-instructions",
        "description": "FinCEN Suspicious Activity Report (FinCEN SAR) Electronic Filing Instructions - Release Date October 2012 - Version 1.2.",
        "page_count": 36,
    },
    {
        "document_id": "fincen_sar_narrative",
        "document_name": "FinCEN SAR Narrative Guidance",
        "file_name": "sarnarrcompletguidfinal_112003.pdf",
        "authority": "FinCEN",
        "jurisdiction": "US",
        "document_type": "SAR_NARRATIVE_GUIDANCE",
        "publication_date": "November 2003",
        "source_url": "https://www.fincen.gov/sar-narrative-guidance",
        "description": "Suggestions for Preparing a Complete and Sufficient Suspicious Activity Report Narrative - FinCEN Guidance November 2003.",
        "page_count": 33,
    },
]


def extract_fatf_chunks(pdf_path: Path) -> list[dict[str, Any]]:
    reader = PyPDF2.PdfReader(str(pdf_path))
    chunks: list[dict[str, Any]] = []
    current_section = "General Principles & Introduction"
    chunk_idx = 1

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        text = page.extract_text() or ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        cur_lines: list[str] = []
        for line in lines:
            if re.match(r"^(RECOMMENDATION\s+\d+|[A-G]\.\s+[A-Z\s]+|INTERPRETIVE\s+NOTE\s+TO\s+RECOMMENDATION\s+\d+|THE\s+FATF\s+RECOMMENDATIONS)", line, re.IGNORECASE):
                if not any(skip in line for skip in ["CONTENTS", "INTERNATIONAL STANDARDS ON COMBATING"]):
                    current_section = line[:120]

            if any(h in line for h in ["THE FATF RECOMMENDATIONS", "INTERNATIONAL STANDARDS ON COMBATING", "FINANCIAL ACTION TASK FORCE"]):
                continue
            if re.match(r"^\d+\s+[\uF8E9\uf8e9]?\s*2012", line) or re.match(r"^[\uF8E9\uf8e9]?\s*2012-\s*2026\s+\d+", line):
                continue

            cur_lines.append(line)
            if len(" ".join(cur_lines)) >= 750:
                chunk_str = " ".join(cur_lines).strip()
                if len(chunk_str) > 80:
                    chunks.append({
                        "chunk_id": f"reg_fatf_{chunk_idx:03d}",
                        "document_id": "fatf_recommendations",
                        "document_name": "FATF Recommendations (Updated June 2026)",
                        "authority": "FATF",
                        "jurisdiction": "GLOBAL",
                        "document_type": "AML_CFT_STANDARD",
                        "section": current_section,
                        "page_number": page_num,
                        "chunk_text": chunk_str,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    chunk_idx += 1
                cur_lines = []

        if cur_lines:
            chunk_str = " ".join(cur_lines).strip()
            if len(chunk_str) > 80:
                chunks.append({
                    "chunk_id": f"reg_fatf_{chunk_idx:03d}",
                    "document_id": "fatf_recommendations",
                    "document_name": "FATF Recommendations (Updated June 2026)",
                    "authority": "FATF",
                    "jurisdiction": "GLOBAL",
                    "document_type": "AML_CFT_STANDARD",
                    "section": current_section,
                    "page_number": page_num,
                    "chunk_text": chunk_str,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                chunk_idx += 1

    return chunks


def extract_efiling_chunks(pdf_path: Path) -> list[dict[str, Any]]:
    reader = PyPDF2.PdfReader(str(pdf_path))
    chunks: list[dict[str, Any]] = []
    current_section = "Electronic Filing Requirements & General Instructions"
    chunk_idx = 1

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        text = page.extract_text() or ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        cur_lines: list[str] = []
        for line in lines:
            if re.match(r"^(Part\s+[I|V|X]+|PART\s+[I|V|X]+|Item\s+\d+|General\s+Instructions|Electronic\s+Filing\s+Requirements)", line, re.IGNORECASE):
                current_section = line[:100]

            if "Financial Crimes Enforcement Network" in line or "Electronic Filing Requirements for the FinCEN" in line:
                continue
            if re.match(r"^\d+\s+FinCEN SAR Electronic Filing", line) or re.match(r"^\d+\s*$", line):
                continue

            cur_lines.append(line)
            if len(" ".join(cur_lines)) >= 700:
                chunk_str = " ".join(cur_lines).strip()
                if len(chunk_str) > 80:
                    chunks.append({
                        "chunk_id": f"reg_fincen_efile_{chunk_idx:03d}",
                        "document_id": "fincen_sar_efiling",
                        "document_name": "FinCEN SAR Electronic Filing Instructions",
                        "authority": "FinCEN",
                        "jurisdiction": "US",
                        "document_type": "SAR_FILING_GUIDANCE",
                        "section": current_section,
                        "page_number": page_num,
                        "chunk_text": chunk_str,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    chunk_idx += 1
                cur_lines = []

        if cur_lines:
            chunk_str = " ".join(cur_lines).strip()
            if len(chunk_str) > 80:
                chunks.append({
                    "chunk_id": f"reg_fincen_efile_{chunk_idx:03d}",
                    "document_id": "fincen_sar_efiling",
                    "document_name": "FinCEN SAR Electronic Filing Instructions",
                    "authority": "FinCEN",
                    "jurisdiction": "US",
                    "document_type": "SAR_FILING_GUIDANCE",
                    "section": current_section,
                    "page_number": page_num,
                    "chunk_text": chunk_str,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                chunk_idx += 1

    return chunks


def extract_narrative_chunks(pdf_path: Path) -> list[dict[str, Any]]:
    reader = PyPDF2.PdfReader(str(pdf_path))
    chunks: list[dict[str, Any]] = []
    current_section = "Introduction & Overview"
    chunk_idx = 1

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        text = page.extract_text() or ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        cur_lines: list[str] = []
        for line in lines:
            if any(sec in line for sec in ["Collecting Information", "Organizing Information", "SARs Filed by Depository", "SARs Filed by Money Services", "SARs Filed by Broker-Dealers", "SARs Filed by Casinos", "Examples of Sufficient", "Introduction"]):
                current_section = line[:100]

            if "Financial Crimes Enforcement Network" in line or line == "Table of Contents":
                continue
            if re.match(r"^\d+\s*$", line) or re.match(r"^November 2003$", line):
                continue

            cur_lines.append(line)
            if len(" ".join(cur_lines)) >= 700:
                chunk_str = " ".join(cur_lines).strip()
                if len(chunk_str) > 80:
                    chunks.append({
                        "chunk_id": f"reg_fincen_narrative_{chunk_idx:03d}",
                        "document_id": "fincen_sar_narrative",
                        "document_name": "FinCEN SAR Narrative Guidance",
                        "authority": "FinCEN",
                        "jurisdiction": "US",
                        "document_type": "SAR_NARRATIVE_GUIDANCE",
                        "section": current_section,
                        "page_number": page_num,
                        "chunk_text": chunk_str,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    chunk_idx += 1
                cur_lines = []

        if cur_lines:
            chunk_str = " ".join(cur_lines).strip()
            if len(chunk_str) > 80:
                chunks.append({
                    "chunk_id": f"reg_fincen_narrative_{chunk_idx:03d}",
                    "document_id": "fincen_sar_narrative",
                    "document_name": "FinCEN SAR Narrative Guidance",
                    "authority": "FinCEN",
                    "jurisdiction": "US",
                    "document_type": "SAR_NARRATIVE_GUIDANCE",
                    "section": current_section,
                    "page_number": page_num,
                    "chunk_text": chunk_str,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                chunk_idx += 1

    return chunks


def build_regulatory_corpus() -> dict[str, Any]:
    fatf_path = DOCS_DIR / "fatf-recommendations-2012.pdf"
    efile_path = DOCS_DIR / "FinCEN SAR ElectronicFilingInstructions- Stand Alone doc.pdf"
    narrative_path = DOCS_DIR / "sarnarrcompletguidfinal_112003.pdf"

    fatf_chunks = extract_fatf_chunks(fatf_path)
    efile_chunks = extract_efiling_chunks(efile_path)
    narrative_chunks = extract_narrative_chunks(narrative_path)

    all_chunks = fatf_chunks + efile_chunks + narrative_chunks

    corpus = {
        "metadata": REGULATORY_DOCUMENTS_META,
        "counts": {
            "fatf": len(fatf_chunks),
            "efile": len(efile_chunks),
            "narrative": len(narrative_chunks),
            "total": len(all_chunks),
        },
        "chunks": all_chunks,
    }

    with open(CORPUS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)

    logger.info(f"Built regulatory corpus with {len(all_chunks)} chunks saved to {CORPUS_CACHE_FILE}")
    return corpus


def sync_to_snowflake(corpus: dict[str, Any] | None = None) -> dict[str, Any]:
    if corpus is None:
        corpus = build_regulatory_corpus()

    conn = get_snowflake_connection()
    if conn is None:
        return {"status": "skipped", "reason": "No Snowflake connection available"}

    cur = conn.cursor()
    try:
        cur.execute("USE DATABASE RAILS_DB")
        cur.execute("CREATE SCHEMA IF NOT EXISTS REGULATORY")
        cur.execute("USE SCHEMA REGULATORY")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS REGULATORY_DOCUMENTS (
                document_id VARCHAR(100) PRIMARY KEY,
                document_name VARCHAR(255) NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                authority VARCHAR(50) NOT NULL,
                jurisdiction VARCHAR(50) NOT NULL,
                document_type VARCHAR(50) NOT NULL,
                publication_date VARCHAR(50),
                source_url VARCHAR(500),
                description VARCHAR(1000),
                page_count INTEGER,
                created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)

        for doc in corpus["metadata"]:
            cur.execute("""
                MERGE INTO REGULATORY_DOCUMENTS AS target
                USING (SELECT
                    %(document_id)s AS document_id,
                    %(document_name)s AS document_name,
                    %(file_name)s AS file_name,
                    %(authority)s AS authority,
                    %(jurisdiction)s AS jurisdiction,
                    %(document_type)s AS document_type,
                    %(publication_date)s AS publication_date,
                    %(source_url)s AS source_url,
                    %(description)s AS description,
                    %(page_count)s AS page_count
                ) AS src
                ON target.document_id = src.document_id
                WHEN MATCHED THEN UPDATE SET
                    document_name = src.document_name,
                    file_name = src.file_name,
                    authority = src.authority,
                    jurisdiction = src.jurisdiction,
                    document_type = src.document_type,
                    publication_date = src.publication_date,
                    source_url = src.source_url,
                    description = src.description,
                    page_count = src.page_count
                WHEN NOT MATCHED THEN INSERT (
                    document_id, document_name, file_name, authority,
                    jurisdiction, document_type, publication_date,
                    source_url, description, page_count
                ) VALUES (
                    src.document_id, src.document_name, src.file_name, src.authority,
                    src.jurisdiction, src.document_type, src.publication_date,
                    src.source_url, src.description, src.page_count
                )
            """, doc)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS REGULATORY_CHUNKS (
                chunk_id VARCHAR(100) PRIMARY KEY,
                document_id VARCHAR(100) NOT NULL,
                document_name VARCHAR(255) NOT NULL,
                authority VARCHAR(50) NOT NULL,
                jurisdiction VARCHAR(50) NOT NULL,
                document_type VARCHAR(50) NOT NULL,
                section VARCHAR(255),
                page_number INTEGER NOT NULL,
                chunk_text VARCHAR(16777216) NOT NULL,
                created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)

        cur.execute("TRUNCATE TABLE REGULATORY_CHUNKS")

        chunks = corpus["chunks"]
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            values_clause = ", ".join([
                f"(%(c_{idx}_id)s, %(c_{idx}_doc)s, %(c_{idx}_name)s, %(c_{idx}_auth)s, %(c_{idx}_jur)s, %(c_{idx}_type)s, %(c_{idx}_sec)s, %(c_{idx}_page)s, %(c_{idx}_text)s)"
                for idx in range(len(batch))
            ])
            params = {}
            for idx, c in enumerate(batch):
                params[f"c_{idx}_id"] = c["chunk_id"]
                params[f"c_{idx}_doc"] = c["document_id"]
                params[f"c_{idx}_name"] = c["document_name"]
                params[f"c_{idx}_auth"] = c["authority"]
                params[f"c_{idx}_jur"] = c["jurisdiction"]
                params[f"c_{idx}_type"] = c["document_type"]
                params[f"c_{idx}_sec"] = c["section"]
                params[f"c_{idx}_page"] = c["page_number"]
                params[f"c_{idx}_text"] = c["chunk_text"]

            cur.execute(f"""
                INSERT INTO REGULATORY_CHUNKS (
                    chunk_id, document_id, document_name, authority,
                    jurisdiction, document_type, section, page_number, chunk_text
                ) VALUES {values_clause}
            """, params)

        try:
            cur.execute("""
                CREATE OR REPLACE CORTEX SEARCH SERVICE REGULATORY_SEARCH_SERVICE
                    ON chunk_text
                    ATTRIBUTES document_id, document_name, authority, jurisdiction, document_type, section, page_number, chunk_id
                    WAREHOUSE = COMPUTE_WH
                    TARGET_LAG = '1 hour'
                    AS (
                        SELECT
                            chunk_id,
                            document_id,
                            document_name,
                            authority,
                            jurisdiction,
                            document_type,
                            section,
                            page_number,
                            chunk_text
                        FROM RAILS_DB.REGULATORY.REGULATORY_CHUNKS
                    )
            """)
            cortex_created = True
        except Exception as e:
            logger.warning(f"Could not create Cortex Search Service: {e}")
            cortex_created = False

        return {
            "status": "success",
            "documents_synced": len(corpus["metadata"]),
            "chunks_synced": len(corpus["chunks"]),
            "cortex_search_created": cortex_created,
        }
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Building local corpus...")
    corpus = build_regulatory_corpus()
    print(f"Chunks summary: {corpus['counts']}")
    print("Syncing to Snowflake...")
    res = sync_to_snowflake(corpus)
    print(f"Snowflake sync result: {res}")
