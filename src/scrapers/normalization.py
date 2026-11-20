from __future__ import annotations

import re
import unicodedata

_CITY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:thanh pho\s+)?ho chi minh\b|\btp\.?\s*hcm\b|\bsaigon\b", "Hồ Chí Minh"),
    (r"\b(?:thanh pho\s+)?ha noi\b", "Hà Nội"),
    (r"\b(?:thanh pho\s+)?da nang\b", "Đà Nẵng"),
    (r"\b(?:thanh pho\s+)?hai phong\b", "Hải Phòng"),
    (r"\b(?:thanh pho\s+)?can tho\b", "Cần Thơ"),
)


def _ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    folded = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

    return folded.lower().replace("đ", "d")


def extract_city(raw: str | None) -> str | None:
    """Trả về tên thành phố, giữ nhiều thành phố nếu tìm thấy nhiều nơi làm việc."""
    if not raw:
        return None
    folded = _ascii_fold(raw)
    matches: list[tuple[int, str]] = []
    for pattern, city in _CITY_PATTERNS:
        match = re.search(pattern, folded, re.IGNORECASE)
        if match:
            matches.append((match.start(), city))
    if matches:
        return " - ".join(city for _, city in sorted(matches))

    candidate = re.split(r"\s+-\s+|,", raw)[-1].strip()
    candidate = re.sub(r"^(?:Thành phố|City of)\s+", "", candidate, flags=re.I)  # noqa: FURB167
    return candidate or None


_EXPERIENCE_FALLBACK_MAX_LEN = 80


def extract_experience(raw: str | None) -> str | None:
    if not raw:
        return None
    if re.search(r"not required|no experience|không yêu cầu", raw, re.I):  # noqa: FURB167
        return "Không yêu cầu"
    matches = re.findall(
        r"(?:từ\s+)?\d+(?:\s*[-–]\s*\d+)?\+?\s*(?:năm|years?)",
        raw,
        flags=re.I,  # noqa: FURB167
    )
    unique: list[str] = []
    for value in matches:
        value = re.sub(r"\s+", " ", value).strip()
        if value not in unique:
            unique.append(value)
    if unique:
        return "; ".join(unique)
    fallback = clean_optional(raw)
    return (
        fallback if fallback and len(fallback) <= _EXPERIENCE_FALLBACK_MAX_LEN else None
    )


def short_description(raw: str | None, limit: int = 300) -> str | None:
    text = clean_optional(raw)
    if not text:
        return None
    text = re.sub(
        r"^(?:Job description|Mô tả công việc|Your role & responsibilities)\s*",
        "",
        text,
        flags=re.I,  # noqa: FURB167
    )
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{clipped}…"


def classify_time_info(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.lower()
    if "left" in value or "deadline" in value or "hạn nộp" in value:
        return "deadline"
    if (
        "posted" in value
        or "ago" in value
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[t ].*)?", value)
    ):
        return "posted"
    return None


def normalize_posted_date(raw: str | None) -> str | None:
    """Lấy phần YYYY-MM-DD từ datePosted."""
    if not raw:
        return None
    match = re.match(r"\s*(\d{4}-\d{2}-\d{2})(?:[T ]|$)", raw)
    return match.group(1) if match else None


def clean_optional(raw: str | None) -> str | None:
    if not raw:
        return None
    value = re.sub(r"\s+", " ", raw).strip()
    return value or None


def clean_list(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = clean_optional(value)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result
