select market_year, skill_name, count(*) as row_count
from {{ ref('mart_skill_trends_by_year') }}
group by market_year, skill_name
having count(*) > 1

