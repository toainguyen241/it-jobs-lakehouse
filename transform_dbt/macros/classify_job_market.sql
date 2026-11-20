{% macro classify_job_market(source_name, country) %}
case
    when {{ source_name }} in ('itviec', 'topcv', 'topdev') then 'Vietnam'
    when lower(trim({{ country }})) = 'vietnam' then 'Vietnam'
    when nullif(trim({{ country }}), '') is null then 'Unknown'
    else 'International'
end
{% endmacro %}


{% macro normalize_employment_type(employment_type) %}
case
    when lower(trim({{ employment_type }})) in (
        'ft', 'full-time', 'fulltime', 'full time', 'full_time',
        'toàn thời gian', 'cố định'
    ) then 'Full-time'
    when lower(trim({{ employment_type }})) in (
        'pt', 'part-time', 'part time', 'part_time', 'bán thời gian'
    ) then 'Part-time'
    when lower(trim({{ employment_type }})) in ('ct', 'contract', 'thời vụ')
        then 'Contract'
    when lower(trim({{ employment_type }})) in ('fl', 'freelance')
        then 'Freelance'
    when lower(trim({{ employment_type }})) in ('intern', 'internship', 'thực tập')
        then 'Internship'
    else 'Unknown'
end
{% endmacro %}


{% macro classify_work_arrangement(source_name, employment_type, city, country, remote_ratio=none) %}
case
    when {{ source_name }} in ('weworkremotely', 'remoteok') then 'Remote'
{%- if remote_ratio %}
    when {{ remote_ratio }} = 100 then 'Remote'
    when {{ remote_ratio }} = 50 then 'Hybrid'
    when {{ remote_ratio }} = 0 then 'On-site'
{%- endif %}
    when lower(trim(coalesce({{ employment_type }}, ''))) = 'remote' then 'Remote'
    when lower(trim(coalesce({{ employment_type }}, ''))) = 'hybrid' then 'Hybrid'
    when lower(trim(coalesce({{ employment_type }}, ''))) = 'at office' then 'On-site'
    when lower(trim(coalesce({{ city }}, ''))) ~ '(^|[^a-z])remote([^a-z]|$)'
        then 'Remote'
    when lower(trim(coalesce({{ country }}, ''))) = 'worldwide' then 'Remote'
    else 'Unknown'
end
{% endmacro %}
