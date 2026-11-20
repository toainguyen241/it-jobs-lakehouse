-- =================================================================
-- IT Jobs Data Lakehouse 
-- Thứ tự: schemas -> Bronze staging tables -> Gold star schema DDL.
-- =================================================================
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
-- Text normalization and trigram similarity used by the review-only cross-source duplicate candidate mart.
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- ============================================================================
-- BRONZE LAYER -- staging thô, giữ nguyên cấu trúc gần với nguồn nhất có thể.
-- ============================================================================
-- Crawled sources -- lưu JSONB vì schema có thể lệch nhẹ giữa các website, tránh phải ALTER TABLE liên tục khi site đổi cấu trúc HTML/field.
CREATE TABLE IF NOT EXISTS bronze.raw_jobs_crawled (
    id BIGSERIAL PRIMARY KEY,
    job_id_nk TEXT NOT NULL,
    source_name TEXT NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_raw_jobs_crawled_nk UNIQUE (job_id_nk, source_name)
);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_crawled_payload ON bronze.raw_jobs_crawled USING GIN (payload);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_crawled_source ON bronze.raw_jobs_crawled (source_name);
CREATE INDEX IF NOT EXISTS idx_raw_jobs_crawled_source_loaded_at ON bronze.raw_jobs_crawled (source_name, loaded_at DESC);
-- Registry cho incremental crawl. Lưu cả job đã load và job đã chủ động loại (ví dụ non-IT) để crawler không mở lại cùng detail URL ở các DAG run sau.
-- Lỗi network/parser không được ghi vào đây để run sau vẫn retry được.
CREATE TABLE IF NOT EXISTS bronze.crawl_job_state (
    source_name TEXT NOT NULL,
    job_id_nk TEXT NOT NULL,
    job_url TEXT,
    status TEXT NOT NULL,
    reason TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_name, job_id_nk),
    CONSTRAINT ck_crawl_job_state_status CHECK (
        status IN ('loaded', 'rejected', 'failed', 'quarantined')
    )
);
CREATE INDEX IF NOT EXISTS idx_crawl_job_state_status ON bronze.crawl_job_state (source_name, status);
INSERT INTO bronze.crawl_job_state (source_name, job_id_nk, status)
SELECT source_name,
    job_id_nk,
    'loaded'
FROM bronze.raw_jobs_crawled ON CONFLICT (source_name, job_id_nk) DO NOTHING;
-- Kaggle "Global AI Job Market & Salary Trends 2025".
CREATE TABLE IF NOT EXISTS bronze.raw_jobs_kaggle_global_ai_2025 (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT,
    job_title TEXT,
    salary_usd NUMERIC,
    salary_currency TEXT,
    experience_level TEXT,
    employment_type TEXT,
    company_location TEXT,
    company_size TEXT,
    employee_residence TEXT,
    remote_ratio INTEGER,
    required_skills TEXT,
    education_required TEXT,
    years_experience NUMERIC,
    industry TEXT,
    posting_date DATE,
    application_deadline DATE,
    job_description_length INTEGER,
    benefits_score NUMERIC,
    company_name TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- ===================================================================
-- GOLD LAYER -- star schema (Kimball), sẵn sàng cho query BI/analyst.
-- ===================================================================
CREATE TABLE IF NOT EXISTS gold.dim_date (
    date_sk DATE PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS gold.dim_companies (
    company_sk SERIAL PRIMARY KEY,
    company_nk TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    company_size TEXT,
    industry TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS gold.dim_locations (
    location_sk SERIAL PRIMARY KEY,
    city_nk TEXT,
    country TEXT NOT NULL,
    CONSTRAINT uq_dim_locations UNIQUE NULLS NOT DISTINCT (city_nk, country)
);
CREATE TABLE IF NOT EXISTS gold.dim_skills (
    skill_sk SERIAL PRIMARY KEY,
    skill_name TEXT NOT NULL UNIQUE
);
-- Fact table -- PARTITION BY RANGE(posted_date).
-- Composite PK (job_sk, posted_date) BẮT BUỘC vì Postgres yêu cầu cột partition key phải nằm trong mọi unique constraint/PK của bảng partition.
CREATE TABLE IF NOT EXISTS gold.fact_job_postings (
    job_sk BIGINT GENERATED ALWAYS AS IDENTITY,
    posted_date DATE NOT NULL,
    job_id_nk TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    company_sk INTEGER REFERENCES gold.dim_companies (company_sk),
    location_sk INTEGER REFERENCES gold.dim_locations (location_sk),
    job_title TEXT NOT NULL,
    salary_min_usd NUMERIC,
    salary_max_usd NUMERIC,
    salary_status TEXT,
    experience_level TEXT,
    employment_type TEXT,
    years_experience NUMERIC,
    posted_date_is_estimated BOOLEAN NOT NULL DEFAULT false,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (job_sk, posted_date)
) PARTITION BY RANGE (posted_date);
-- Bootstrap partition cho tháng của dataset hiện tại. Mỗi dbt invocation tiếp tục bảo đảm partition tháng hiện tại và tháng kế tiếp tồn tại qua macro ensure_fact_month_partitions.
CREATE TABLE IF NOT EXISTS gold.fact_job_postings_2026_08 PARTITION OF gold.fact_job_postings FOR
VALUES
FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS gold.fact_job_postings_default PARTITION OF gold.fact_job_postings DEFAULT;
ALTER TABLE gold.fact_job_postings
ALTER COLUMN source_name
SET NOT NULL,
    ALTER COLUMN job_title
SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fact_job_postings_company ON gold.fact_job_postings (company_sk);
CREATE INDEX IF NOT EXISTS idx_fact_job_postings_location ON gold.fact_job_postings (location_sk);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_job_postings_nk ON gold.fact_job_postings (source_name, job_id_nk, posted_date);
-- Bridge table cho quan hệ many-to-many job <-> skill.
CREATE TABLE IF NOT EXISTS gold.bridge_job_skills (
    job_sk BIGINT NOT NULL,
    posted_date DATE NOT NULL,
    skill_sk INTEGER NOT NULL REFERENCES gold.dim_skills (skill_sk),
    PRIMARY KEY (job_sk, posted_date, skill_sk),
    FOREIGN KEY (job_sk, posted_date) REFERENCES gold.fact_job_postings (job_sk, posted_date)
);