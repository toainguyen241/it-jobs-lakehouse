select skill_alias, canonical_skill_name, skill_category
from {{ ref('skill_aliases') }}
where skill_alias <> lower(trim(skill_alias))
   or canonical_skill_name <> lower(trim(canonical_skill_name))
   or skill_category <> lower(trim(skill_category))
   or skill_alias = ''
   or canonical_skill_name = ''
   or skill_category = ''
