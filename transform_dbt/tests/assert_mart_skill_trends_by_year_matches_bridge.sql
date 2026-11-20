with mart_counts as (
    select market_year, sum(job_count) as association_count
    from {{ ref('mart_skill_trends_by_year') }}
    group by market_year
),

canonical_counts as (
    select
        case
            when facts.source_name = 'kaggle' then 2025
            when facts.source_name in ('itviec', 'topdev', 'topcv', 'indeed', 'weworkremotely', 'remoteok')
             and extract(year from facts.posted_date) = 2026 then 2026
        end                                                       as market_year,
        count(*)                                                  as association_count
    from {{ ref('canonical_job_skills') }} bridge
    inner join {{ ref('fact_job_postings') }} facts
        on facts.job_sk = bridge.job_sk
       and facts.posted_date = bridge.posted_date
    where facts.source_name = 'kaggle'
       or (
            facts.source_name in ('itviec', 'topdev', 'topcv', 'indeed', 'weworkremotely', 'remoteok')
            and extract(year from facts.posted_date) = 2026
       )
    group by 1
)

select
    coalesce(mart.market_year, canonical.market_year) as market_year,
    mart.association_count as mart_associations,
    canonical.association_count as canonical_associations
from mart_counts mart
full outer join canonical_counts canonical
    on canonical.market_year = mart.market_year
where mart.association_count is distinct from canonical.association_count
