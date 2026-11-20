import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

from playwright.async_api import Error as PlaywrightError

from src.pages.base_page import BasePage

JOB_LINK_SELECTOR = (
    "h3[data-search--job-selection-target='jobTitle'] a[href*='/it-jobs/']"
)


class ITviecJobListPage(BasePage):
    BASE_URL = "https://itviec.com/it-jobs"
    NAVIGATION_ATTEMPTS = 5

    async def goto_page(self, page_num: int) -> bool:
        """Mở một trang listing, retry nếu ITviec trả DOM rỗng tạm thời."""
        target_url = f"{self.BASE_URL}?page={page_num}&query=&source=search_job"
        for attempt in range(1, self.NAVIGATION_ATTEMPTS + 1):
            response = None
            try:
                response = await self.page.goto(
                    target_url, wait_until="domcontentloaded", timeout=30_000
                )
                await self.page.wait_for_selector(JOB_LINK_SELECTOR, timeout=15_000)
            except PlaywrightError:
                pass

            actual_page = parse_qs(urlsplit(self.page.url).query).get("page", [""])[0]
            has_expected_page = actual_page == str(page_num)
            has_job_links = await self.page.locator(JOB_LINK_SELECTOR).count() > 0
            if has_expected_page and has_job_links:
                # Pacing nhẹ để tránh ITviec trả listing rỗng khi đổi trang liên tục.
                await self.page.wait_for_timeout(1_000)
                return True

            status = response.status if response else "no-response"
            if attempt < self.NAVIGATION_ATTEMPTS:
                delay_ms = attempt * 2_000
                print(
                    f"[itviec] Trang {page_num} chua san sang "
                    f"(lan {attempt}/{self.NAVIGATION_ATTEMPTS}, status={status}, "
                    f"url={self.page.url}); thu lai sau {delay_ms // 1000}s."
                )
                await self.page.wait_for_timeout(delay_ms)

        return False

    async def get_job_urls(self) -> list[str]:
        hrefs = await self.safe_attr_all(JOB_LINK_SELECTOR, "href")
        result: list[str] = []
        for href in hrefs:
            parts = urlsplit(href)
            canonical = urlunsplit(
                (
                    parts.scheme or "https",
                    parts.netloc or "itviec.com",
                    parts.path,
                    "",
                    "",
                )
            )
            if canonical not in result:
                result.append(canonical)
        return result

    async def has_jobs(self) -> bool:
        return await self.page.locator(JOB_LINK_SELECTOR).count() > 0

    async def get_total_jobs(self) -> int:
        headline = await self.safe_text("h1.headline-total-jobs")
        match = re.search(r"([\d,.]+)\s+IT jobs", headline or "", re.I)  # noqa: FURB167
        if not match:
            raise ValueError("Khong doc duoc tong so job ITviec.")
        return int(re.sub(r"\D", "", match.group(1)))

    async def get_total_pages(self) -> int:
        text = await self.safe_text(".pagination-search-jobs")
        pages = [int(value) for value in re.findall(r"\b\d+\b", text or "")]
        if not pages:
            raise ValueError("Khong doc duoc tong so trang ITviec.")
        return max(pages)

    async def has_next_page(self) -> bool:
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await self.page.wait_for_timeout(500)
        return await self.page.locator("a[rel='next']").count() > 0
