with cases as (
    select *
    from (
        values
            ('weworkremotely'::text, '$120-$170/hr'::text, 120::numeric, 170::numeric, 'hour'::text),
            ('weworkremotely'::text, '$5,000/mo'::text, 5000::numeric, 5000::numeric, 'month'::text),
            ('weworkremotely'::text, '$100,000 - $150,000'::text, 100000::numeric, 150000::numeric, 'year'::text),
            ('indeed'::text, '10,000,000 VND - 15,000,000 VND a year'::text, 10000000::numeric, 15000000::numeric, 'month'::text),
            ('indeed'::text, '10,000,000 VNĐ - 15,000,000 VNĐ a year'::text, 10000000::numeric, 15000000::numeric, 'month'::text),
            ('indeed'::text, '20,000,000 VNĐ a year'::text, 20000000::numeric, 20000000::numeric, 'month'::text)
    ) as c(source_name, salary_text, expected_min, expected_max, expected_period)
),

parsed as (
    select
        *,
        silver.parse_salary_range(
            {{ normalized_crawled_salary_text('source_name', 'salary_text') }}
        ) as result
    from cases
)

select *
from parsed
where (result).salary_min is distinct from expected_min
   or (result).salary_max is distinct from expected_max
   or (result).period is distinct from expected_period
