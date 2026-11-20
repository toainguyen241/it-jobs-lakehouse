{{ config(
    materialized='gold_merge',
    pre_hook=[
        "{{ delete_stale_fact_bridges() }}",
        "{{ delete_stale_fact_rows() }}"
    ],
    unique_key=['source_name', 'job_id_nk', 'posted_date'],
    merge_columns=[
        'posted_date', 'job_id_nk', 'source_type', 'source_name', 'company_sk',
        'location_sk', 'job_title', 'salary_min_usd', 'salary_max_usd',
        'salary_status', 'experience_level', 'employment_type',
        'years_experience', 'posted_date_is_estimated', 'loaded_at'
    ],
    merge_update_columns=[
        'source_type', 'company_sk', 'location_sk', 'job_title',
        'salary_min_usd', 'salary_max_usd', 'salary_status', 'experience_level',
        'employment_type', 'years_experience', 'posted_date_is_estimated', 'loaded_at'
    ],
    merge_compare_columns=[
        'source_type', 'company_sk', 'location_sk', 'job_title',
        'salary_min_usd', 'salary_max_usd', 'salary_status', 'experience_level',
        'employment_type', 'years_experience', 'posted_date_is_estimated'
    ]
) }}

select
    jobs.posted_date,
    jobs.job_id_nk,
    jobs.source_type,
    jobs.source_name,
    companies.company_sk,
    locations.location_sk,
    jobs.job_title,
    jobs.salary_min_usd,
    jobs.salary_max_usd,
    jobs.salary_status,
    jobs.experience_level,
    jobs.employment_type,
    jobs.years_experience,
    jobs.posted_date_is_estimated,
    now()                                                         as loaded_at
from {{ ref('silver_jobs_unified') }} jobs
inner join {{ ref('dim_date') }} dates
    on dates.date_sk = jobs.posted_date
left join {{ ref('dim_companies') }} companies
    on companies.company_nk = md5(lower(trim(jobs.company_name)))
left join {{ ref('dim_locations') }} locations
    on locations.city_nk is not distinct from nullif(lower(trim(jobs.city)), '')
   and locations.country = trim(jobs.country)
