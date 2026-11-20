with silver_count as (
    select count(*) as row_count
    from {{ ref('silver_jobs_unified') }}
    where posted_date is not null
),

gold_count as (
    select count(*) as row_count
    from {{ ref('fact_job_postings') }}
)

select
    silver_count.row_count as silver_rows,
    gold_count.row_count as gold_rows
from silver_count
cross join gold_count
where silver_count.row_count <> gold_count.row_count
