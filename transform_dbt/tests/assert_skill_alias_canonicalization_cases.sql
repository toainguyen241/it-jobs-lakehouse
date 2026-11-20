with test_cases(skill_alias, expected_skill_name) as (
    values
        ('nodejs', 'node.js'),
        ('reactjs', 'react'),
        ('golang', 'go'),
        ('google cloud', 'gcp'),
        ('qa qc', 'qa/qc'),
        ('phân tích nghiệp vụ', 'business analysis'),
        ('kinh nghiệm làm việc trong bệnh viện/phòng khám quốc tế', null)
),

actual as (
    select
        cases.skill_alias,
        cases.expected_skill_name,
        aliases.canonical_skill_name as actual_skill_name
    from test_cases cases
    left join {{ ref('skill_aliases') }} aliases
        on aliases.skill_alias = cases.skill_alias
)

select *
from actual
where actual_skill_name is distinct from expected_skill_name
