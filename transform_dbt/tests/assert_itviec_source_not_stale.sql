{{ config(tags=['pipeline_guard']) }}


with source_state as (
    select
        max(loaded_at) as latest_loaded_at
    from {{ source('bronze', 'raw_jobs_crawled') }}
    where source_name = 'itviec'
)

select
    'itviec_source_stale'::text as check_name,
    latest_loaded_at,
    current_timestamp as checked_at,
    {{ env_var('DQ_ITVIEC_FRESHNESS_HOURS', '72') | int }}::integer
        as freshness_threshold_hours
from source_state
where latest_loaded_at is not null
  and latest_loaded_at < current_timestamp - make_interval(
      hours => {{ env_var('DQ_ITVIEC_FRESHNESS_HOURS', '72') | int }}
  )

