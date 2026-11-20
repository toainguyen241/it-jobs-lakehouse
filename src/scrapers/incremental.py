from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit


def job_id_from_url(url: str) -> str | None:
    parts = urlsplit(url)
    query_job_id = parse_qs(parts.query).get("jk", [""])[0].strip()
    if query_job_id:
        return query_job_id
    path = parts.path.rstrip("/")
    if not path:
        return None
    job_id = path.rsplit("/", 1)[-1].strip()
    if job_id.lower().endswith(".html"):
        job_id = job_id[:-5]
    return job_id or None


@dataclass(frozen=True)
class PageSelection:
    new_urls: list[str]
    known_count: int
    consecutive_known_pages: int
    should_stop: bool


class IncrementalUrlSelector:
    """Giữ URL chưa có trong Bronze và stop sau nhiều trang toàn job cũ."""

    def __init__(self, existing_ids: set[str], stop_after_known_pages: int = 3):
        if stop_after_known_pages < 1:
            raise ValueError("stop_after_known_pages phai lon hon hoac bang 1.")
        self.existing_ids = existing_ids
        self.stop_after_known_pages = stop_after_known_pages
        self._selected_ids: set[str] = set()
        self._selected_urls: set[str] = set()
        self._consecutive_known_pages = 0

    def select_page(self, urls: list[str]) -> PageSelection:
        new_urls: list[str] = []
        known_count = 0

        for url in urls:
            job_id = job_id_from_url(url)
            selection_key = job_id or url
            if job_id in self.existing_ids:
                known_count += 1
                continue
            if selection_key in self._selected_ids or url in self._selected_urls:
                known_count += 1
                continue
            self._selected_ids.add(selection_key)
            self._selected_urls.add(url)
            new_urls.append(url)

        if urls and not new_urls:
            self._consecutive_known_pages += 1
        else:
            self._consecutive_known_pages = 0

        return PageSelection(
            new_urls=new_urls,
            known_count=known_count,
            consecutive_known_pages=self._consecutive_known_pages,
            should_stop=(self._consecutive_known_pages >= self.stop_after_known_pages),
        )


def cap_hit_message(
    *,
    incremental: bool,
    stopped_early: bool,
    pages_crawled: int,
    expected_pages: int,
    last_page_new: int,
) -> str | None:
    """Cảnh báo khi crawl dừng vì chạm trần --max-pages chứ không phải early-stop."""
    if not incremental or stopped_early:
        return None
    if pages_crawled >= expected_pages or last_page_new <= 0:
        return None
    return (
        f"CAP_HIT: dung o tran {pages_crawled}/{expected_pages} trang nhung trang "
        f"cuoi van con {last_page_new} job moi; cac job o trang sau co the bi bo "
        "lo. Can nhac tang --max-pages."
    )
