{{ config(materialized = 'view') }}
SELECT facts.posted_date,
    facts.source_name,
    locations.country,
    locations.city_nk AS city,
    skills.skill_name,
    COUNT(DISTINCT facts.job_sk) AS job_count,
    COUNT(DISTINCT facts.job_sk) filter (
        WHERE facts.salary_status IN ('scraped', 'corrected')
    ) AS jobs_with_salary,
    avg(
        CASE
            WHEN facts.salary_status IN ('scraped', 'corrected') THEN (
                coalesce(facts.salary_min_usd, facts.salary_max_usd) + coalesce(facts.salary_max_usd, facts.salary_min_usd)
            ) / 2.0
        END
    ) AS avg_salary_usd
FROM {{ ref('canonical_job_skills') }} skills
    INNER JOIN {{ ref('fact_job_postings') }} facts ON facts.job_sk = skills.job_sk
    AND facts.posted_date = skills.posted_date
    LEFT JOIN {{ ref('dim_locations') }} locations ON locations.location_sk = facts.location_sk
GROUP BY facts.posted_date,
    facts.source_name,
    locations.country,
    locations.city_nk,
    skills.skill_name
