from playwright.async_api import Locator, Page


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    async def safe_text(self, selector: str) -> str | None:
        """Lấy nội dung text từ selector một cách an toàn."""
        loc = self.page.locator(selector)
        if await loc.count():
            text = await loc.first.inner_text()
            return text.strip()
        return None

    async def safe_text_all(self, selector: str) -> list[str]:
        elements = await self.page.locator(selector).all()
        return [await el.inner_text() for el in elements]

    async def safe_attr(self, selector: str, attr: str) -> str | None:
        loc = self.page.locator(selector)
        if await loc.count():
            return await loc.first.get_attribute(attr)
        return None

    async def safe_attr_all(self, selector: str, attr: str) -> list[str]:
        elements = await self.page.locator(selector).all()
        values = [await el.get_attribute(attr) for el in elements]
        return [v for v in values if v]

    async def locator_text(self, locator: Locator) -> str | None:
        if await locator.count():
            return (await locator.first.inner_text()).strip() or None
        return None

    async def value_beside_label(self, label: str) -> str | None:
        label_loc = self.page.get_by_text(label, exact=True)
        if not await label_loc.count():
            return None
        value = label_loc.first.locator("xpath=parent::*/*[last()]")
        return await self.locator_text(value)
