-- Staging cho các nguồn crawled. Chỉ extract JSONB -> cột typed và truncate job_description.
with source as (
    select
        job_id_nk,
        source_name,
        scraped_at,
        payload
    from {{ source('bronze', 'raw_jobs_crawled') }}

),

extracted as (
    select
        job_id_nk,
        source_name,
        scraped_at,
        'crawled'                                  as source_type,
        payload ->> 'job_title'                     as job_title,
        payload ->> 'company_name'                  as company_name,
        payload ->> 'experience'                    as experience_raw,
        payload ->> 'salary_text'                   as salary_text,
        payload ->> 'location'                      as city_raw,
        payload ->> 'job_type'                      as employment_type,
        payload ->> 'company_size'                  as company_size,
        payload ->> 'industry'                      as industry,
        payload ->> 'country'                       as country,
        (payload ->> 'posted_date')::date           as posted_date,
        payload ->> 'time_info_raw'                 as time_info_raw,
        payload ->> 'time_info_label'                as time_info_label,
        left(payload ->> 'job_description', 300)     as job_description_snippet,

        -- skills lưu dạng JSONB array trong payload -> convert về comma-separated string để đồng nhất format với Kaggle (required_skills).

        (
            select string_agg(skill, ', ')
            from jsonb_array_elements_text(payload -> 'skills') as skill
        )                                            as skills_raw

    from source

)

select * from extracted
