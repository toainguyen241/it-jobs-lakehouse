with test_cases as (
    select *
    from (
        values
            ('15.000.000 VND to 25.000.000 VND'::text, 15000000::numeric, 25000000::numeric, 'vnd'::text, 'month'::text, 'scraped'::text, null::text),
            ('1,000 - 1,500 USD', 1000::numeric, 1500::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('15m - 17m', 15000000::numeric, 17000000::numeric, 'vnd'::text, 'month'::text, 'scraped'::text, null::text),
            ('From 20.000.000 VND', 20000000::numeric, null::numeric, 'vnd'::text, 'month'::text, 'scraped'::text, null::text),
            ('From $1300', 1300::numeric, null::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('Up $1000', null::numeric, 1000::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('Up to 2.000 USD', null::numeric, 2000::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('- 1,000 USD', null::numeric, 1000::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('0 - 1,000 USD', null::numeric, 1000::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('Up to 37,000$ /year', null::numeric, 37000::numeric, 'usd'::text, 'year'::text, 'scraped'::text, null::text),
            ('$102,100 - $219,200 a year', 102100::numeric, 219200::numeric, 'usd'::text, 'year'::text, 'scraped'::text, null::text),
            ('$52,573.16 - $63,313.92 a year', 52573.16::numeric, 63313.92::numeric, 'usd'::text, 'year'::text, 'scraped'::text, null::text),
            ('$18 - $20 an hour', 18::numeric, 20::numeric, 'usd'::text, 'hour'::text, 'scraped'::text, null::text),
            ('$1,200 - $1,500 a week', 1200::numeric, 1500::numeric, 'usd'::text, 'week'::text, 'scraped'::text, null::text),
            ('35 - 40m, thỏa thuận', 35000000::numeric, 40000000::numeric, 'vnd'::text, 'month'::text, 'scraped'::text, null::text),
            ('Approximately $230', 230::numeric, 230::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('Negotiable', null::numeric, null::numeric, null::text, null::text, 'not_disclosed'::text, null::text),
            ('16.000.000 VND to 2.200.000 VND', 16000000::numeric, 22000000::numeric, 'vnd'::text, 'month'::text, 'corrected'::text, 'upper_bound_multiplied_by_10'::text),
            ('25.000.000 VND to 3.000.000 VND', 25000000::numeric, 30000000::numeric, 'vnd'::text, 'month'::text, 'corrected'::text, 'upper_bound_multiplied_by_10'::text),
            ('8.000.000 VND to 1.000.000 VND', 8000000::numeric, 10000000::numeric, 'vnd'::text, 'month'::text, 'corrected'::text, 'upper_bound_multiplied_by_10'::text),
            ('8.000.000 VND to 1.200.000 VND', 8000000::numeric, 12000000::numeric, 'vnd'::text, 'month'::text, 'corrected'::text, 'upper_bound_multiplied_by_10'::text),
            ('From 20.000.000 USD', 20000000::numeric, null::numeric, 'vnd'::text, 'month'::text, 'corrected'::text, 'currency_usd_to_vnd_due_to_implausible_value'::text),
            ('From 30.000.000 USD', 30000000::numeric, null::numeric, 'vnd'::text, 'month'::text, 'corrected'::text, 'currency_usd_to_vnd_due_to_implausible_value'::text),
            ('700 VND to 1.200 VND', 700::numeric, 1200::numeric, 'usd'::text, 'month'::text, 'corrected'::text, 'currency_vnd_to_usd_due_to_implausible_value'::text),
            ('10,000,000', 10000000::numeric, 10000000::numeric, 'vnd'::text, 'month'::text, 'scraped'::text, null::text),
            ('15.5 triệu', 15500000::numeric, 15500000::numeric, 'vnd'::text, 'month'::text, 'scraped'::text, null::text),
            ('700 USD to 500 USD', 700::numeric, 500::numeric, 'usd'::text, 'month'::text, 'invalid'::text, null::text),
            ('Competitve', null::numeric, null::numeric, null::text, null::text, 'not_disclosed'::text, null::text),
            ('You''ll surely love it', null::numeric, null::numeric, null::text, null::text, 'not_disclosed'::text, null::text),
            ('Come as you are.', null::numeric, null::numeric, null::text, null::text, 'not_disclosed'::text, null::text),
            ('Thương lượng', null::numeric, null::numeric, null::text, null::text, 'not_disclosed'::text, null::text),
            ('1.5k - 2.5k USD', 1500::numeric, 2500::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('Up to 5k USD', null::numeric, 5000::numeric, 'usd'::text, 'month'::text, 'scraped'::text, null::text),
            ('$100K - $150K a year', 100000::numeric, 150000::numeric, 'usd'::text, 'year'::text, 'scraped'::text, null::text),
            ('Từ $100/ngày', 100::numeric, null::numeric, 'usd'::text, 'day'::text, 'scraped'::text, null::text),
            ('$200 - $300 per day', 200::numeric, 300::numeric, 'usd'::text, 'day'::text, 'scraped'::text, null::text),
            ('Up to $250 a day', null::numeric, 250::numeric, 'usd'::text, 'day'::text, 'scraped'::text, null::text)
    ) as cases(
        salary_text,
        expected_min,
        expected_max,
        expected_currency,
        expected_period,
        expected_status,
        expected_correction_reason
    )
),

parsed as (
    select
        *,
        silver.parse_salary_range(salary_text) as result
    from test_cases
)

select *
from parsed
where (result).salary_min is distinct from expected_min
   or (result).salary_max is distinct from expected_max
   or (result).currency is distinct from expected_currency
   or (result).period is distinct from expected_period
   or (result).salary_status is distinct from expected_status
   or (result).correction_reason is distinct from expected_correction_reason
