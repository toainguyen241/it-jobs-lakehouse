from __future__ import annotations

import asyncio
import os
import socket
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Error, Page, async_playwright

LOGIN_URL = "https://itviec.com/sign_in"
STATE_PATH = Path("storage_state/itviec_state.json")
PROFILE_DIR = Path("browser_profile/itviec_manual_cdp")
SESSION_COOKIE = "_ITViec_session"


def find_chrome_executable() -> Path:
    """Find branded Google Chrome."""
    candidates = [
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Khong tim thay Google Chrome. Hay cai Chrome roi chay lai; "
        "khong dung Chromium bundled cho Google OAuth."
    )


def is_itviec_page(url: str) -> bool:
    hostname = (urlsplit(url).hostname or "").lower()
    return hostname == "itviec.com" or hostname.endswith(".itviec.com")


def find_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_manual_chrome_command(chrome_path: Path, debug_port: int) -> list[str]:
    return [
        str(chrome_path),
        f"--user-data-dir={PROFILE_DIR.resolve()}",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={debug_port}",
        "--new-window",
        LOGIN_URL,
    ]


async def current_itviec_page(context: BrowserContext) -> Page | None:
    for page in reversed(context.pages):
        if is_itviec_page(page.url):
            return page
    return None


async def login_is_complete(context: BrowserContext) -> tuple[bool, str]:
    page = await current_itviec_page(context)
    if page is None:
        return False, "Browser chua quay lai domain itviec.com sau Google OAuth."

    path = urlsplit(page.url).path.rstrip("/")
    if (
        path == "/sign_in"
        or await page.locator('input[type="password"]:visible').count()
    ):
        return False, "ITviec van dang hien thi trang/form Sign In."

    cookies = await context.cookies("https://itviec.com")
    if not any(cookie["name"] == SESSION_COOKIE for cookie in cookies):  # type: ignore
        return False, f"Khong tim thay cookie {SESSION_COOKIE} cua ITviec."
    return True, page.url


async def connect_to_manual_chrome(playwright, debug_port: int):
    endpoint = f"http://127.0.0.1:{debug_port}"
    last_error: Error | None = None
    for _ in range(20):
        try:
            return await playwright.chromium.connect_over_cdp(endpoint)
        except Error as exc:
            last_error = exc
            await asyncio.sleep(0.5)
    raise RuntimeError(
        "Khong attach duoc vao Chrome login. Hay dong Chrome ITviec, "
        "chay lai script va khong dong browser truoc khi nhan Enter."
    ) from last_error


async def login_and_save() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    chrome_path = find_chrome_executable()
    debug_port = find_free_local_port()

    print("\n=== ITVIEC LOGIN ===")
    print(f"Dang mo Google Chrome binh thuong tai: {LOGIN_URL}")
    print("Hay bam 'Sign In with Google' va dang nhap thu cong.")
    print("Sau khi ITviec bao dang nhap thanh cong, GIU NGUYEN cua so Chrome.")
    print("Script khong doc email, password, OTP hoac captcha cua ban.")
    await asyncio.create_subprocess_exec(
        *build_manual_chrome_command(chrome_path, debug_port),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await asyncio.to_thread(
        input,
        "Sau khi dang nhap thanh cong, GIU Chrome mo va nhan Enter de luu session...",
    )

    async with async_playwright() as playwright:
        browser = await connect_to_manual_chrome(playwright, debug_port)

        try:
            if not browser.contexts:
                raise RuntimeError("Chrome khong co browser context de luu session.")
            context = browser.contexts[0]
            complete, detail = await login_is_complete(context)
            if not complete:
                raise RuntimeError(
                    f"Google/ITviec login chua hoan tat: {detail} "
                    "Session cu khong bi ghi de; hay chay script va thu lai."
                )

            await context.storage_state(path=str(STATE_PATH))
            print(f"[OK] ITviec authenticated page: {detail}")
            print(f"[OK] Da luu session vao {STATE_PATH}")
            print("Kiem tra tiep bang:")
            print("  uv run python crawl_itviec.py --check-session-only")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(login_and_save())
