{{ config(materialized = 'view') }} WITH cohort_jobs AS (
    SELECT facts.job_sk,
        facts.posted_date,
        CASE
            WHEN facts.source_name = 'kaggle' THEN 2025
            WHEN facts.source_name IN ('itviec', 'topdev', 'topcv', 'indeed', 'weworkremotely', 'remoteok')
            AND extract(
                year
                FROM facts.posted_date
            ) = 2026 THEN 2026
        END AS market_year,
        CASE
            WHEN facts.salary_status IN ('scraped', 'corrected') THEN (
                coalesce(facts.salary_min_usd, facts.salary_max_usd) + coalesce(facts.salary_max_usd, facts.salary_min_usd)
            ) / 2.0
        END AS salary_mid_usd
    FROM {{ ref('fact_job_postings') }} facts
    WHERE facts.source_name = 'kaggle'
        OR (
            facts.source_name IN ('itviec', 'topdev', 'topcv', 'indeed', 'weworkremotely', 'remoteok')
            AND extract(
                year
                FROM facts.posted_date
            ) = 2026
        )
),
cohort_totals AS (
    SELECT market_year,
        COUNT(*) AS total_jobs,
        round(avg(salary_mid_usd), 2) AS overall_avg_salary_usd
    FROM cohort_jobs
    GROUP BY market_year
),
skill_metrics AS (
    SELECT jobs.market_year,
        skills.skill_name,
        COUNT(DISTINCT jobs.job_sk) AS job_count,
        COUNT(DISTINCT jobs.job_sk) filter (
            WHERE jobs.salary_mid_usd IS NOT NULL
        ) AS jobs_with_salary,
        round(avg(jobs.salary_mid_usd), 2) AS avg_salary_usd,
        round(
            (
                percentile_cont(0.5) within group (
                    ORDER BY jobs.salary_mid_usd
                ) filter (
                    WHERE jobs.salary_mid_usd IS NOT NULL
                )
            )::numeric,
            2
        ) AS median_salary_usd
    FROM {{ ref('canonical_job_skills') }} skills
        INNER JOIN cohort_jobs jobs ON jobs.job_sk = skills.job_sk
        AND jobs.posted_date = skills.posted_date
    GROUP BY jobs.market_year,
        skills.skill_name
)
SELECT metrics.market_year,
    CASE
        WHEN metrics.market_year = 2025 THEN 'Kaggle'
        WHEN metrics.market_year = 2026 THEN 'Crawled IT jobs'
    END AS source_scope,
    metrics.skill_name,
    totals.total_jobs,
    totals.overall_avg_salary_usd,
    metrics.job_count,
    round(
        metrics.job_count::numeric / nullif(totals.total_jobs, 0),
        6
    ) AS demand_rate,
    metrics.jobs_with_salary,
    round(
        metrics.jobs_with_salary::numeric / nullif(metrics.job_count, 0),
        4
    ) AS salary_coverage_rate,
    metrics.avg_salary_usd,
    metrics.median_salary_usd
FROM skill_metrics metrics
    INNER JOIN cohort_totals totals ON totals.market_year = metrics.market_year
