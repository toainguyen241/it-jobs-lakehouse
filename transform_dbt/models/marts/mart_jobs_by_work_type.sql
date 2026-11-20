{{ config(materialized='view') }}

with normalized as (
    select
        extract(year from facts.posted_date)::integer as market_year,
        facts.source_type,
        facts.source_name,
        {{ classify_job_market('facts.source_name', 'locations.country') }} as market_scope,
        {{ normalize_employment_type('facts.employment_type') }} as employment_type,
        {{ classify_work_arrangement(
            'facts.source_name',
            'facts.employment_type',
            'locations.city_nk',
            'locations.country',
            'silver_jobs.remote_ratio'
        ) }} as work_arrangement,
        facts.job_sk,
        facts.company_sk,
        case
            when facts.salary_status in ('scraped', 'corrected') then (
                coalesce(facts.salary_min_usd, facts.salary_max_usd)
                + coalesce(facts.salary_max_usd, facts.salary_min_usd)
            ) / 2.0
        end as salary_mid_usd
    from {{ ref('fact_job_postings') }} facts
    left join {{ ref('dim_locations') }} locations
        on locations.location_sk = facts.location_sk
    left join {{ ref('silver_jobs_unified') }} silver_jobs
        on silver_jobs.source_name = facts.source_name
       and silver_jobs.job_id_nk = facts.job_id_nk
       and silver_jobs.posted_date = facts.posted_date
    where {{ in_market_year_scope('facts') }}
),

aggregated as (
    select
        market_year,
        source_type,
        source_name,
        market_scope,
        employment_type,
        work_arrangement,
        count(*) as job_count,
        count(distinct company_sk) as company_count,
        count(salary_mid_usd) as jobs_with_salary,
        round(avg(salary_mid_usd), 2) as avg_salary_usd,
        round(
            percentile_cont(0.5) within group (order by salary_mid_usd)::numeric,
            2
        ) as median_salary_usd
    from normalized
    group by
        market_year,
        source_type,
        source_name,
        market_scope,
        employment_type,
        work_arrangement
)

select
    *,
    round(
        job_count::numeric
        / sum(job_count) over (partition by market_year, source_name),
        4
    ) as job_share_within_source_year,
    round(jobs_with_salary::numeric / nullif(job_count, 0), 4)
        as salary_coverage_rate
from aggregated
