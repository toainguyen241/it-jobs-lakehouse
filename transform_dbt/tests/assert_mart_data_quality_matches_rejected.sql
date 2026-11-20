with expected as (
    select source_name, count(*) as jobs_with_invalid_salary
    from {{ ref('rejected_jobs') }}
    group by source_name
),

actual as (
    select source_name, jobs_with_invalid_salary
    from {{ ref('mart_data_quality') }}
)

select
    coalesce(actual.source_name, expected.source_name) as source_name,
    actual.jobs_with_invalid_salary as actual_count,
    coalesce(expected.jobs_with_invalid_salary, 0) as expected_count
from actual
full outer join expected using (source_name)
where actual.jobs_with_invalid_salary
    is distinct from coalesce(expected.jobs_with_invalid_salary, 0)
