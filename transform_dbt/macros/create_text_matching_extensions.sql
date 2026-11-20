{% macro create_text_matching_extensions() %}

{% set sql %}
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
{% endset %}

{% if execute %}
    {% do run_query(sql) %}
{% endif %}

{% endmacro %}
