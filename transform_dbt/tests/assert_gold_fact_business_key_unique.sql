select
    source_name,
    job_id_nk,
    posted_date,
    count(*) as duplicate_count
from {{ ref('fact_job_postings') }}
group by source_name, job_id_nk, posted_date
having count(*) > 1
