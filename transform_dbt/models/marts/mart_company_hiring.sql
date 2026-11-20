{{ config(materialized = 'view') }}

WITH jobs AS (
    SELECT f.source_name,
        f.location_sk,
        f.posted_date,
        f.salary_status,
        f.salary_min_usd,
        f.salary_max_usd,
        c.company_name,
        c.company_size,
        c.industry,
        {{ company_group_key('c.company_name') }} AS raw_group_key
    FROM {{ ref('fact_job_postings') }} f
        INNER JOIN {{ ref('dim_companies') }} c ON c.company_sk = f.company_sk
    WHERE {{ in_crawl_scope('f') }}
),
aliases AS (
    SELECT alias_key,
        canonical_name,
        {{ company_group_key('canonical_name') }} AS canonical_key
    FROM {{ ref('company_aliases') }}
),
keyed AS (
    SELECT j.*,
        a.canonical_name,
        coalesce(a.canonical_key, j.raw_group_key) AS company_group_key
    FROM jobs j
        LEFT JOIN aliases a ON a.alias_key = j.raw_group_key
)
SELECT source_name,
    company_group_key,
    coalesce(
        max(canonical_name),
        mode() WITHIN GROUP (ORDER BY company_name)
    ) AS company_name,
    mode() WITHIN GROUP (ORDER BY company_size) AS company_size,
    mode() WITHIN GROUP (ORDER BY industry) AS industry,
    COUNT(*) AS job_count,
    min(posted_date) AS first_posted_date,
    max(posted_date) AS latest_posted_date,
    COUNT(DISTINCT location_sk) AS active_location_count,
    COUNT(*) filter (
        WHERE salary_status IN ('scraped', 'corrected')
    ) AS jobs_with_salary,
    avg(
        CASE
            WHEN salary_status IN ('scraped', 'corrected') THEN (
                coalesce(salary_min_usd, salary_max_usd) + coalesce(salary_max_usd, salary_min_usd)
            ) / 2.0
        END
    ) AS avg_salary_usd
FROM keyed
GROUP BY source_name,
    company_group_key
