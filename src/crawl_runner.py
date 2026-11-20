from __future__ import annotations

import argparse
from pathlib import Path

from playwright.async_api import async_playwright

from src.incremental_state import (
    load_existing_job_ids,
    record_crawl_failures,
    record_crawl_outcomes,
)
from src.output.parquet_writer import write_jobs_parquet
from src.scrapers.itviec_scraper import ITviecScraper


def browser_launch_args(source: str) -> list[str]:
    """Trả về Chromium args cần thiết cho từng source."""
    launch_args = ["--disable-blink-features=AutomationControlled"]
    if source == "topdev":
        launch_args.append("--host-resolver-rules=MAP topdev.vn www.topdev.vn")
    return launch_args


def _unsupported_source(source: str, exc: ImportError) -> NotImplementedError:
    """Biến ImportError khó hiểu thành thông báo rõ ràng cho crawler local-only."""
    error = NotImplementedError(
        f"Crawler cho nguon '{source}' khong co trong repo public -- day la "
        "crawler local/manual khong phai loi thieu code. Chi '--source itviec' "
        "duoc ho tro tren fresh clone."
    )
    return error


async def crawl(args: argparse.Namespace) -> Path | None:
    """Chạy crawler được chọn và ghi kết quả ra Parquet."""
    selected = []
    if args.source == "topdev":
        try:
            from crawl.scrapers.topdev_scraper import TopDevScraper
        except ImportError as exc:
            raise _unsupported_source(args.source, exc) from exc

        selected.append(TopDevScraper("crawl/storage_state/topdev_state.json"))
    elif args.source == "itviec":
        selected.append(ITviecScraper("storage_state/itviec_state.json"))
    elif args.source == "topcv":
        try:
            from crawl.scrapers.topcv_scraper import TopCVScraper
        except ImportError as exc:
            raise _unsupported_source(args.source, exc) from exc

        selected.append(TopCVScraper())
    elif args.source == "indeed":
        try:
            from crawl.scrapers.indeed_scraper import IndeedScraper
        except ImportError as exc:
            raise _unsupported_source(args.source, exc) from exc

        selected.append(IndeedScraper("crawl/storage_state/indeed_state.json"))
    elif args.source == "weworkremotely":
        try:
            from crawl.scrapers.weworkremotely_scraper import WeWorkRemotelyScraper
        except ImportError as exc:
            raise _unsupported_source(args.source, exc) from exc

        selected.append(WeWorkRemotelyScraper())
    elif args.source == "remoteok":
        try:
            from crawl.scrapers.remoteok_scraper import RemoteOKScraper
        except ImportError as exc:
            raise _unsupported_source(args.source, exc) from exc

        selected.append(RemoteOKScraper())
    else:
        raise ValueError(f"Nguon crawl khong duoc ho tro: {args.source}")

    existing_job_ids: set[str] | None = None
    if not getattr(args, "full_refresh", False) and not getattr(
        args, "check_session_only", False
    ):
        existing_job_ids = load_existing_job_ids(args.source)
        print(
            f"[{args.source}] Incremental mode: Bronze da co "
            f"{len(existing_job_ids)} job_id_nk."
        )

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=not args.headed,
            args=browser_launch_args(args.source),
        )
        try:
            for scraper in selected:
                if getattr(args, "check_session_only", False):
                    context = await scraper.new_context(browser)
                    try:
                        checker = getattr(scraper, "check_salary_session", None)
                        if checker is not None:
                            await checker(context)
                        else:
                            await scraper.get_job_urls(context, max_pages=1)
                    finally:
                        await context.close()
                    print(
                        f"[{scraper.source_name}] Kiem tra session xong; "
                        "khong crawl, khong ghi Parquet."
                    )
                    return None

                jobs = await scraper.scrape_all(
                    browser,
                    max_pages=args.max_pages,
                    existing_job_ids=existing_job_ids,
                    known_pages_stop=getattr(args, "known_pages_stop", 3),
                )
                rejected_jobs = getattr(scraper, "rejected_jobs", [])
                if rejected_jobs:
                    record_crawl_outcomes(
                        scraper.source_name,
                        rejected_jobs,
                        status="rejected",
                    )
                    print(
                        f"[{scraper.source_name}] Da ghi nho "
                        f"{len(rejected_jobs)} job rejected."
                    )
                failed_jobs = getattr(scraper, "failed_jobs", [])
                if failed_jobs:
                    outcomes = record_crawl_failures(scraper.source_name, failed_jobs)
                    details = {job_id: (url, why) for job_id, url, why in failed_jobs}
                    for job_id, status, attempts in outcomes:
                        url, why = details.get(job_id, (None, None))
                        label = "QUARANTINED" if status == "quarantined" else "FAILED"
                        print(
                            f"[{scraper.source_name}] {label} {job_id} "
                            f"(lan {attempts}) {url}: {why}"
                        )
                if not jobs:
                    print(
                        f"[{scraper.source_name}] Khong co job moi; "
                        "khong ghi Parquet, khong load Bronze."
                    )
                    print("NO_NEW_JOBS")
                    return None
                output_path = write_jobs_parquet(jobs, scraper.source_name)
                clear_checkpoints = getattr(scraper, "clear_checkpoints", None)
                if clear_checkpoints is not None:
                    clear_checkpoints()
                resolved_path = output_path.resolve()
                print(
                    f"[{scraper.source_name}] Da luu {len(jobs)} dong vao "
                    f"{resolved_path}"
                )
                print(f"PARQUET_PATH={resolved_path}")
                return resolved_path
        finally:
            await browser.close()

    return None
