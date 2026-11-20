select job_sk, experience_level
from {{ ref('mart_data_engineer_jobs') }}
where experience_level is null
    or length(experience_level) > 30
