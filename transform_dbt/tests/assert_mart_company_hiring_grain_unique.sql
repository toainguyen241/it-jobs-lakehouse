select
    source_name,
    company_group_key,
    count(*) as duplicate_count
from {{ ref('mart_company_hiring') }}
group by source_name, company_group_key
having count(*) > 1
