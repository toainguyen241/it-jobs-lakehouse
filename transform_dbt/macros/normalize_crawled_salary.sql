{% macro crawled_salary_correction_reason(source_column, salary_column) %}
case
    when {{ source_column }} = 'indeed'
     and {{ salary_column }} ~* 'VN[DdĐđ].*(?:a|per)\s+year'
        then 'indeed_vnd_year_label_corrected_to_month'
    when {{ source_column }} = 'weworkremotely'
     and {{ salary_column }} ~* '(USD|\$)'
     and {{ salary_column }} !~* '(year|annual|annually|yearly|/\s*yr|per\s+yr|month|week|hour|/\s*(?:hr|mo|wk)|per\s+(?:hr|mo|wk))'
        then 'weworkremotely_usd_salary_assumed_annual'
    when {{ source_column }} = 'itviec'
     and {{ salary_column }} ~* '^\s*(?:up\s*to|upto|up|from|-)?\s*[0-9][0-9,.]*\s*$'
        then 'itviec_missing_currency_assumed_usd'
end
{% endmacro %}


{% macro normalized_crawled_salary_text(source_column, salary_column) %}
case
    when {{ source_column }} = 'indeed'
     and {{ salary_column }} ~* 'VN[DdĐđ].*(?:a|per)\s+year'
        then regexp_replace(
            {{ salary_column }},
            '(a|per)\s+year',
            'a month',
            'i'
        )
    when {{ source_column }} = 'weworkremotely'
     and {{ salary_column }} ~* '(USD|\$)'
     and {{ salary_column }} !~* '(year|annual|annually|yearly|/\s*yr|per\s+yr|month|week|hour|/\s*(?:hr|mo|wk)|per\s+(?:hr|mo|wk))'
        then {{ salary_column }} || ' a year'
    when {{ source_column }} = 'itviec'
     and {{ salary_column }} ~* '^\s*(?:up\s*to|upto|up|from|-)?\s*[0-9][0-9,.]*\s*$'
        then {{ salary_column }} || ' USD'
    else {{ salary_column }}
end
{% endmacro %}
