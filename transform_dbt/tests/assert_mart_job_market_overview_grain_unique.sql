select
    posted_date,
    source_name,
    country,
    city,
    posted_date_is_estimated,
    count(*) as duplicate_count
from {{ ref('mart_job_market_overview') }}
group by posted_date, source_name, country, city, posted_date_is_estimated
having count(*) > 1
