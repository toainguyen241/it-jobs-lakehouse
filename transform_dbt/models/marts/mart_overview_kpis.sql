select count(*) as total_jobs,
    count(distinct source_name) as source_count,
    count(distinct company_sk) as company_count,
    count(distinct location_sk) as location_count,
    count(*) filter (
        where salary_status in ('scraped', 'corrected')
    ) as jobs_with_salary,
    max(posted_date) filter (
        where not coalesce(posted_date_is_estimated, false)
    ) as latest_posted_date,
    max(loaded_at) as last_loaded_at,
    (
        select max(scraped_at)
        from {{ source('bronze', 'raw_jobs_crawled') }}
    ) as last_crawled_at
from {{ ref('fact_job_postings') }} f
where {{ in_crawl_scope('f') }}