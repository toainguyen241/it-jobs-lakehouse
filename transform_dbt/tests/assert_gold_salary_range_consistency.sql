select *
from {{ ref('fact_job_postings') }}
where salary_min_usd is not null
  and salary_max_usd is not null
  and salary_min_usd > salary_max_usd
