{% macro delete_stale_fact_bridges() %}
    delete from
        {{ adapter.quote(this.schema) }}.{{ adapter.quote('bridge_job_skills') }}
        as bridge
    using {{ this }} as fact
    where bridge.job_sk = fact.job_sk
      and bridge.posted_date = fact.posted_date
      and not exists (
          select 1
          from {{ ref('silver_jobs_unified') }} as silver
          where silver.source_name = fact.source_name
            and silver.job_id_nk = fact.job_id_nk
            and silver.posted_date = fact.posted_date
      )
{% endmacro %}


{% macro delete_stale_fact_rows() %}
    delete from {{ this }} as fact
    where not exists (
        select 1
        from {{ ref('silver_jobs_unified') }} as silver
        where silver.source_name = fact.source_name
          and silver.job_id_nk = fact.job_id_nk
          and silver.posted_date = fact.posted_date
    )
{% endmacro %}
