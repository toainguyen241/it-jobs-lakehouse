{{ config(materialized='view') }}

with aliases as (
    select
        lower(trim(skill_alias)) as skill_alias,
        lower(trim(canonical_skill_name)) as skill_name,
        lower(trim(skill_category)) as skill_category
    from {{ ref('skill_aliases') }}
),

canonicalized as (
    select distinct
        bridge.job_sk,
        bridge.posted_date,
        aliases.skill_name,
        aliases.skill_category
    from {{ ref('bridge_job_skills') }} bridge
    inner join {{ ref('dim_skills') }} skills
        on skills.skill_sk = bridge.skill_sk
    inner join aliases
        on aliases.skill_alias = skills.skill_name
)

select *
from canonicalized
