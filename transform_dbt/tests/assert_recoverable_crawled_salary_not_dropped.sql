with recoverable_bronze as (
    select source_name, job_id_nk
    from {{ source('bronze', 'raw_jobs_crawled') }}
    where
        payload ->> 'salary_text' is null
        or trim(payload ->> 'salary_text') = ''
        or payload ->> 'salary_text' !~ '[0-9]'
        or (
            source_name = 'weworkremotely'
            and payload ->> 'salary_text' ~* '(USD|\$)'
        )
        or (
            source_name = 'itviec'
            and payload ->> 'salary_text' ~* '^\s*(?:up\s*to|upto|up|from|-)?\s*[0-9][0-9,.]*\s*$'
        )
),

silver_keys as (
    select source_name, job_id_nk
    from {{ ref('silver_jobs_unified') }}
)

select bronze.source_name, bronze.job_id_nk
from recoverable_bronze bronze
left join silver_keys silver
    on silver.source_name = bronze.source_name
   and silver.job_id_nk = bronze.job_id_nk
where silver.job_id_nk is null
