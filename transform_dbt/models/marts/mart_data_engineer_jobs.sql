{{ config(materialized='view') }}

with job_skills as (
    select
        skills.job_sk,
        skills.posted_date,
        array_agg(skills.skill_name order by skills.skill_name) as skills,
        count(*) as skill_count
    from {{ ref('canonical_job_skills') }} skills
    group by skills.job_sk, skills.posted_date
)

select
    facts.job_sk,
    facts.posted_date,
    extract(year from facts.posted_date)::integer as market_year,
    facts.job_id_nk,
    facts.source_type,
    facts.source_name,
    {{ classify_job_market('facts.source_name', 'locations.country') }} as market_scope,
    facts.job_title,
    companies.company_name,
    initcap(locations.city_nk) as city,
    locations.country,
    {{ normalize_employment_type('facts.employment_type') }} as employment_type,
    {{ classify_work_arrangement(
        'facts.source_name',
        'facts.employment_type',
        'locations.city_nk',
        'locations.country',
        'silver_jobs.remote_ratio'
    ) }} as work_arrangement,
    facts.experience_level as experience_level_raw,
    case
        when nullif(trim(facts.experience_level), '') is null then 'Unknown'
        when upper(trim(facts.experience_level)) = 'EN' then 'Entry'
        when upper(trim(facts.experience_level)) = 'MI' then 'Mid'
        when upper(trim(facts.experience_level)) = 'SE' then 'Senior'
        when upper(trim(facts.experience_level)) = 'EX' then 'Executive'
        when length(regexp_replace(trim(facts.experience_level), '\s+', ' ', 'g')) <= 30
            then regexp_replace(trim(facts.experience_level), '\s+', ' ', 'g')
        else 'Cần xem xét'
    end as experience_level,
    facts.salary_status,
    facts.salary_min_usd,
    facts.salary_max_usd,
    case
        when facts.salary_status in ('scraped', 'corrected') then (
            coalesce(facts.salary_min_usd, facts.salary_max_usd)
            + coalesce(facts.salary_max_usd, facts.salary_min_usd)
        ) / 2.0
    end as salary_mid_usd,
    coalesce(job_skills.skills, array[]::text[]) as skills,
    coalesce(job_skills.skill_count, 0) as skill_count
from {{ ref('fact_job_postings') }} facts
left join {{ ref('dim_companies') }} companies
    on companies.company_sk = facts.company_sk
left join {{ ref('dim_locations') }} locations
    on locations.location_sk = facts.location_sk
left join {{ ref('silver_jobs_unified') }} silver_jobs
    on silver_jobs.source_name = facts.source_name
   and silver_jobs.job_id_nk = facts.job_id_nk
   and silver_jobs.posted_date = facts.posted_date
left join job_skills
    on job_skills.job_sk = facts.job_sk
   and job_skills.posted_date = facts.posted_date
where {{ in_market_year_scope('facts') }}
    and unaccent(lower(facts.job_title))
    ~ '(^|[^a-z0-9])data[ -]*engineer(ing)?([^a-z0-9]|$)'
