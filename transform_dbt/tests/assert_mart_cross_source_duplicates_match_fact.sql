with candidates as (
    select left_job_sk as job_sk, left_posted_date as posted_date
    from {{ ref('mart_cross_source_duplicates') }}
    union all
    select right_job_sk as job_sk, right_posted_date as posted_date
    from {{ ref('mart_cross_source_duplicates') }}
)

select candidates.*
from candidates
left join {{ ref('fact_job_postings') }} facts
    on facts.job_sk = candidates.job_sk
   and facts.posted_date = candidates.posted_date
where facts.job_sk is null
