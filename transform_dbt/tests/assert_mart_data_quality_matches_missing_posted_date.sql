with expected as (
    select source_name, count(*) as jobs_missing_posted_date
    from {{ ref('silver_jobs_unified') }}
    where posted_date is null
    group by source_name
),

actual as (
    select source_name, jobs_missing_posted_date
    from {{ ref('mart_data_quality') }}
)

select
    coalesce(actual.source_name, expected.source_name) as source_name,
    actual.jobs_missing_posted_date as actual_count,
    coalesce(expected.jobs_missing_posted_date, 0) as expected_count
from actual
full outer join expected using (source_name)
where coalesce(actual.jobs_missing_posted_date, 0)
    is distinct from coalesce(expected.jobs_missing_posted_date, 0)
