with mart_count as (
    select coalesce(sum(job_count), 0) as row_count
    from {{ ref('mart_job_market_overview') }}
),

fact_count as (
    select count(*) as row_count
    from {{ ref('fact_job_postings') }} f
    where {{ in_crawl_scope('f') }}
)

select
    mart_count.row_count as mart_rows,
    fact_count.row_count as fact_rows
from mart_count
cross join fact_count
where mart_count.row_count <> fact_count.row_count
