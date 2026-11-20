select *
from {{ ref('silver_jobs_unified') }}
where salary_min_usd = 0
   or salary_max_usd = 0
