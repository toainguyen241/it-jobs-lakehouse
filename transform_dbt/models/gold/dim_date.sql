{{ config(
    materialized='gold_merge',
    unique_key=['date_sk'],
    merge_columns=['date_sk', 'year', 'month', 'day', 'quarter', 'day_of_week', 'is_weekend'],
    merge_update_columns=['year', 'month', 'day', 'quarter', 'day_of_week', 'is_weekend'],
    merge_compare_columns=['year', 'month', 'day', 'quarter', 'day_of_week', 'is_weekend']
) }}

select distinct
    posted_date                                                   as date_sk,
    extract(year from posted_date)::integer                       as year,
    extract(month from posted_date)::integer                      as month,
    extract(day from posted_date)::integer                        as day,
    extract(quarter from posted_date)::integer                    as quarter,
    trim(to_char(posted_date, 'Day'))                             as day_of_week,
    extract(isodow from posted_date)::integer in (6, 7)           as is_weekend
from {{ ref('silver_jobs_unified') }}
where posted_date is not null
