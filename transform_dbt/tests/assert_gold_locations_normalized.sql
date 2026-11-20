select *
from {{ ref('dim_locations') }}
where country <> trim(country)
   or city_nk is distinct from nullif(lower(trim(city_nk)), '')
