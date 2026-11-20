select job_sk, posted_date, skill_name, count(*) as row_count
from {{ ref('canonical_job_skills') }}
group by job_sk, posted_date, skill_name
having count(*) > 1
