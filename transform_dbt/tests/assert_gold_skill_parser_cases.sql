with test_cases(raw_skills) as (
    values
        ('Python, SQL; Docker|Airflow' || chr(10) || 'Node.js'),
        ('["C++", "C#", ".NET"]')
),

actual as (
    select distinct
        {{ gold_normalize_skill('skill.value') }}                as skill_name
    from test_cases
    cross join lateral {{ gold_split_skills('raw_skills') }} as skill(value)
    where {{ gold_normalize_skill('skill.value') }} is not null
),

expected(skill_name) as (
    values
        ('python'),
        ('sql'),
        ('docker'),
        ('airflow'),
        ('node.js'),
        ('c++'),
        ('c#'),
        ('.net')
),

differences as (
    (select * from actual except select * from expected)
    union all
    (select * from expected except select * from actual)
)

select *
from differences
