{% macro create_salary_parser_function() %}

{% set sql %}

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'salary_parsed'
          AND typnamespace = 'silver'::regnamespace
    ) THEN
        CREATE TYPE silver.salary_parsed AS (
            salary_min      NUMERIC,
            salary_max      NUMERIC,
            currency        TEXT,
            period          TEXT,
            salary_status   TEXT,
            correction_reason TEXT
        );
    ELSIF NOT EXISTS (
        SELECT 1
        FROM pg_attribute
        WHERE attrelid = 'silver.salary_parsed'::regclass
          AND attname = 'correction_reason'
          AND NOT attisdropped
    ) THEN
        ALTER TYPE silver.salary_parsed
            ADD ATTRIBUTE correction_reason TEXT;
    END IF;
END$$;

CREATE OR REPLACE FUNCTION silver.parse_salary_number(value_text TEXT)
RETURNS NUMERIC
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    normalized TEXT;
BEGIN
    normalized := regexp_replace(trim(value_text), '\s+', '', 'g');
    IF normalized !~ '^[0-9]+([.,][0-9]+)*$' THEN
        RETURN NULL;
    END IF;
    IF normalized ~ '^[0-9]{1,3}(,[0-9]{3})+\.[0-9]{1,2}$' THEN
        RETURN replace(normalized, ',', '')::NUMERIC;
    END IF;
    IF normalized ~ '^[0-9]{1,3}(\.[0-9]{3})+,[0-9]{1,2}$' THEN
        RETURN replace(replace(normalized, '.', ''), ',', '.')::NUMERIC;
    END IF;
    IF normalized ~ '^[0-9]{1,3}([.,][0-9]{3})+$' THEN
        RETURN replace(replace(normalized, '.', ''), ',', '')::NUMERIC;
    END IF;
    IF normalized ~ '^[0-9]+[.,][0-9]+$' THEN
        RETURN replace(normalized, ',', '.')::NUMERIC;
    END IF;
    IF normalized ~ '^[0-9]+$' THEN
        RETURN normalized::NUMERIC;
    END IF;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION silver.parse_salary_range(salary_text TEXT)
RETURNS silver.salary_parsed
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    result          silver.salary_parsed;
    cleaned         TEXT;
    matches         TEXT[];
    currency_code   TEXT;
    salary_period   TEXT;
    uses_million    BOOLEAN;
    uses_thousand   BOOLEAN;
    has_usd         BOOLEAN;
    has_vnd         BOOLEAN;
    currency_corrected BOOLEAN := FALSE;
    value_min       NUMERIC;
    value_max       NUMERIC;
