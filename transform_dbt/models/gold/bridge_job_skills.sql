{{ config(
    materialized='gold_merge',
    unique_key=['job_sk', 'posted_date', 'skill_sk'],
    merge_columns=['job_sk', 'posted_date', 'skill_sk'],
    merge_update_columns=[],
    insert_only=true
) }}

with exploded as (
    select distinct
        jobs.job_id_nk,
        jobs.source_name,
        jobs.posted_date,
        {{ gold_normalize_skill('skill.value') }}                 as skill_name
    from {{ ref('silver_jobs_unified') }} jobs
    cross join lateral {{ gold_split_skills('jobs.skills_raw') }} as skill(value)
    where {{ gold_normalize_skill('skill.value') }} is not null
)

select distinct
    facts.job_sk,
    facts.posted_date,
    skills.skill_sk
from exploded
inner join {{ ref('fact_job_postings') }} facts
    on facts.job_id_nk = exploded.job_id_nk
   and facts.source_name = exploded.source_name
   and facts.posted_date = exploded.posted_date
inner join {{ ref('dim_skills') }} skills
    on skills.skill_name = exploded.skill_name
