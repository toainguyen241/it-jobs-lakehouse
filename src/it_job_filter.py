from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import pandas as pd

IT_TITLE_PATTERN = re.compile(
    r"("
    r"\b(?:software|web|mobile|android|ios) "
    r"(?:engineer|developer|architect|designer)\b|"
    r"\b(?:frontend|backend|full[ -]?stack)\b|"
    r"\b(?:developer|programmer|devops|site reliability|sre)\b|"
    r"\bdata (?:engineer|analyst|scientist|architect|quality|governance)\b|"
    r"\b(?:database|dba|machine learning|deep learning|computer vision|nlp)\b|"
    r"\bai (?:engineer|developer|researcher|specialist|architect)\b|"
    r"\b(?:cyber|information|network|cloud|application) security\b|"
    r"\b(?:network|system|cloud|platform|infrastructure) "
    r"(?:engineer|architect|administrator|admin|specialist)\b|"
    r"\b(?:solution|solutions) architect\b|"
    r"\b(?:qa|quality assurance|automation|manual|software) (?:engineer|tester)\b|"
    r"\b(?:business analyst|product owner|scrum master|engineering manager)\b|"
    r"\b(?:ui[ /-]?ux|ux[ /-]?ui|ui designer|ux designer|web designer)\b|"
    r"\b(?:embedded|firmware|blockchain|game developer|unity developer)\b|"
    r"\b(?:it|technical|tech) "
    r"(?:engineer|specialist|support|help ?desk|administrator|admin|operations|"
    r"infrastructure|project manager|product manager|risk|auditor)\b|"
    r"\b(?:help ?desk|service desk|sap|erp|brse|comtor)\b|"
    r"lập trình|phần mềm|công nghệ thông tin|trí tuệ nhân tạo|học máy|"
    r"an ninh mạng|bảo mật (?:thông tin|dữ liệu)|quản trị (?:mạng|hệ thống)|"
    r"kiểm thử|kỹ sư (?:dữ liệu|cầu nối)|phân tích (?:nghiệp vụ|dữ liệu)|"
    r"kiến trúc sư giải pháp|phát triển ứng dụng|"
    r"giảng viên (?:it|cntt|công nghệ thông tin)|"
    r"(?:it|computer science) lecturer"
    r")",
    re.IGNORECASE,
)

NON_IT_TITLE_PATTERN = re.compile(
    r"("
    r"\b(?:sales|telesales|marketing|accountant|accounting|finance|financial advisor)\b|"
    r"\b(?:human resources|hr|recruiter|recruitment|talent acquisition)\b|"
    r"\b(?:legal|lawyer|mechanical|civil|construction|architectural)\b|"
    r"\b(?:logistics|warehouse|receptionist|teacher|lecturer|cashier|teller)\b|"
    r"\b(?:content writer|copywriter|video editor|graphic designer|interior designer)\b|"
    r"\b(?:customer care|customer service|insurance|procurement|purchasing)\b|"
    r"\b(?:restaurant|hotel|tourism|real estate|medical|pharmacist)\b|"
    r"kinh doanh|tiếp thị|kế toán|tài chính|nhân sự|tuyển dụng|pháp lý|luật sư|"
    r"cơ khí|xây dựng|kiến trúc|xuất nhập khẩu|kho vận|lễ tân|"
    r"giảng viên|giáo viên|chăm sóc khách hàng|giao dịch viên|bảo hiểm|"
    r"thu mua|nhà hàng|khách sạn|du lịch"
    r")",
    re.IGNORECASE,
)

# Tiêu đề khớp từ khóa non-IT nhưng có token IT mạnh thì vẫn giữ lại.

STRONG_IT_TITLE_TOKEN_PATTERN = re.compile(
    r"\b(?:ai|data(?! entry)|automation|tech|solutions? engineer)\b",
    re.IGNORECASE,
)

TECH_SKILL_PATTERN = re.compile(
    r"("
    r"\bpython\b|\bjava\b|javascript|typescript|\bc\+\+\b|\bc#\b|\.net|\bphp\b|"
    r"golang|\bruby\b|kotlin|\bswift\b|react(?:js)?|angular|vue(?:js)?|node(?:js)?|"
    r"django|flask|fastapi|spring boot|laravel|\bsql\b|mysql|postgresql|oracle database|"
    r"mongodb|redis|snowflake|apache spark|hadoop|kafka|airflow|\bdbt\b|"
    r"\baws\b|azure|\bgcp\b|docker|kubernetes|\blinux\b|\bgit\b|ci/cd|"
    r"rest api|microservice|machine learning|deep learning|tensorflow|pytorch|"
    r"computer vision|cybersecurity|information security|network security|"
    r"salesforce|power bi|tableau|selenium|appium|\bunity\b|unreal engine|"
    r"embedded|firmware|\biot\b"
    r")",
    re.IGNORECASE,
)

IT_INDUSTRY_PATTERN = re.compile(
    r"(?:information technology|software|computer|internet|cybersecurity|"
    r"công nghệ thông tin|phần mềm)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RejectedJob:
    job_id_nk: str
    job_title: str
    reason: str


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def _skills_text(skills: Any) -> str:
    if skills is None:
        return ""
    if isinstance(skills, str):
        return skills
    if isinstance(skills, Iterable):
        return " ".join(_text(skill) for skill in skills)
    return _text(skills)


def classify_it_job(
    job_title: Any,
    skills: Any = None,
    industry: Any = None,
) -> tuple[bool, str]:
    """Classify one row without rejecting roles merely because they are unknown."""
    title = _text(job_title)
    skill_text = _skills_text(skills)
    industry_text = _text(industry)

    if IT_TITLE_PATTERN.search(title):
        return True, "it_title"

    non_it_match = NON_IT_TITLE_PATTERN.search(title)
    if non_it_match:
        if TECH_SKILL_PATTERN.search(skill_text):
            return True, "non_it_title_with_technical_skills"
        if STRONG_IT_TITLE_TOKEN_PATTERN.search(title):
            return True, "non_it_title_with_it_title_token"
        return False, f"explicit_non_it_title:{non_it_match.group(0).casefold()}"

    if TECH_SKILL_PATTERN.search(skill_text):
        return True, "technical_skills"
    if IT_INDUSTRY_PATTERN.search(industry_text):
        return True, "it_industry"

    return True, "no_explicit_non_it_signal"


def filter_non_it_rows(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[RejectedJob]]:
    """Return accepted rows and clearly non-IT rows rejected from the load."""
    accepted_indexes: list[Any] = []
    rejected: list[RejectedJob] = []

    for index, row in df.iterrows():
        is_it, reason = classify_it_job(
            row.get("job_title"),
            row.get("skills"),
            row.get("industry"),
        )
        if is_it:
            accepted_indexes.append(index)
            continue
        rejected.append(
            RejectedJob(
                job_id_nk=_text(row.get("job_id_nk")),
                job_title=_text(row.get("job_title")),
                reason=reason,
            )
        )

    return df.loc[accepted_indexes].reset_index(drop=True), rejected
