{% macro ensure_fact_month_partitions(months_ahead=1) %}

{% if months_ahead < 0 %}
    {{ exceptions.raise_compiler_error("months_ahead must be zero or greater") }}
{% endif %}

{% set sql %}
DO $partition_maintenance$
DECLARE
    month_offset integer;
    partition_start date;
    partition_end date;
    partition_name text;
    default_has_rows boolean;
BEGIN
    IF to_regclass('gold.fact_job_postings') IS NULL THEN
        RAISE EXCEPTION
            'gold.fact_job_postings does not exist; run containers/postgres/init.sql first';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtext('gold.fact_job_postings_partition_maintenance')
    );

    -- Offset 0 protects fresh clones created during a later month.
    -- Offset 1 creates the next partition before the calendar rolls over.
    FOR month_offset IN 0..{{ months_ahead }} LOOP
        partition_start := (
            date_trunc('month', current_date)
            + make_interval(months => month_offset)
        )::date;
        partition_end := (partition_start + interval '1 month')::date;
        partition_name := 'fact_job_postings_' || to_char(partition_start, 'YYYY_MM');

        IF to_regclass(format('%I.%I', 'gold', partition_name)) IS NULL THEN
            default_has_rows := false;

            IF to_regclass('gold.fact_job_postings_default') IS NOT NULL THEN
                EXECUTE
                    'SELECT EXISTS (
                        SELECT 1
                        FROM gold.fact_job_postings_default
                        WHERE posted_date >= $1
                          AND posted_date < $2
                    )'
                INTO default_has_rows
                USING partition_start, partition_end;
            END IF;

            IF default_has_rows THEN
                RAISE EXCEPTION USING MESSAGE = format(
                    'Cannot create gold.%I: default partition already contains rows '
                    'from %s (inclusive) to %s (exclusive); migrate those rows first',
                    partition_name,
                    partition_start,
                    partition_end
                );
            END IF;

            EXECUTE format(
                'CREATE TABLE %I.%I PARTITION OF %I.%I '
                'FOR VALUES FROM (%L) TO (%L)',
                'gold',
                partition_name,
                'gold',
                'fact_job_postings',
                partition_start,
                partition_end
            );

            RAISE NOTICE 'Created partition gold.% for [% - %)',
                partition_name,
                partition_start,
                partition_end;
        END IF;
    END LOOP;
END
$partition_maintenance$;
{% endset %}

{% if execute %}
    {% do run_query(sql) %}
{% endif %}

{% endmacro %}

