with source as (
    select *
    from {{ source('bronze', 'raw_jobs_kaggle_global_ai_2025') }}
),

renamed as (
    select
        job_id                                      as job_id_nk,
        'kaggle'                                    as source_name,
        null::timestamptz                           as scraped_at,
        'kaggle_dataset'                            as source_type,
        job_title,
        company_name,
        experience_level                            as experience_raw,
        years_experience,
        salary_usd                                  as salary_amount_raw,
        lower(salary_currency)                      as salary_currency,
        employment_type,
        remote_ratio,
        company_size,
        industry,
        company_location                            as country,
        posting_date                                as posted_date,
        required_skills                             as skills_raw

    from source

)

select * from renamed
