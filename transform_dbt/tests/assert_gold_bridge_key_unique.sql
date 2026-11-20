select
    job_sk,
    posted_date,
    skill_sk,
    count(*) as duplicate_count
from {{ ref('bridge_job_skills') }}
group by job_sk, posted_date, skill_sk
having count(*) > 1
