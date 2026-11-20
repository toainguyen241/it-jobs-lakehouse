{{ config(materialized = 'view') }}
SELECT facts.job_sk,
    facts.posted_date,
    facts.source_name,
    facts.job_title,
    companies.company_name,
    initcap(locations.city_nk) AS city,
    locations.country,
    facts.salary_min_usd,
    facts.salary_max_usd,
    (
        coalesce(facts.salary_min_usd, facts.salary_max_usd) + coalesce(facts.salary_max_usd, facts.salary_min_usd)
    ) / 2.0 AS salary_mid_usd,
    facts.salary_status
FROM {{ ref('fact_job_postings') }} facts
    LEFT JOIN {{ ref('dim_companies') }} companies ON companies.company_sk = facts.company_sk
    LEFT JOIN {{ ref('dim_locations') }} locations ON locations.location_sk = facts.location_sk
WHERE {{ in_crawl_scope('facts') }}
    AND facts.salary_status IN ('scraped', 'corrected')
    AND (
        facts.salary_min_usd IS NOT NULL
        OR facts.salary_max_usd IS NOT NULL
    )
