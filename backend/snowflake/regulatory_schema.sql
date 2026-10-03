CREATE DATABASE IF NOT EXISTS RAILS_DB;
USE DATABASE RAILS_DB;

CREATE SCHEMA IF NOT EXISTS REGULATORY;
USE SCHEMA REGULATORY;

CREATE STAGE IF NOT EXISTS REGULATORY_STAGE
    DIRECTORY = (ENABLE = TRUE)
    COMMENT = 'Internal stage holding authoritative regulatory PDFs';

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
);

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
);

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
    );
