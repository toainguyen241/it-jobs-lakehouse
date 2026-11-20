{% macro gold_split_skills(skills_expression) -%}
    regexp_split_to_table(
        replace(
            replace(coalesce({{ skills_expression }}, ''), chr(13), ','),
            chr(10),
            ','
        ),
        E'\\s*[,;|]+\\s*'
    )
{%- endmacro %}


{% macro gold_normalize_skill(skill_expression) -%}
    nullif(
        lower(
            trim(
                regexp_replace(
                    trim({{ skill_expression }}),
                    E'^[\\[\\]"'']+|[\\[\\]"'']+$',
                    '',
                    'g'
                )
            )
        ),
        ''
    )
{%- endmacro %}
