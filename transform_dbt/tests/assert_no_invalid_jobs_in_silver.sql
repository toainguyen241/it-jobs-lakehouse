select job_id_nk, source_name, salary_text_raw
from {{ ref('silver_jobs_unified') }}
where salary_status = 'invalid'
