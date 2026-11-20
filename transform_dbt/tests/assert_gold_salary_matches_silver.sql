with silver_salary as (
    select
        source_name,
        job_id_nk,
        posted_date,
        salary_min_usd,
        salary_max_usd,
        salary_status
    from {{ ref('silver_jobs_unified') }}
    where posted_date is not null
),

gold_salary as (
    select
        source_name,
        job_id_nk,
        posted_date,
        salary_min_usd,
        salary_max_usd,
        salary_status
    from {{ ref('fact_job_postings') }}
)

select
    coalesce(silver.source_name, gold.source_name)                as source_name,
    coalesce(silver.job_id_nk, gold.job_id_nk)                    as job_id_nk,
    coalesce(silver.posted_date, gold.posted_date)                as posted_date
from silver_salary silver
full outer join gold_salary gold
    on gold.source_name = silver.source_name
   and gold.job_id_nk = silver.job_id_nk
   and gold.posted_date = silver.posted_date
where silver.job_id_nk is null
   or gold.job_id_nk is null
   or gold.salary_min_usd is distinct from silver.salary_min_usd
   or gold.salary_max_usd is distinct from silver.salary_max_usd
   or gold.salary_status is distinct from silver.salary_status
