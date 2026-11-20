import argparse
import asyncio

from src.crawl_runner import crawl
from src.scrapers.errors import CrawlCompletenessError, SalarySessionError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl rieng ITviec.")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument(
        "--known-pages-stop",
        type=int,
        default=3,
        help="Early-stop sau N trang lien tiep chi co job da ton tai trong Bronze.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Bo qua Bronze lookup va crawl lai cac job trong pham vi --max-pages.",
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--check-session-only", action="store_true")
    args = parser.parse_args()
    args.source = "itviec"
    return args


if __name__ == "__main__":
    cli_args = parse_args()
    if cli_args.max_pages is not None and cli_args.max_pages < 1:
        raise SystemExit("--max-pages phai lon hon hoac bang 1.")
    if cli_args.known_pages_stop < 1:
        raise SystemExit("--known-pages-stop phai lon hon hoac bang 1.")
    try:
        asyncio.run(crawl(cli_args))
    except SalarySessionError as exc:
        raise SystemExit(f"[session] {exc}") from None
    except CrawlCompletenessError as exc:
        raise SystemExit(f"[completeness] {exc}") from None
