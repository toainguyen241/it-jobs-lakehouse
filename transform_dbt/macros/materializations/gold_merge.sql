{% materialization gold_merge, adapter='postgres' %}
    {%- set target_relation = this -%}
    {%- set existing_relation = load_relation(target_relation) -%}
    {%- set unique_key = config.require('unique_key') -%}
    {%- set merge_columns = config.require('merge_columns') -%}
    {%- set update_columns = config.get('merge_update_columns', []) -%}
    {%- set compare_columns = config.get('merge_compare_columns', []) -%}
    {%- set insert_only = config.get('insert_only', false) -%}

    {% if existing_relation is none %}
        {{ exceptions.raise_compiler_error(
            "Gold target " ~ target_relation ~ " does not exist. Run containers/postgres/init.sql first."
        ) }}
    {% endif %}

    {% if unique_key is string %}
        {% set unique_key = [unique_key] %}
    {% endif %}

    {{ run_hooks(pre_hooks, inside_transaction=False) }}
    {{ run_hooks(pre_hooks, inside_transaction=True) }}

    {% call statement('main') %}
        {% if insert_only %}
        insert into {{ target_relation }} (
            {% for column in merge_columns %}
            {{ adapter.quote(column) }}{% if not loop.last %},{% endif %}
            {% endfor %}
        )
        select
            {% for column in merge_columns %}
            DBT_INTERNAL_SOURCE.{{ adapter.quote(column) }}{% if not loop.last %},{% endif %}
            {% endfor %}
        from (
            {{ sql }}
        ) as DBT_INTERNAL_SOURCE
        on conflict (
            {% for key in unique_key %}
            {{ adapter.quote(key) }}{% if not loop.last %},{% endif %}
            {% endfor %}
        ) do nothing
        {% else %}
        merge into {{ target_relation }} as DBT_INTERNAL_DEST
        using (
            {{ sql }}
        ) as DBT_INTERNAL_SOURCE
        on
        {% for key in unique_key %}
            DBT_INTERNAL_SOURCE.{{ adapter.quote(key) }}
                is not distinct from
            DBT_INTERNAL_DEST.{{ adapter.quote(key) }}
            {% if not loop.last %}and{% endif %}
        {% endfor %}

        {% if update_columns | length > 0 %}
        when matched
        {% if compare_columns | length > 0 %}
          and (
            {% for column in compare_columns %}
            DBT_INTERNAL_SOURCE.{{ adapter.quote(column) }}
                is distinct from
            DBT_INTERNAL_DEST.{{ adapter.quote(column) }}
            {% if not loop.last %}or{% endif %}
            {% endfor %}
          )
        {% endif %}
        then update set
            {% for column in update_columns %}
            {{ adapter.quote(column) }} = DBT_INTERNAL_SOURCE.{{ adapter.quote(column) }}{% if not loop.last %},{% endif %}
            {% endfor %}
        {% endif %}

        when not matched then insert (
            {% for column in merge_columns %}
            {{ adapter.quote(column) }}{% if not loop.last %},{% endif %}
            {% endfor %}
        ) values (
            {% for column in merge_columns %}
            DBT_INTERNAL_SOURCE.{{ adapter.quote(column) }}{% if not loop.last %},{% endif %}
            {% endfor %}
        )
        {% endif %}
    {% endcall %}

    {{ run_hooks(post_hooks, inside_transaction=True) }}
    {% do adapter.commit() %}
    {{ run_hooks(post_hooks, inside_transaction=False) }}

    {{ return({'relations': [target_relation]}) }}
{% endmaterialization %}
