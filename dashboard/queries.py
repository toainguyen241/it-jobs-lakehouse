OVERVIEW_KPIS = """
select *
from gold.mart_overview_kpis
"""

JOBS_BY_COUNTRY = """
select *
from gold.mart_jobs_by_country
order by total_jobs desc, country
"""

MARKET_OVERVIEW = """
select *
from gold.mart_job_market_overview
order by posted_date, source_name, country, city
"""

SALARY_BY_SOURCE = """
select *
from gold.mart_salary_by_source
order by source_name
"""

SALARY_BENCHMARK = """
select
    source_name,
    job_title,
    country,
    salary_mid_usd
from gold.mart_salary_benchmark
"""

JOBS_BY_SKILL = """
select *
from gold.mart_jobs_by_skill
order by total_jobs desc, skill_name
"""

HOT_SKILLS = """
select *
from gold.mart_hot_skills
order by hot_rank
"""

SKILL_TRENDS_BY_YEAR = """
select *
from gold.mart_skill_trends_by_year
order by market_year, job_count desc, skill_name
"""

COMPANY_HIRING = """
select *
from gold.mart_company_hiring
order by job_count desc, company_name
"""

DATA_QUALITY = """
select *
from gold.mart_data_quality
order by source_name
"""

DOMESTIC_VS_INTERNATIONAL = """
select *
from gold.mart_domestic_vs_international_jobs
order by market_year, source_name, market_scope
"""

DATA_ENGINEER_JOBS = """
select *
from gold.mart_data_engineer_jobs
order by posted_date desc, source_name, job_title
"""

JOBS_BY_WORK_TYPE = """
select *
from gold.mart_jobs_by_work_type
order by market_year, source_name, employment_type, work_arrangement
"""
