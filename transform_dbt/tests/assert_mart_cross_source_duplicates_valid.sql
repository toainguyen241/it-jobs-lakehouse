select *
from {{ ref('mart_cross_source_duplicates') }}
where left_job_sk >= right_job_sk
   or left_source_name = right_source_name
   or posted_date_gap_days < 0
   or posted_date_gap_days > 14
   or confidence_score < 0
   or confidence_score > 1
   or title_similarity < 0.78
   or company_similarity < 0.88
