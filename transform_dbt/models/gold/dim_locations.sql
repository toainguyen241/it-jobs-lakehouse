{{ config(
    materialized='gold_merge',
    unique_key=['city_nk', 'country'],
    merge_columns=['city_nk', 'country'],
    merge_update_columns=[]
) }}

select distinct
    nullif(lower(trim(city)), '')                                 as city_nk,
    trim(country)                                                as country
from {{ ref('silver_jobs_unified') }}
where nullif(trim(country), '') is not null
