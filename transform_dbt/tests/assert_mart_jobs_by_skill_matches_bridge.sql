with mart_count as (
    select coalesce(sum(total_jobs), 0) as association_count
    from {{ ref('mart_jobs_by_skill') }}
),

canonical_count as (
    select count(*) as association_count
    from {{ ref('canonical_job_skills') }} skills
    inner join {{ ref('fact_job_postings') }} f
        on f.job_sk = skills.job_sk
       and f.posted_date = skills.posted_date
    where {{ in_crawl_scope('f') }}
)

select
    mart_count.association_count as mart_associations,
    canonical_count.association_count as canonical_associations
from mart_count
cross join canonical_count
where mart_count.association_count <> canonical_count.association_count
