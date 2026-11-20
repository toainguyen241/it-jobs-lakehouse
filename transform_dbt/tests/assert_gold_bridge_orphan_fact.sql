select bridge.*
from {{ ref('bridge_job_skills') }} bridge
left join {{ ref('fact_job_postings') }} facts
    on facts.job_sk = bridge.job_sk
   and facts.posted_date = bridge.posted_date
where facts.job_sk is null
