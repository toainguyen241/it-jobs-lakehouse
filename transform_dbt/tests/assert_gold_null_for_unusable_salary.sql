select *
from {{ ref('fact_job_postings') }}
where salary_status in ('invalid', 'not_disclosed')
  and (
      salary_min_usd is not null
      or salary_max_usd is not null
  )
