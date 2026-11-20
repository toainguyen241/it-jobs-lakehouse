with mart_totals as (
    select sum(job_count) as job_count
    from {{ ref('mart_jobs_by_work_type') }}
),

fact_totals as (
    select count(*) as job_count
    from {{ ref('fact_job_postings') }} f
    where {{ in_market_year_scope('f') }}
),

invalid_shares as (
    select market_year, source_name
    from {{ ref('mart_jobs_by_work_type') }}
    group by market_year, source_name
    having abs(sum(job_share_within_source_year) - 1) > 0.001
),

duplicate_grain as (
    select
        market_year,
        source_type,
        source_name,
        market_scope,
        employment_type,
        work_arrangement
    from {{ ref('mart_jobs_by_work_type') }}
    group by
        market_year,
        source_type,
        source_name,
        market_scope,
        employment_type,
        work_arrangement
    having count(*) > 1
)

select 'job total mismatch' as failure
from mart_totals cross join fact_totals
where mart_totals.job_count <> fact_totals.job_count
union all
select 'invalid source-year share: ' || source_name || '/' || market_year
from invalid_shares
union all
select
    'duplicate grain: ' || source_name || '/' || market_year
    || '/' || market_scope || '/' || employment_type || '/' || work_arrangement
from duplicate_grain
