with duplicate_grain as (
    select job_sk, posted_date
    from {{ ref('mart_data_engineer_jobs') }}
    group by job_sk, posted_date
    having count(*) > 1
),

expected_count as (
    select count(*) as job_count
    from {{ ref('fact_job_postings') }} f
    where {{ in_market_year_scope('f') }}
        and unaccent(lower(job_title))
        ~ '(^|[^a-z0-9])data[ -]*engineer(ing)?([^a-z0-9]|$)'
),

actual_count as (
    select count(*) as job_count
    from {{ ref('mart_data_engineer_jobs') }}
)

select 'duplicate job grain: ' || job_sk || '/' || posted_date as failure
from duplicate_grain
union all
select 'Data Engineer job total mismatch'
from expected_count cross join actual_count
where expected_count.job_count <> actual_count.job_count
union all
select 'non-DE title: ' || job_title
from {{ ref('mart_data_engineer_jobs') }}
where unaccent(lower(job_title))
    !~ '(^|[^a-z0-9])data[ -]*engineer(ing)?([^a-z0-9]|$)'
