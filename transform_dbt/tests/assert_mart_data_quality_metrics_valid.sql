select *
from {{ ref('mart_data_quality') }}
where total_jobs < 0
   or jobs_missing_company > total_jobs
   or jobs_missing_location > total_jobs
   or jobs_with_salary > total_jobs
   or jobs_with_invalid_salary < 0
   or jobs_missing_posted_date < 0
   or jobs_without_skills > total_jobs
   or salary_coverage_rate not between 0 and 1
   or skills_coverage_rate not between 0 and 1
