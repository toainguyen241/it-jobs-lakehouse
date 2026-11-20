{#
  Override macro mặc định của dbt. Hành vi gốc của dbt là nối
  "<default_schema>_<custom_schema>" khi model có +schema custom -- gây ra
  lỗi "silver_silver" (default schema trong profiles.yml đã là 'silver',
  cộng thêm +schema: silver trong dbt_project.yml).

  Macro này đơn giản: nếu có custom_schema_name -> dùng ĐÚNG tên đó, không
  nối gì thêm. Nếu không có -> dùng default schema từ profiles.yml.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}