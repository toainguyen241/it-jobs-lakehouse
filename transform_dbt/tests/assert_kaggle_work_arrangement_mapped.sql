with expected as (
    select
        case silver_jobs.remote_ratio
            when 100 then 'Remote'
            when 50 then 'Hybrid'
            when 0 then 'On-site'
        end as work_arrangement,
        count(*) as job_count
    from {{ ref('fact_job_postings') }} facts
    inner join {{ ref('silver_jobs_unified') }} silver_jobs
        on silver_jobs.source_name = facts.source_name
       and silver_jobs.job_id_nk = facts.job_id_nk
       and silver_jobs.posted_date = facts.posted_date
    where facts.source_name = 'kaggle'
      and silver_jobs.remote_ratio in (0, 50, 100)
    group by 1
),

actual as (
    select work_arrangement, sum(job_count) as job_count
    from {{ ref('mart_jobs_by_work_type') }}
    where source_name = 'kaggle'
      and work_arrangement <> 'Unknown'
    group by 1
)

select
    coalesce(expected.work_arrangement, actual.work_arrangement)
    || ': expected ' || coalesce(expected.job_count, 0)
    || ', got ' || coalesce(actual.job_count, 0) as failure
from expected
full outer join actual
    on actual.work_arrangement = expected.work_arrangement
where coalesce(expected.job_count, 0) <> coalesce(actual.job_count, 0)
