from __future__ import annotations

import json
import re

from playwright.async_api import Error as PlaywrightError

from src.pages.base_page import BasePage
from src.scrapers.errors import SalarySessionError


class ITviecJobDetailPage(BasePage):
    NAVIGATION_ATTEMPTS = 5

    async def goto(self, url: str) -> None:
        for attempt in range(1, self.NAVIGATION_ATTEMPTS + 1):
            response = None
            try:
                response = await self.page.goto(
                    url, wait_until="domcontentloaded", timeout=30_000
                )
                await self.page.locator("h1").first.wait_for(timeout=15_000)
                await self.page.locator(
                    ".job-header-info .employer-name"
                ).first.wait_for(timeout=15_000)
            except PlaywrightError:
                pass

            has_title = await self.page.locator("h1").count() > 0
            has_company = (
                await self.page.locator(".job-header-info .employer-name").count() > 0
            )
            if has_title and has_company:
                return

            status = response.status if response else "no-response"
            if attempt < self.NAVIGATION_ATTEMPTS:
                delay_ms = attempt * 2_000
                print(
                    f"\n[itviec] Detail chua san sang "
                    f"(lan {attempt}/{self.NAVIGATION_ATTEMPTS}, status={status}, "
                    f"url={self.page.url}); thu lai sau {delay_ms // 1000}s."
                )
                await self.page.wait_for_timeout(delay_ms)

        raise TimeoutError(
            f"ITviec detail thieu job_title/company_name sau "
            f"{self.NAVIGATION_ATTEMPTS} lan thu: {url}."
        )

    async def _tracking_data(self) -> dict:
        locator = self.page.locator("[data-jobs--save-data-layer-value]").first
        if not await locator.count():
            return {}
        raw = await locator.get_attribute("data-jobs--save-data-layer-value")
        try:
            return json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}

    async def _job_json_ld(self) -> dict:
        scripts = await self.page.locator(
            "script[type='application/ld+json']"
        ).all_text_contents()
        for raw in scripts:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "JobPosting":
                return payload
        return {}

    async def _section_text(self, heading: str) -> str | None:
        title = self.page.get_by_role("heading", name=heading, exact=True)
        if not await title.count():
            return None
        return await self.locator_text(title.first.locator("xpath=parent::*"))

    async def get_title(self) -> str | None:
        return await self.safe_text("h1")

    async def get_company_name(self) -> str | None:
        return await self.safe_text(".job-header-info .employer-name")

    async def get_salary_text(self) -> str | None:
        value = await self.safe_text(".job-header-info .salary")
        if value and re.search(r"log in|login|sign in", value, re.I):  # noqa: FURB167
            raise SalarySessionError(
                "ITviec van hien 'Sign in to view salary'; itviec_state.json khong con hop le."
            )
        return value

    async def get_location_raw(self) -> str | None:
        return (await self._tracking_data()).get("job_by_city")

    async def get_experience_raw(self) -> str | None:
        return await self._section_text("Your skills and experience")

    async def get_required_skills(self) -> list[str]:
        label = self.page.get_by_text("Skills:", exact=True)
        if not await label.count():
            return []
        return await label.first.locator("xpath=parent::*//a").all_inner_texts()

    async def get_company_size_raw(self) -> str | None:
        return await self.value_beside_label("Company size")

    async def get_industry(self) -> str | None:
        return await self.value_beside_label("Company industry")

    async def get_country(self) -> str | None:
        return await self.value_beside_label("Country")

    async def get_posted_date(self) -> str | None:
        value = (await self._job_json_ld()).get("datePosted")
        return value if isinstance(value, str) else None

    async def get_time_info_raw(self) -> str | None:
        info = await self.safe_text(".job-show-info")
        lines = [line.strip() for line in (info or "").splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if line.lower() == "posted" and index + 1 < len(lines):
                return f"Posted {lines[index + 1]}"
            if re.match(r"^Posted\b", line, re.I):  # noqa: FURB167
                return line
            if re.fullmatch(r"\d+\s+days?\s+left", line, re.I):  # noqa: FURB167
                return line
        return await self.get_posted_date()

    async def get_description_raw(self) -> str | None:
        return await self._section_text("Job description")

    async def get_job_type(self) -> str | None:
        info = await self.safe_text(".job-show-info")
        if not info:
            return None
        for line in info.splitlines():
            value = line.strip()
            if re.fullmatch(r"At office|Remote|Hybrid", value, re.I):  # noqa: FURB167
                return value
        return None