BEGIN
    IF salary_text IS NULL OR trim(salary_text) = '' THEN
        result.salary_status := 'not_disclosed';
        RETURN result;
    END IF;

    cleaned := lower(trim(salary_text));
    IF cleaned !~ '[0-9]' THEN
        result.salary_status := 'not_disclosed';
        RETURN result;
    END IF;

    has_usd := cleaned ~* '(usd|\$)';
    has_vnd := cleaned ~* '(vnd|vnđ|triệu|trieu|million|(^|[^a-z])(tr|m)([^a-z]|$)|(^|[^[:alpha:]])(đ|₫)([^[:alpha:]]|$))';
    uses_million := cleaned ~* '(triệu|trieu|million|(^|[^a-z])(tr|m)([^a-z]|$))';
    uses_thousand := NOT uses_million AND cleaned ~* '[0-9]\s*k([^a-z]|$)';

    IF has_usd AND NOT has_vnd THEN
        currency_code := 'usd';
    ELSIF has_vnd AND NOT has_usd THEN
        currency_code := 'vnd';
    ELSIF NOT has_usd
          AND cleaned ~ '([0-9]{1,3}(\.[0-9]{3}){2,}|[0-9]{1,3}(,[0-9]{3}){2,})' THEN
        currency_code := 'vnd';
    ELSE
        currency_code := NULL;
    END IF;

    salary_period := CASE
        WHEN cleaned ~* '(/\s*year|(?:a|per)\s+year|annual|annually|yearly|/\s*yr|per\s+yr)' THEN 'year'
        WHEN cleaned ~* '(/\s*week|(?:a|per)\s+week|weekly|/\s*wk|per\s+wk)' THEN 'week'
        WHEN cleaned ~* '(/\s*(?:day|ng[àa]y)([^[:alpha:]]|$)|(?:a|per)\s+day|daily|m[ỗo]i\s+ng[àa]y)' THEN 'day'
        WHEN cleaned ~* '(/\s*hour|an?\s+hour|per\s+hour|hourly|/\s*hr|per\s+hr)' THEN 'hour'
        ELSE 'month'
    END;

    matches := regexp_match(
        cleaned,
        '([0-9][0-9,.]*)\s*(?:vnd|vnđ|usd|\$|đ|₫|triệu|trieu|million|tr|m|k)?\s*(?:-|–|—|to|đến)\s*(?:up\s*to\s*)?\$?\s*([0-9][0-9,.]*)'
    );

    IF matches IS NOT NULL THEN
        value_min := silver.parse_salary_number(matches[1]);
        value_max := silver.parse_salary_number(matches[2]);
    ELSE
        matches := regexp_match(cleaned, '(?:from|từ)\s*\$?\s*([0-9][0-9,.]*)');
        IF matches IS NOT NULL THEN
            value_min := silver.parse_salary_number(matches[1]);
            value_max := NULL;
        ELSE
            matches := regexp_match(
                cleaned,
                '(?:^-\s*|(?:up\s*to|upto|up|tối đa|đến)\s*(?:là\s*)?)\$?\s*([0-9][0-9,.]*)'
            );
            IF matches IS NOT NULL THEN
                value_min := NULL;
                value_max := silver.parse_salary_number(matches[1]);
            ELSE
                matches := regexp_match(cleaned, '\$?\s*([0-9][0-9,.]*)');
                IF matches IS NOT NULL THEN
                    value_min := silver.parse_salary_number(matches[1]);
                    value_max := value_min;
                ELSE
                    result.salary_status := 'invalid';
                    RETURN result;
                END IF;
            END IF;
        END IF;
    END IF;

    IF uses_million THEN
        value_min := value_min * 1000000;
        value_max := value_max * 1000000;
    END IF;

    IF uses_thousand THEN
        value_min := value_min * 1000;
        value_max := value_max * 1000;
    END IF;

    IF value_min <= 0 THEN
        value_min := NULL;
    END IF;
    
    IF value_max <= 0 THEN
        value_max := NULL;
    END IF;

    result.salary_min := value_min;
    result.salary_max := value_max;
    result.currency := currency_code;
    result.period := salary_period;

    IF currency_code IS NULL OR (value_min IS NULL AND value_max IS NULL) THEN
        result.salary_status := 'invalid';
        RETURN result;
    END IF;

    IF salary_period = 'month'
       AND currency_code = 'vnd'
       AND has_vnd
       AND NOT has_usd
       AND value_min BETWEEN 100 AND 10000
       AND value_max BETWEEN 100 AND 10000
       AND value_max >= value_min THEN
        currency_code := 'usd';
        result.currency := currency_code;
        result.correction_reason := 'currency_vnd_to_usd_due_to_implausible_value';
        currency_corrected := TRUE;
    ELSIF salary_period = 'month'
          AND currency_code = 'usd'
          AND has_usd
          AND NOT has_vnd
          AND coalesce(value_min, value_max) BETWEEN 1000000 AND 200000000
          AND coalesce(value_max, value_min) BETWEEN 1000000 AND 200000000
          AND cleaned ~ '([0-9]{1,3}(\.[0-9]{3}){2,}|[0-9]{1,3}(,[0-9]{3}){2,})' THEN
        currency_code := 'vnd';
        result.currency := currency_code;
        result.correction_reason := 'currency_usd_to_vnd_due_to_implausible_value';
        currency_corrected := TRUE;
    END IF;

    IF currency_code = 'vnd'
       AND value_min IS NOT NULL
       AND value_max IS NOT NULL
       AND value_min >= 5000000
       AND value_max >= 1000000
       AND value_max < value_min THEN
        IF value_max * 10 >= value_min
           AND value_max * 10 <= 200000000 THEN
            result.salary_max := value_max * 10;
            result.salary_status := 'corrected';
            result.correction_reason := 'upper_bound_multiplied_by_10';
        ELSE
            result.salary_status := 'invalid';
        END IF;
        RETURN result;
    END IF;

    IF value_min IS NOT NULL
       AND value_max IS NOT NULL
       AND value_min > value_max THEN
        result.salary_status := 'invalid';
        RETURN result;
    END IF;

    IF (currency_code = 'usd' AND salary_period = 'month'
        AND greatest(coalesce(value_min, 0), coalesce(value_max, 0)) > 100000)
       OR (currency_code = 'vnd'
           AND least(coalesce(value_min, value_max), coalesce(value_max, value_min)) < 100000) THEN
        result.salary_status := 'invalid';
        RETURN result;
    END IF;

    result.salary_status := CASE
        WHEN currency_corrected THEN 'corrected'
        ELSE 'scraped'
    END;
    RETURN result;
END;
$$;

{% endset %}

{% do run_query(sql) %}

{% endmacro %}
