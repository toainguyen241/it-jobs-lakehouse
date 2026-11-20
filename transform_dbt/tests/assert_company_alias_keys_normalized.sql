select *
from {{ ref('company_aliases') }}
where alias_key !~ '^[a-z0-9]+$'
