with mart_counts as (
    select source_name, total_jobs
    from {{ ref('mart_salary_by_source') }}
),

fact_counts as (
    select source_name, count(*) as total_jobs
    from {{ ref('fact_job_postings') }} f
    where {{ in_crawl_scope('f') }}
    group by source_name
)

select
    coalesce(mart.source_name, facts.source_name) as source_name
from mart_counts mart
full outer join fact_counts facts
    on facts.source_name = mart.source_name
where mart.source_name is null
   or facts.source_name is null
   or mart.total_jobs <> facts.total_jobs
