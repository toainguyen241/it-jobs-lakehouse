select *
from {{ ref('dim_companies') }}
where company_name <> trim(company_name)
   or company_nk <> md5(lower(trim(company_name)))
