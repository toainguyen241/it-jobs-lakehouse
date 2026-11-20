from abc import ABC, abstractmethod
from pathlib import Path

from playwright.async_api import BrowserContext

from src.schemas.raw_job import RawJobPosting
from src.scrapers.errors import (
    CrawlCompletenessError,
    JobFilteredOutError,
    SalarySessionError,
)
from src.scrapers.incremental import job_id_from_url


class BaseScraper(ABC):
    source_name: str

    def __init__(self, storage_state_path: str | None = None):
        self.storage_state_path: str | None = None
        if storage_state_path is not None:
            state_path = Path(storage_state_path)
            if not state_path.is_file():
                raise FileNotFoundError(
                    f"Khong tim thay storage_state bat buoc: {state_path}"
                )
            self.storage_state_path = str(state_path)

    def _context_options(self) -> dict:
        return {
            "viewport": {"width": 1280, "height": 900},
            "locale": "en-US",
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
        }

    async def new_context(self, browser) -> BrowserContext:
        options = self._context_options()
        if self.storage_state_path is not None:
            options["storage_state"] = self.storage_state_path
        return await browser.new_context(**options)

    @abstractmethod
    async def get_job_urls(
        self,
        context: BrowserContext,
        max_pages: int | None,
        existing_job_ids: set[str] | None = None,
        known_pages_stop: int = 3,
    ) -> list[str]: ...

    @abstractmethod
    async def scrape_job_detail(
        self, context: BrowserContext, url: str
    ) -> RawJobPosting: ...

    async def _canary_healthy(self, context: BrowserContext) -> bool | None:
        """Scrape thử 1 job đã biết để phân biệt lỗi riêng job vs lỗi hệ thống.
        None: không có canary (vd lần đầu crawl). True: trang detail vẫn parse được -> lỗi của các job mới là riêng từng job. False: parse hỏng ngay cả với job từng thành công -> nghi DOM/session drift.
        """
        url = getattr(self, "canary_url", None)
        if not url:
            return None
        try:
            await self.scrape_job_detail(context, url)
        except JobFilteredOutError:
            return True  # trang parse được, chỉ là job non-IT.
        except SalarySessionError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"\n[{self.source_name}] Canary loi {url}: {exc}")
            return False
        return True

    async def scrape_all(
        self,
        browser,
        max_pages: int | None = None,
        existing_job_ids: set[str] | None = None,
        known_pages_stop: int = 3,
    ) -> list[RawJobPosting]:
        context = await self.new_context(browser)
        self.rejected_jobs: list[tuple[str, str, str]] = []
        # Job lỗi riêng lẻ (job_id, url, lý do): scrape_all trả về kết quả một phần, caller ghi nhận attempts/quarantine.
        self.failed_jobs: list[tuple[str, str, str]] = []
        self.canary_url: str | None = None
        try:
            job_urls = await self.get_job_urls(
                context,
                max_pages,
                existing_job_ids=existing_job_ids,
                known_pages_stop=known_pages_stop,
            )
            total = len(job_urls)
            print(f"[{self.source_name}] Bat dau crawl chi tiet {total} job.")
            results: list[RawJobPosting] = []
            filtered_count = 0
            untracked_failures = 0
            for index, url in enumerate(job_urls, start=1):
                percent = (index / total * 100) if total else 100
                print(
                    f"\r[{self.source_name}] Chi tiet: {index}/{total} "
                    f"({percent:5.1f}%)",
                    end="",
                    flush=True,
                )
                try:
                    results.append(await self.scrape_job_detail(context, url))
                except JobFilteredOutError as exc:
                    filtered_count += 1
                    job_id = job_id_from_url(url)
                    if job_id:
                        self.rejected_jobs.append((job_id, url, str(exc)))
                    print(f"\n[{self.source_name}] Bo job non-IT: {exc}")
                except SalarySessionError:
                    print()
                    raise
                except Exception as exc:  # noqa: BLE001
                    job_id = job_id_from_url(url)
                    if job_id:
                        self.failed_jobs.append((job_id, url, str(exc)[:300]))
                    else:
                        untracked_failures += 1
                    print(f"\n[{self.source_name}] Loi crawl {url}: {exc}")
            if total:
                print()
            failed_count = len(self.failed_jobs) + untracked_failures
            if failed_count:
                # Fail-closed chỉ còn cho nghi vấn hệ thống: không job nào thành công và canary (job đã biết) cũng không parse được, hoặc job lỗi không định danh được để theo dõi attempts.
                healthy = bool(results) or await self._canary_healthy(context) is True
                if untracked_failures or not healthy:
                    raise CrawlCompletenessError(
                        f"{self.source_name}: {failed_count}/{total} job detail bi "
                        "loi va khong xac nhan duoc la loi rieng tung job; "
                        "khong ghi Parquet."
                    )
                print(
                    f"[{self.source_name}] CANH BAO: {failed_count}/{total} job "
                    "loi rieng le; se thu lai o lan sau (quarantine sau nhieu lan)"
                )
            print(
                f"[{self.source_name}] Hoan tat: {len(results)}/{total} job IT; "
                f"bo {filtered_count} job non-IT."
            )
            return results
        finally:
            await context.close()
