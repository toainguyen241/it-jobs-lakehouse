{{ config(materialized = 'view') }}
SELECT skills.skill_name,
    COUNT(DISTINCT facts.job_sk) AS total_jobs,
    COUNT(DISTINCT facts.job_sk) filter (
        WHERE facts.source_name = 'itviec'
    ) AS itviec_jobs,
    COUNT(DISTINCT facts.job_sk) filter (
        WHERE facts.source_name = 'topdev'
    ) AS topdev_jobs,
    COUNT(DISTINCT facts.job_sk) filter (
        WHERE facts.source_name = 'topcv'
    ) AS topcv_jobs,
    COUNT(DISTINCT facts.job_sk) filter (
        WHERE facts.source_name = 'indeed'
    ) AS indeed_jobs,
    COUNT(DISTINCT facts.source_name) AS source_count,
    min(facts.posted_date) AS first_posted_date,
    max(facts.posted_date) AS latest_posted_date,
    COUNT(DISTINCT facts.job_sk) filter (
        WHERE facts.salary_status IN ('scraped', 'corrected')
    ) AS jobs_with_salary,
    round(
        avg(
            CASE
                WHEN facts.salary_status IN ('scraped', 'corrected') THEN (
                    coalesce(facts.salary_min_usd, facts.salary_max_usd) + coalesce(facts.salary_max_usd, facts.salary_min_usd)
                ) / 2.0
            END
        ),
        2
    ) AS avg_salary_usd
FROM {{ ref('canonical_job_skills') }} skills
    INNER JOIN {{ ref('fact_job_postings') }} facts ON facts.job_sk = skills.job_sk
    AND facts.posted_date = skills.posted_date
WHERE {{ in_crawl_scope('facts') }}
GROUP BY skills.skill_name
