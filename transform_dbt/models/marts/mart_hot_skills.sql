{{ config(materialized = 'view') }} WITH date_boundary AS (
    SELECT max(posted_date) AS latest_posted_date
    FROM {{ ref('fact_job_postings') }} scoped
    WHERE {{ in_crawl_scope('scoped') }}
        AND NOT coalesce(scoped.posted_date_is_estimated, false)
),
recent_skill_jobs AS (
    SELECT s.skill_name,
        f.job_sk,
        f.source_name,
        f.posted_date,
        CASE
            WHEN f.salary_status IN ('scraped', 'corrected') THEN (
                coalesce(f.salary_min_usd, f.salary_max_usd) + coalesce(f.salary_max_usd, f.salary_min_usd)
            ) / 2.0
        END AS salary_mid_usd,
        boundary.latest_posted_date
    FROM {{ ref('canonical_job_skills') }} s
        INNER JOIN {{ ref('fact_job_postings') }} f ON f.job_sk = s.job_sk
        AND f.posted_date = s.posted_date
        CROSS JOIN date_boundary boundary
    WHERE f.posted_date >= boundary.latest_posted_date - 29
        AND NOT coalesce(f.posted_date_is_estimated, false)
        AND {{ in_crawl_scope('f') }}
),
aggregated AS (
    SELECT skill_name,
        latest_posted_date - 29 AS window_start_date,
        latest_posted_date AS window_end_date,
        COUNT(DISTINCT job_sk) AS job_count,
        COUNT(DISTINCT source_name) AS source_count,
        max(posted_date) AS latest_skill_posted_date,
        round(avg(salary_mid_usd), 2) AS avg_salary_usd
    FROM recent_skill_jobs
    GROUP BY skill_name,
        latest_posted_date
),
ranked AS (
    SELECT dense_rank() over (
            ORDER BY job_count DESC,
                skill_name
        ) AS hot_rank,
        *
    FROM aggregated
)
SELECT hot_rank,
    skill_name,
    window_start_date,
    window_end_date,
    job_count,
    source_count,
    latest_skill_posted_date,
    avg_salary_usd
FROM ranked
WHERE hot_rank <= 20
