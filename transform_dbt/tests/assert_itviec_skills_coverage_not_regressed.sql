{{ config(tags=['pipeline_guard']) }}

with params as (
    select
        {{ env_var('DQ_RECENT_WINDOW_HOURS', '36') | int }}::integer
            as recent_hours,
        {{ env_var('DQ_BASELINE_WINDOW_DAYS', '14') | int }}::integer
            as baseline_days,
        {{ env_var('DQ_COVERAGE_MIN_RECENT_JOBS', '5') | int }}::integer
            as min_recent_jobs,
        {{ env_var('DQ_COVERAGE_MIN_BASELINE_JOBS', '20') | int }}::integer
            as min_baseline_jobs,
        {{ env_var('DQ_COVERAGE_MAX_DROP', '0.20') | float }}::numeric
            as max_coverage_drop
),

classified as (
    select
        loaded_at,
        case
            when jsonb_typeof(payload -> 'skills') = 'array'
                then (jsonb_array_length(payload -> 'skills') > 0)::integer
            else 0
        end as has_skills
    from {{ source('bronze', 'raw_jobs_crawled') }}
    where source_name = 'itviec'
),

metrics as (
    select
        count(*) filter (
            where loaded_at >= current_timestamp - make_interval(
                hours => params.recent_hours
            )
        ) as recent_jobs,
        count(*) filter (
            where loaded_at >= current_timestamp - make_interval(
                days => params.baseline_days
            )
              and loaded_at < current_timestamp - make_interval(
                  hours => params.recent_hours
              )
        ) as baseline_jobs,
        avg(has_skills) filter (
            where loaded_at >= current_timestamp - make_interval(
                hours => params.recent_hours
            )
        ) as recent_coverage,
        avg(has_skills) filter (
            where loaded_at >= current_timestamp - make_interval(
                days => params.baseline_days
            )
              and loaded_at < current_timestamp - make_interval(
                  hours => params.recent_hours
              )
        ) as baseline_coverage,
        params.*
    from classified
    cross join params
    group by
        params.recent_hours,
        params.baseline_days,
        params.min_recent_jobs,
        params.min_baseline_jobs,
        params.max_coverage_drop
)

select
    'itviec_skills_coverage_regression'::text as check_name,
    recent_jobs,
    baseline_jobs,
    round(recent_coverage, 4) as recent_coverage,
    round(baseline_coverage, 4) as baseline_coverage,
    round(baseline_coverage - recent_coverage, 4) as coverage_drop
from metrics
where recent_jobs >= min_recent_jobs
  and baseline_jobs >= min_baseline_jobs
  and baseline_coverage - recent_coverage > max_coverage_drop
