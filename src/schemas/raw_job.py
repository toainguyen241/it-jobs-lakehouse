from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RawJobPosting(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_id_nk: str = Field(min_length=1)
    source_name: Literal[
        "itviec",
        "topdev",
        "topcv",
        "indeed",
        "weworkremotely",
        "remoteok",
    ]
    scraped_at: datetime
    job_title: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    experience: str | None = None
    salary_text: str | None = None
    location: str | None = None
    skills: list[str] = Field(default_factory=list)
    job_type: str | None = None
    job_description: str | None = Field(default=None, max_length=300)
    company_size: str | None = None
    industry: str | None = None
    country: str | None = None
    posted_date: date | None = None
    time_info_raw: str | None = None
    time_info_label: Literal["posted", "deadline"] | None = None

    @field_validator(
        "experience",
        "salary_text",
        "location",
        "job_type",
        "job_description",
        "company_size",
        "industry",
        "country",
        "time_info_raw",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in result:
                result.append(cleaned)
        return result

    @field_validator("scraped_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scraped_at phai co timezone.")
        return value
