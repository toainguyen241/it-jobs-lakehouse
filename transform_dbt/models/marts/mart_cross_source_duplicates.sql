{{ config(materialized='table') }}

-- Review-only duplicate candidates.
with crawled_jobs as (
    select
        f.job_sk,
        f.posted_date,
        f.job_id_nk,
        f.source_name,
        f.job_title,
        companies.company_name,
        locations.city_nk as city,
        locations.country,
        f.salary_min_usd,
        f.salary_max_usd,
        regexp_replace(
            unaccent(lower(trim(f.job_title))),
            '[^a-z0-9]+',
            ' ',
            'g'
        ) as normalized_title,
        trim(regexp_replace(
            regexp_replace(
                unaccent(lower(trim(companies.company_name))),
                '[^a-z0-9]+',
                ' ',
                'g'
            ),
            '\m(company|corporation|corp|limited|ltd|inc|jsc|llc|tnhh|cong ty|co phan)\M',
            ' ',
            'g'
        )) as normalized_company
    from {{ ref('fact_job_postings') }} f
    inner join {{ ref('dim_companies') }} companies
        on companies.company_sk = f.company_sk
    left join {{ ref('dim_locations') }} locations
        on locations.location_sk = f.location_sk
    where f.source_type = 'crawled'
),

candidate_pairs as (
    select
        left_job.*,
        right_job.job_sk as matched_job_sk,
        right_job.posted_date as matched_posted_date,
        right_job.job_id_nk as matched_job_id_nk,
        right_job.source_name as matched_source_name,
        right_job.job_title as matched_job_title,
        right_job.company_name as matched_company_name,
        right_job.city as matched_city,
        right_job.country as matched_country,
        right_job.salary_min_usd as matched_salary_min_usd,
        right_job.salary_max_usd as matched_salary_max_usd,
        similarity(left_job.normalized_title, right_job.normalized_title) as title_similarity,
        similarity(left_job.normalized_company, right_job.normalized_company) as company_similarity,
        abs(left_job.posted_date - right_job.posted_date) as posted_date_gap_days,
        (
            left_job.city is not null
            and right_job.city is not null
            and left_job.city = right_job.city
            and left_job.country = right_job.country
        ) as same_location,
        left_job.normalized_company = right_job.normalized_company as exact_company
    from crawled_jobs left_job
    inner join crawled_jobs right_job
        on left_job.job_sk < right_job.job_sk
       and left_job.source_name <> right_job.source_name
       and abs(left_job.posted_date - right_job.posted_date) <= 30
       and similarity(left_job.normalized_company, right_job.normalized_company) >= 0.85
       and similarity(left_job.normalized_title, right_job.normalized_title) >= 0.72
),

scored as (
    select
        *,
        round((
            title_similarity * 0.50
            + company_similarity * 0.35
            + case when same_location then 0.10 else 0 end
            + greatest(0, 1 - posted_date_gap_days::numeric / 30) * 0.05
        )::numeric, 4) as confidence_score
    from candidate_pairs
),

classified as (
    select
        *,
        case
            when title_similarity >= 0.90
             and company_similarity >= 0.90
             and posted_date_gap_days <= 7
                then 'high'
            else 'medium'
        end as confidence_level
    from scored
    where
        (
            title_similarity >= 0.90
            and company_similarity >= 0.90
            and posted_date_gap_days <= 7
        )
        or (
            title_similarity >= 0.78
            and company_similarity >= 0.88
            and posted_date_gap_days <= 14
        )
)

select
    md5(concat_ws(
        '|',
        job_sk::text,
        posted_date::text,
        matched_job_sk::text,
        matched_posted_date::text
    )) as candidate_id,
    job_sk as left_job_sk,
    posted_date as left_posted_date,
    source_name as left_source_name,
    least(source_name, matched_source_name)
        || ' <-> '
        || greatest(source_name, matched_source_name) as source_pair,
    job_id_nk as left_job_id_nk,
    job_title as left_job_title,
    company_name as left_company_name,
    city as left_city,
    country as left_country,
    salary_min_usd as left_salary_min_usd,
    salary_max_usd as left_salary_max_usd,
    matched_job_sk as right_job_sk,
    matched_posted_date as right_posted_date,
    matched_source_name as right_source_name,
    matched_job_id_nk as right_job_id_nk,
    matched_job_title as right_job_title,
    matched_company_name as right_company_name,
    matched_city as right_city,
    matched_country as right_country,
    matched_salary_min_usd as right_salary_min_usd,
    matched_salary_max_usd as right_salary_max_usd,
    round(title_similarity::numeric, 4) as title_similarity,
    round(company_similarity::numeric, 4) as company_similarity,
    posted_date_gap_days,
    same_location,
    confidence_score,
    confidence_level,
    concat_ws(
        '; ',
        case when exact_company then 'same normalized company' else 'similar company name' end,
        case when title_similarity >= 0.90 then 'very similar title' else 'similar title' end,
        case when same_location then 'same location' end,
        'posted within ' || posted_date_gap_days || ' day(s)'
    ) as match_reason,
    'pending_review'::text as review_status
from classified
