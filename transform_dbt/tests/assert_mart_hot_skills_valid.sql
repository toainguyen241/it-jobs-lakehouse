select *
from {{ ref('mart_hot_skills') }}
where hot_rank not between 1 and 20
   or job_count <= 0
   or source_count <= 0
   or window_start_date > window_end_date
   or latest_skill_posted_date not between window_start_date and window_end_date
