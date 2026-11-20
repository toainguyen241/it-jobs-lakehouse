{{ config(materialized = 'view') }}
SELECT f.posted_date,
    d.year,
    d.month,
    d.quarter,
    f.source_name,
    coalesce(f.posted_date_is_estimated, false) AS posted_date_is_estimated,
    locations.country,
    initcap(locations.city_nk) AS city,
    COUNT(*) AS job_count,
    COUNT(DISTINCT f.company_sk) AS company_count,
    COUNT(*) filter (
        WHERE f.salary_status IN ('scraped', 'corrected')
    ) AS jobs_with_salary,
    round(
        COUNT(*) filter (
            WHERE f.salary_status IN ('scraped', 'corrected')
        )::numeric / nullif(COUNT(*), 0),
        4
    ) AS salary_disclosure_rate
FROM {{ ref('fact_job_postings') }} f
    INNER JOIN {{ ref('dim_date') }} d ON d.date_sk = f.posted_date
    LEFT JOIN {{ ref('dim_locations') }} locations ON locations.location_sk = f.location_sk
WHERE {{ in_crawl_scope('f') }}
GROUP BY f.posted_date,
    d.year,
    d.month,
    d.quarter,
    f.source_name,
    coalesce(f.posted_date_is_estimated, false),
    locations.country,
    initcap(locations.city_nk)
