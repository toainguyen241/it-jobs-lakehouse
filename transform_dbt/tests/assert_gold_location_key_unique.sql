select
    city_nk,
    country,
    count(*) as duplicate_count
from {{ ref('dim_locations') }}
group by city_nk, country
having count(*) > 1
