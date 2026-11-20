{{ config(materialized='view') }}

WITH job_salary AS (
    SELECT source_name,
        salary_status,
        salary_min_usd,
        salary_max_usd,
        CASE
            WHEN salary_status IN ('scraped', 'corrected') THEN (
                coalesce(salary_min_usd, salary_max_usd) + coalesce(salary_max_usd, salary_min_usd)
            ) / 2.0
        END AS salary_mid_usd
    FROM {{ ref('fact_job_postings') }} f
    WHERE {{ in_crawl_scope('f') }}
)
SELECT source_name,
    COUNT(*) AS total_jobs,
    COUNT(*) filter (
        WHERE salary_mid_usd IS NOT NULL
    ) AS jobs_with_salary,
    round(
        COUNT(*) filter (
            WHERE salary_mid_usd IS NOT NULL
        )::numeric / nullif(COUNT(*), 0),
        4
    ) AS salary_coverage_rate,
    round(
        avg(salary_min_usd) filter (
            WHERE salary_mid_usd IS NOT NULL
        ),
        2
    ) AS avg_salary_min_usd,
    round(avg(salary_mid_usd), 2) AS avg_salary_usd,
    round(
        avg(salary_max_usd) filter (
            WHERE salary_mid_usd IS NOT NULL
        ),
        2
    ) AS avg_salary_max_usd,
    round(
        (
            percentile_cont(0.5) within group (
                ORDER BY salary_mid_usd
            ) filter (
                WHERE salary_mid_usd IS NOT NULL
            )
        )::numeric,
        2
    ) AS median_salary_usd,
    round(min(salary_mid_usd), 2) AS min_salary_usd,
    round(max(salary_mid_usd), 2) AS max_salary_usd
FROM job_salary
GROUP BY source_name
