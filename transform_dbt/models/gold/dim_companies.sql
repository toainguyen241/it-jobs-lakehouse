{{ config(
    materialized='gold_merge',
    unique_key=['company_nk'],
    merge_columns=['company_nk', 'company_name', 'company_size', 'industry', 'updated_at'],
    merge_update_columns=['company_name', 'company_size', 'industry', 'updated_at'],
    merge_compare_columns=['company_name', 'company_size', 'industry']
) }}

with normalized as (
    select
        md5(lower(trim(company_name)))                            as company_nk,
        trim(company_name)                                        as company_name,
        nullif(trim(company_size), '')                            as company_size,
        nullif(trim(industry), '')                                as industry
    from {{ ref('silver_jobs_unified') }}
    where nullif(trim(company_name), '') is not null
),

ranked_names as (
    select
        company_nk,
        company_name,
        row_number() over (
            partition by company_nk
            order by count(*) desc, company_name
        )                                                         as row_num
    from normalized
    group by company_nk, company_name
),

ranked_sizes as (
    select
        company_nk,
        company_size,
        row_number() over (
            partition by company_nk
            order by count(*) desc, company_size
        )                                                         as row_num
    from normalized
    where company_size is not null
    group by company_nk, company_size
),

ranked_industries as (
    select
        company_nk,
        industry,
        row_number() over (
            partition by company_nk
            order by count(*) desc, industry
        )                                                         as row_num
    from normalized
    where industry is not null
    group by company_nk, industry
)

select
    names.company_nk,
    names.company_name,
    sizes.company_size,
    industries.industry,
    now()                                                         as updated_at
from ranked_names names
left join ranked_sizes sizes
    on sizes.company_nk = names.company_nk
   and sizes.row_num = 1
left join ranked_industries industries
    on industries.company_nk = names.company_nk
   and industries.row_num = 1
where names.row_num = 1
