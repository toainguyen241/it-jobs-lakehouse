-- Silver layer: 1 bảng phẳng union crawled + kaggle, đã áp business logic (salary parse/convert/annualize, xác định posted_date_is_estimated).
with crawled as (
    select
        job_id_nk,
        source_type,
        source_name,
        scraped_at,
        job_title,
        company_name,
        experience_raw,
        null::numeric                              as years_experience,     
        employment_type,
        company_size,
        industry,
        case when source_name in ('itviec', 'topcv', 'topdev') then 'Vietnam' else country end as country,
        city_raw,
        city,
        posted_date,
        coalesce(time_info_label in ('deadline', 'estimated'), false) as posted_date_is_estimated,
        skills_raw,
        salary_text                                  as salary_text_raw,

        (parsed).salary_min                         as salary_min_raw,
        (parsed).salary_max                          as salary_max_raw,
        (parsed).currency                            as salary_currency,
        (parsed).period                              as salary_period,
        case
            when source_correction_reason is not null
             and (parsed).salary_status = 'scraped' then 'corrected'
            else (parsed).salary_status
        end                                           as salary_status,
        coalesce(
            (parsed).correction_reason,
            source_correction_reason
        )                                             as correction_reason

    from (
        select
            *,
            {{ crawled_salary_correction_reason('source_name', 'salary_text') }}
                                                        as source_correction_reason,
            silver.parse_salary_range(
                {{ normalized_crawled_salary_text('source_name', 'salary_text') }}
            )                                         as parsed,
            {{ canonical_city('city_raw') }}           as city
        from {{ ref('stg_crawled') }}
    ) t

),

crawled_usd as (
    select
        job_id_nk,
        source_type,
        source_name,
        job_title,
        company_name,
        experience_raw                               as experience_level,
        years_experience,
        employment_type,
        null::integer                                 as remote_ratio,      
        company_size,
        industry,
        country,
        city_raw,
        city,
        posted_date,
        posted_date_is_estimated,
        skills_raw,
        salary_text_raw,
        salary_status,
        correction_reason,
        -- Convert VND/USD -> USD qua seed fx_rates, rồi quy về ANNUAL (month x12, week x52, day x260 = 52 tuần x 5 ngày, hour x2080) để khớp Kaggle.
        case
            when salary_status in ('scraped', 'corrected')
                then round(
                    salary_min_raw * fx.usd_rate
                    * case salary_period
                        when 'year' then 1
                        when 'week' then 52
                        when 'day' then 260
                        when 'hour' then 2080
                        else 12
                      end,
                    2
                )
            else null
        end                                           as salary_min_usd,
        case
            when salary_status in ('scraped', 'corrected')
                then round(
                    salary_max_raw * fx.usd_rate
                    * case salary_period
                        when 'year' then 1
                        when 'week' then 52
                        when 'day' then 260
                        when 'hour' then 2080
                        else 12
                      end,
                    2
                )
            else null
        end                                           as salary_max_usd

    from crawled
    left join {{ ref('fx_rates') }} fx
        on crawled.salary_currency = fx.currency
    where crawled.salary_status <> 'invalid'

),

kaggle as (
    select
        job_id_nk,
        source_type,
        source_name,
        job_title,
        company_name,
        experience_raw                               as experience_level,
        years_experience,
        employment_type,
        remote_ratio,
        company_size,
        industry,
        country,
        null::text                                    as city_raw,                  
        null::text                                    as city,
        posted_date,
        false                                         as posted_date_is_estimated,  
        skills_raw,
        null::text                                    as salary_text_raw,
        case when salary_amount_raw is null then 'not_disclosed' else 'scraped' end as salary_status,
        null::text                                    as correction_reason,
        salary_amount_raw::numeric                     as salary_min_usd,
        salary_amount_raw::numeric                     as salary_max_usd

    from {{ ref('stg_kaggle_global_ai_2025') }} k

),

unioned as (
    select * from crawled_usd
    union all
    select * from kaggle
)

select * from unioned
