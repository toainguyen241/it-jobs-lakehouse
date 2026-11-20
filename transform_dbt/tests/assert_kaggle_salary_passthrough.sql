select
    s.job_id_nk,
    s.salary_min_usd,
    s.salary_max_usd,
    b.salary_usd
from {{ ref('silver_jobs_unified') }} as s
join {{ source('bronze', 'raw_jobs_kaggle_global_ai_2025') }} as b
    on s.job_id_nk = b.job_id
where s.source_name = 'kaggle'
  and (
      s.salary_min_usd is distinct from b.salary_usd
      or s.salary_max_usd is distinct from b.salary_usd
  )
