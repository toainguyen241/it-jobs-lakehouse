select
    job_id_nk,
    source_type,
    salary_status
from {{ ref('silver_jobs_unified') }}
where salary_status in ('scraped', 'corrected')
  and salary_min_usd is null
  and salary_max_usd is null
