{{ config(materialized='view') }}

with parsed as (
    select
        job_id_nk,
        source_name,
        scraped_at,
        job_title,
        company_name,
        posted_date,
        salary_text as salary_text_raw,
        {{ crawled_salary_correction_reason('source_name', 'salary_text') }}
            as source_correction_reason,
        silver.parse_salary_range(
            {{ normalized_crawled_salary_text('source_name', 'salary_text') }}
        ) as salary_parsed
    from {{ ref('stg_crawled') }}
)

select
    source_name,
    job_id_nk,
    scraped_at,
    job_title,
    company_name,
    posted_date,
    salary_text_raw,
    'salary_parser'::text as rejection_stage,
    coalesce(
        (salary_parsed).correction_reason,
        source_correction_reason,
        'invalid_salary'
    ) as rejection_reason
from parsed
where (salary_parsed).salary_status = 'invalid'
