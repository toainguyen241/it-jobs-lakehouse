select
    posted_date,
    source_name,
    country,
    city,
    skill_name,
    count(*) as duplicate_count
from {{ ref('mart_skills_demand') }}
group by posted_date, source_name, country, city, skill_name
having count(*) > 1
