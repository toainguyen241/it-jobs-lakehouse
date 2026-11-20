select *
from {{ ref('dim_skills') }}
where skill_name <> lower(trim(skill_name))
   or skill_name = ''
