{# Normalised lookup key for one Vietnamese place label:
   unaccent + lower-case, dots to spaces, "q.7"/"quận 7" -> "quan 7", administrative prefix removed. #}
{% macro vn_city_key(expr) %}
regexp_replace(
    regexp_replace(
        regexp_replace(
            regexp_replace(lower(unaccent(trim({{ expr }}))), '[.]', ' ', 'g'),
            '\s+', ' ', 'g'
        ),
        '^(quan|q)\s*(\d+)$', 'quan \2'
    ),
    '^(quan|huyen|thi xa|thi tran|thanh pho|tp|tinh|phuong)\s+(?=\D)', ''
)
{% endmacro %}

{# Canonical lower-case city for a raw location label. Tries the whole label, then each fragment split on , ; | / and " - ";
   the first fragment found in seed vn_location_aliases wins. Unknown labels fall back to lower(trim(raw)). #}
{% macro canonical_city(raw_expr) %}
coalesce(
    (
        select aliases.city
        from unnest(
            array[{{ raw_expr }}]
            || regexp_split_to_array({{ raw_expr }}, '\s*[,;|/]\s*|\s+-\s+')
        ) with ordinality as fragments(fragment, position)
        inner join {{ ref('vn_location_aliases') }} aliases
            on aliases.alias_key = {{ vn_city_key('fragments.fragment') }}
        order by fragments.position
        limit 1
    ),
    nullif(lower(trim({{ raw_expr }})), '')
)
{% endmacro %}
