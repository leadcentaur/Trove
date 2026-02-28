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

    async def wait_for_login(self, page: Page) -> None:
        """Detect if Facebook requires login, auto-login if credentials are set, or wait for manual login."""
        if not await self._needs_login(page):
            # Try dismissing an overlay modal (logged-in users sometimes see one)
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
            return

        # Try auto-login if credentials are configured
        if self._settings.fb_email and self._settings.fb_password:
            logger.info("Facebook login required — attempting auto-login...")
            await self._auto_login(page)

            if not await self._needs_login(page):
                logger.info("Auto-login successful")
                return

            logger.warning("Auto-login failed — falling back to manual login")

        # Manual login fallback
        logger.info("Facebook login required — please log in through the browser window")
        logger.info("Waiting for you to complete login...")

        while await self._needs_login(page):
            await asyncio.sleep(2)

        logger.info("Login detected — continuing")
        await asyncio.sleep(2)

    async def _auto_login(self, page: Page) -> None:
        """Fill in the Facebook login form and submit."""
        target_url = page.url

        # Navigate to login page if we're not already on one with a form
        email_field = page.locator('input[name="email"]')
        if await email_field.count() == 0:
            await page.goto("https://www.facebook.com/login/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

        try:
            email_field = page.locator('input[name="email"]')
            pass_field = page.locator('input[name="pass"]')
            login_btn = page.locator('button[name="login"], button[id="loginbutton"], input[value="Log in"]')

            await email_field.first.fill(self._settings.fb_email)
            await asyncio.sleep(0.5)
            await pass_field.first.fill(self._settings.fb_password)
            await asyncio.sleep(0.5)
            await login_btn.first.click()

            # Wait for navigation away from login page
            for _ in range(15):
                await asyncio.sleep(2)
                if not await self._needs_login(page):
                    break

            # Navigate back to the original marketplace URL
            await asyncio.sleep(2)
            if "marketplace" not in page.url:
                logger.info("Navigating back to marketplace...")
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(2)

        except Exception as e:
            logger.warning("Auto-login error: %s", e)

    @staticmethod
    async def _needs_login(page: Page) -> bool:
        """Check if the current page is a Facebook login wall."""
        url = page.url
        if "/login" in url or "checkpoint" in url:
            return True

        # Check for login form on the page (modal or full-page)
        login_form = page.locator('form[action*="login"], #login_form, input[name="email"]')
        if await login_form.count() > 0:
            # Make sure it's not just a tiny hidden element — check for marketplace content too
            marketplace = page.locator(
                'a[href*="/marketplace/item/"], '
                'div[aria-label="Collection of Marketplace items"]'
            )
            if await marketplace.count() == 0:
                return True

        return False
