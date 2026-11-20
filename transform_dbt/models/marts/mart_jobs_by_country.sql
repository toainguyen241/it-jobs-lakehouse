{{ config(materialized = 'view') }}
SELECT coalesce(locations.country, 'Unknown') AS country,
    COUNT(*) AS total_jobs,
    COUNT(*) filter (
        WHERE facts.source_name = 'itviec'
    ) AS itviec_jobs,
    COUNT(*) filter (
        WHERE facts.source_name = 'topdev'
    ) AS topdev_jobs,
    COUNT(*) filter (
        WHERE facts.source_name = 'topcv'
    ) AS topcv_jobs,
    COUNT(*) filter (
        WHERE facts.source_name = 'indeed'
    ) AS indeed_jobs,
    COUNT(DISTINCT facts.company_sk) AS company_count,
    COUNT(*) filter (
        WHERE facts.salary_status IN ('scraped', 'corrected')
    ) AS jobs_with_salary,
    round(
        COUNT(*) filter (
            WHERE facts.salary_status IN ('scraped', 'corrected')
        )::numeric / nullif(COUNT(*), 0),
        4
    ) AS salary_coverage_rate
FROM {{ ref('fact_job_postings') }} facts
    LEFT JOIN {{ ref('dim_locations') }} locations ON locations.location_sk = facts.location_sk
WHERE {{ in_crawl_scope('facts') }}
GROUP BY coalesce(locations.country, 'Unknown')
