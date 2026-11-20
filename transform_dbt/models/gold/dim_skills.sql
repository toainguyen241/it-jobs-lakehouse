{{ config(
    materialized='gold_merge',
    unique_key=['skill_name'],
    merge_columns=['skill_name'],
    merge_update_columns=[]
) }}

select distinct
    {{ gold_normalize_skill('skill.value') }}                    as skill_name
from {{ ref('silver_jobs_unified') }} jobs
cross join lateral {{ gold_split_skills('jobs.skills_raw') }} as skill(value)
where {{ gold_normalize_skill('skill.value') }} is not null
