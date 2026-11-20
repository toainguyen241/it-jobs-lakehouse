from datetime import datetime, timezone

from playwright.async_api import BrowserContext

from src.pages.itviec_job_detail_page import ITviecJobDetailPage
from src.pages.itviec_job_list_page import ITviecJobListPage
from src.schemas.raw_job import RawJobPosting
from src.scrapers.base import BaseScraper
from src.scrapers.errors import CrawlCompletenessError, SalarySessionError
from src.scrapers.incremental import (
    IncrementalUrlSelector,
    cap_hit_message,
    job_id_from_url,
)
from src.scrapers.normalization import (
    classify_time_info,
    clean_list,
    clean_optional,
    extract_city,
    extract_experience,
    normalize_posted_date,
    short_description,
)


class ITviecScraper(BaseScraper):
    source_name = "itviec"

    async def _validate_salary_session(
        self, context: BrowserContext, sample_urls: list[str]
    ) -> None:
        page = await context.new_page()
        try:
            visible_salary_count = 0
            for index, sample_url in enumerate(sample_urls[:5], start=1):
                detail = ITviecJobDetailPage(page)
                await detail.goto(sample_url)
                title = await detail.get_title()
                salary = clean_optional(await detail.get_salary_text())
                if salary:
                    visible_salary_count += 1
                print(
                    f"[itviec] Session sample {index}/{min(len(sample_urls), 5)}: "
                    f"{title or sample_url} | salary_text={salary or 'NULL'}"
                )
            if not visible_salary_count:
                raise SalarySessionError(
                    "5 mau ITviec deu khong co salary_text; "
                    "itviec_state.json khong duoc website cong nhan."
                )
            print(
                f"[itviec] SESSION OK - {visible_salary_count}/"
                f"{min(len(sample_urls), 5)} mau co salary field va khong co login prompt."
            )
        finally:
            await page.close()

    async def get_job_urls(
        self,
        context: BrowserContext,
        max_pages: int | None = None,
        existing_job_ids: set[str] | None = None,
        known_pages_stop: int = 3,
    ) -> list[str]:
        page = await context.new_page()
        try:
            list_page = ITviecJobListPage(page)
            job_urls: list[str] = []
            incremental = existing_job_ids is not None
            selector = IncrementalUrlSelector(
                existing_job_ids or set(), known_pages_stop
            )
            if not await list_page.goto_page(1):
                raise CrawlCompletenessError(
                    "ITviec trang 1 khong tai duoc sau nhieu lan thu."
                )
            expected_jobs = await list_page.get_total_jobs()
            expected_pages = await list_page.get_total_pages()
            pages_to_crawl = min(expected_pages, max_pages or expected_pages)
            print(
                f"[itviec] Website cong bo {expected_jobs} job / "
                f"{expected_pages} trang; se crawl {pages_to_crawl} trang."
            )
            first_page_urls = await list_page.get_job_urls()
            if not first_page_urls:
                raise CrawlCompletenessError("ITviec trang 1 khong co URL job.")
            await self._validate_salary_session(context, first_page_urls)
            if existing_job_ids:
                # Job đã biết ở trang 1 để làm canary khi có job detail lỗi.
                self.canary_url = next(
                    (
                        u
                        for u in first_page_urls
                        if job_id_from_url(u) in existing_job_ids
                    ),
                    None,
                )
            first_selection = selector.select_page(first_page_urls)
            job_urls.extend(first_selection.new_urls)
            print(
                f"[itviec] Trang 1: {len(first_page_urls)} job, "
                f"moi {len(first_selection.new_urls)}, "
                f"da co {first_selection.known_count}, tong moi {len(job_urls)} URL."
            )
            if incremental and first_selection.should_stop:
                print(
                    f"[itviec] Early-stop: {known_pages_stop} trang lien tiep "
                    "chi co job da biet."
                )
                return job_urls
            stopped_early = False
            last_page_new = len(first_selection.new_urls)
            for page_num in range(2, pages_to_crawl + 1):
                if not await list_page.goto_page(page_num):
                    raise CrawlCompletenessError(
                        f"ITviec trang {page_num}/{expected_pages} khong tai duoc "
                        f"sau {list_page.NAVIGATION_ATTEMPTS} lan thu."
                    )
                page_urls = await list_page.get_job_urls()
                selection = selector.select_page(page_urls)
                job_urls.extend(selection.new_urls)
                last_page_new = len(selection.new_urls)
                print(
                    f"[itviec] Trang {page_num}: {len(page_urls)} job, "
                    f"moi {len(selection.new_urls)}, "
                    f"da co {selection.known_count}, tong moi {len(job_urls)} URL."
                )
                if incremental and selection.should_stop:
                    print(
                        f"[itviec] Early-stop tai trang {page_num}: "
                        f"{known_pages_stop} trang lien tiep chi co job da biet."
                    )
                    stopped_early = True
                    break
            cap_warning = cap_hit_message(
                incremental=incremental,
                stopped_early=stopped_early,
                pages_crawled=pages_to_crawl,
                expected_pages=expected_pages,
                last_page_new=last_page_new,
            )
            if cap_warning:
                print(f"[itviec] {cap_warning}")
            if not incremental and max_pages is None and len(job_urls) != expected_jobs:
                raise CrawlCompletenessError(
                    f"ITviec thieu URL: website={expected_jobs}, crawl={len(job_urls)}."
                )
            if not incremental and max_pages is None:
                print(f"[itviec] Da doi chieu du {len(job_urls)}/{expected_jobs} URL.")
            return job_urls
        finally:
            await page.close()

    async def scrape_job_detail(
        self, context: BrowserContext, url: str
    ) -> RawJobPosting:
        page = await context.new_page()
        try:
            detail = ITviecJobDetailPage(page)
            await detail.goto(url)
            title = await detail.get_title()
            company_name = await detail.get_company_name()
            if not title or not company_name:
                raise ValueError("Trang chi tiet thieu job_title hoac company_name.")
            time_info_raw = await detail.get_time_info_raw()
            # Một nguồn duy nhất cho job_id_nk: selector incremental va record.
            job_id_nk = job_id_from_url(url)
            if not job_id_nk:
                raise ValueError(f"Khong tach duoc job_id_nk tu URL: {url}.")
            return RawJobPosting(
                job_id_nk=job_id_nk,
                source_name="itviec",
                scraped_at=datetime.now(timezone.utc),  # noqa: UP017
                job_title=title.strip(),
                company_name=company_name.strip(),
                experience=extract_experience(await detail.get_experience_raw()),
                salary_text=clean_optional(await detail.get_salary_text()),
                location=extract_city(await detail.get_location_raw()),
                skills=clean_list(await detail.get_required_skills()),
                job_type=clean_optional(await detail.get_job_type()),
                job_description=short_description(await detail.get_description_raw()),
                company_size=clean_optional(await detail.get_company_size_raw()),
                industry=clean_optional(await detail.get_industry()),
                country=clean_optional(await detail.get_country()),
                posted_date=normalize_posted_date(await detail.get_posted_date()),  # type: ignore
                time_info_raw=clean_optional(time_info_raw),
                time_info_label=classify_time_info(time_info_raw),  # type: ignore
            )
        finally:
            await page.close()
