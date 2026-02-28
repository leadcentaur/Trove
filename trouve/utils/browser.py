import asyncio
import logging
import random
from types import TracebackType
from typing import Optional, Self

from patchright.async_api import async_playwright, BrowserContext, Page, Playwright

from trouve.config.settings import Settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages a persistent Patchright browser context.

    Usage:
        async with BrowserManager(settings) as manager:
            page = await manager.new_page()
            await page.goto("https://...")
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self) -> Self:
        self._playwright = await async_playwright().start()

        profile_dir = str(self._settings.browser_profile_dir.resolve())
        proxy = self._settings.proxy.to_playwright_proxy()

        launch_kwargs: dict = {
            "user_data_dir": profile_dir,
            "channel": self._settings.chrome_channel,
            "headless": self._settings.browser_headless,
            "no_viewport": True,
            "accept_downloads": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if proxy:
            launch_kwargs["proxy"] = proxy

        self._context = await self._playwright.chromium.launch_persistent_context(
            **launch_kwargs
        )
        logger.info("Browser launched with profile: %s", profile_dir)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self._context:
            await self._context.close()
            logger.info("Browser context closed")
        if self._playwright:
            await self._playwright.stop()

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("BrowserManager not initialized. Use 'async with'.")
        return self._context

    async def new_page(self) -> Page:
        return await self.context.new_page()

    async def random_delay(
        self,
        min_s: Optional[float] = None,
        max_s: Optional[float] = None,
    ) -> None:
        """Sleep for a random duration to mimic human behavior."""
        lo = min_s if min_s is not None else self._settings.min_delay
        hi = max_s if max_s is not None else self._settings.max_delay
        delay = random.uniform(lo, hi)
        logger.debug("Sleeping %.1fs", delay)
        await asyncio.sleep(delay)

    async def dismiss_login_modal(self, page: Page) -> None:
        """Dismiss Facebook login modal if present."""
        try:
            close_btn = page.locator('div[aria-label="Close"]')
            if await close_btn.count() > 0:
                await close_btn.first.click()
                await asyncio.sleep(0.5)
                return
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except Exception:
            pass
