{{ config(materialized = 'view') }}

with jobs_with_skills as (
    select distinct job_sk, posted_date
    from {{ ref('canonical_job_skills') }}
),

fact_metrics as (
    select
        f.source_name,
        count(*) as total_jobs,
        count(*) filter (where f.company_sk is null) as jobs_missing_company,
        count(*) filter (where f.location_sk is null) as jobs_missing_location,
        count(*) filter (
            where coalesce(f.posted_date_is_estimated, false)
        ) as jobs_estimated_posted_date,
        count(*) filter (
            where f.salary_status in ('scraped', 'corrected')
        ) as jobs_with_salary,
        count(*) filter (
            where skill_jobs.job_sk is null
        ) as jobs_without_skills
    from {{ ref('fact_job_postings') }} f
    left join jobs_with_skills skill_jobs
        on skill_jobs.job_sk = f.job_sk
       and skill_jobs.posted_date = f.posted_date
    where {{ in_crawl_scope('f') }}
    group by f.source_name
),

rejected_metrics as (
    select source_name, count(*) as jobs_with_invalid_salary
    from {{ ref('rejected_jobs') }}
    group by source_name
),

missing_date_metrics as (
    select source_name, count(*) as jobs_missing_posted_date
    from {{ ref('silver_jobs_unified') }}
    where posted_date is null
        and source_type = 'crawled'
    group by source_name
),

out_of_scope_metrics as (
    select f.source_name, count(*) as jobs_outside_crawl_year
    from {{ ref('fact_job_postings') }} f
    where f.source_type = 'crawled'
        and not {{ in_crawl_scope('f') }}
    group by f.source_name
),

sources as (
    select source_name from fact_metrics
    union
    select source_name from rejected_metrics
    union
    select source_name from missing_date_metrics
    union
    select source_name from out_of_scope_metrics
)

select
    sources.source_name,
    coalesce(facts.total_jobs, 0) as total_jobs,
    coalesce(facts.jobs_missing_company, 0) as jobs_missing_company,
    coalesce(facts.jobs_missing_location, 0) as jobs_missing_location,
    coalesce(facts.jobs_with_salary, 0) as jobs_with_salary,
    coalesce(facts.jobs_estimated_posted_date, 0) as jobs_estimated_posted_date,
    coalesce(rejected.jobs_with_invalid_salary, 0) as jobs_with_invalid_salary,
    coalesce(out_of_scope.jobs_outside_crawl_year, 0) as jobs_outside_crawl_year,
    coalesce(missing_date.jobs_missing_posted_date, 0) as jobs_missing_posted_date,
    coalesce(facts.jobs_without_skills, 0) as jobs_without_skills,
    coalesce(
        round(facts.jobs_with_salary::numeric / nullif(facts.total_jobs, 0), 4),
        0
    ) as salary_coverage_rate,
    coalesce(
        round(
            (facts.total_jobs - facts.jobs_without_skills)::numeric
            / nullif(facts.total_jobs, 0),
            4
        ),
        0
    ) as skills_coverage_rate
from sources
left join fact_metrics facts using (source_name)
left join rejected_metrics rejected using (source_name)
left join missing_date_metrics missing_date using (source_name)
left join out_of_scope_metrics out_of_scope using (source_name)
