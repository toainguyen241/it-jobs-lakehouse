{# Crawled jobs are analysed for one market year only (dbt var crawl_market_year); Kaggle is historical (2024-2025). #}
{% macro in_crawl_scope(alias) %}
({{ alias }}.source_type = 'crawled'
 and extract(year from {{ alias }}.posted_date) = {{ var('crawl_market_year', 2026) }})
{% endmacro %}

{# Pages with a market-year selector: Kaggle keeps its own years, crawled jobs only count in the crawl year. #}
{% macro in_market_year_scope(alias) %}
({{ alias }}.source_type <> 'crawled'
 or extract(year from {{ alias }}.posted_date) = {{ var('crawl_market_year', 2026) }})
{% endmacro %}
