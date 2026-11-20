{# Heuristic grouping key for a company name, used only to group companies in marts.
   unaccent -> lower -> keep [a-z0-9] -> drop legal-form words -> drop all spaces,
   so "MB Bank" and "MBBANK", or "Công Ty TNHH LG CNS Việt Nam" and "LG CNS Việt Nam", share a key.
   dim_companies.company_nk is intentionally not changed. #}
{% macro company_group_key(column) %}
coalesce(
    nullif(
        regexp_replace(
            regexp_replace(
                trim(regexp_replace(unaccent(lower(trim({{ column }}))), '[^a-z0-9]+', ' ', 'g')),
                '\m(company|corporation|corp|joint stock|co phan|cong ty|co|limited|ltd|inc|jsc|llc|tnhh|pte|pvt|gmbh|plc)\M',
                ' ',
                'g'
            ),
            '\s+',
            '',
            'g'
        ),
        ''
    ),
    nullif(regexp_replace(unaccent(lower(trim({{ column }}))), '[^a-z0-9]+', '', 'g'), ''),
    md5(lower(trim({{ column }})))
)
{% endmacro %}
