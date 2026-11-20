{{ config(tags=['pipeline_guard']) }}


with params as (
    select
        {{ env_var('DQ_VOLUME_RECENT_DAYS', '7') | int }}::integer
            as recent_days,
        {{ env_var('DQ_VOLUME_BASELINE_DAYS', '28') | int }}::integer
            as baseline_days,
        {{ env_var('DQ_VOLUME_MIN_ACTIVE_DAYS', '14') | int }}::integer
            as min_active_days,
        {{ env_var('DQ_VOLUME_MIN_RATIO', '0.20') | float }}::numeric
            as min_volume_ratio,
        (current_timestamp at time zone 'Asia/Bangkok')::date as today_bkk
),

arrivals as (
    select
        (loaded_at at time zone 'Asia/Bangkok')::date as day_bkk,
        count(*) as new_rows
    from {{ source('bronze', 'raw_jobs_crawled') }}
    where source_name = 'itviec'
    group by 1
),


daily as (
    select
        (params.today_bkk - series.n)::date as day_bkk,
        series.n <= params.recent_days as is_recent,
        coalesce(arrivals.new_rows, 0) as new_rows
    from params
    cross join lateral generate_series(
        1, params.recent_days + params.baseline_days
    ) as series (n)
    left join arrivals
        on arrivals.day_bkk = (params.today_bkk - series.n)::date
),

summary as (
    select
        coalesce(sum(new_rows) filter (where is_recent), 0) as recent_jobs,
        (
            percentile_cont(0.5) within group (order by new_rows)
            filter (where not is_recent)
        )::numeric as baseline_median_per_day,
        count(*) filter (
            where not is_recent and new_rows > 0
        ) as baseline_active_days
    from daily
)

select
    'itviec_volume_regression'::text as check_name,
    summary.recent_jobs,
    params.recent_days,
    round(summary.baseline_median_per_day, 2) as baseline_median_per_day,
    summary.baseline_active_days,
    params.min_volume_ratio
from summary
cross join params
where summary.baseline_active_days >= params.min_active_days
  and summary.recent_jobs
      < summary.baseline_median_per_day
        * params.recent_days
        * params.min_volume_ratio
