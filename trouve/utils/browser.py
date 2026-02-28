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

    async def ensure_login(self, page: Page, target_url: str) -> None:
        """Ensure we're logged into Facebook, then navigate to the target URL.

        Goes to facebook.com first to check the session. If not logged in,
        auto-logs in with credentials from .env or waits for manual login.
        Then navigates to the target marketplace URL.
        """
        # Go to Facebook home to check session state
        logger.info("Checking Facebook login status...")
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        if await self._is_logged_in(page):
            logger.info("Already logged in")
        else:
            logger.info("Not logged into Facebook")

            if self._settings.fb_email and self._settings.fb_password:
                logger.info("Attempting auto-login...")
                await self._auto_login(page)
            else:
                logger.info("No credentials configured — please log in through the browser window")

            # Wait for login to succeed (manual or post-auto-login)
            if not await self._is_logged_in(page):
                logger.info("Waiting for login to complete...")
                while not await self._is_logged_in(page):
                    await asyncio.sleep(2)

            logger.info("Login successful")

        # Dismiss any modals, then navigate to marketplace
        try:
            close_btn = page.locator('div[aria-label="Close"]')
            if await close_btn.count() > 0:
                await close_btn.first.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

        logger.info("Navigating to: %s", target_url)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

    async def _auto_login(self, page: Page) -> None:
        """Navigate to the Facebook login page, fill credentials, and submit."""
        await page.goto("https://www.facebook.com/login/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        try:
            email_field = page.locator('input[name="email"]')
            pass_field = page.locator('input[name="pass"]')

            await email_field.first.fill(self._settings.fb_email)
            await asyncio.sleep(0.5)
            await pass_field.first.fill(self._settings.fb_password)
            await asyncio.sleep(0.5)

            # Try multiple strategies to submit the login form
            submitted = False

            # Strategy 1: Click a visible login button
            button_selectors = [
                'button[name="login"]',
                'button[id="loginbutton"]',
                'button[data-testid="royal_login_button"]',
                'input[value="Log In"]',
                'input[value="Log in"]',
                'button[type="submit"]',
            ]
            for selector in button_selectors:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    logger.info("Clicking login button: %s", selector)
                    await btn.first.click(timeout=10000)
                    submitted = True
                    break

            # Strategy 2: Press Enter on the password field
            if not submitted:
                logger.info("No login button found — pressing Enter to submit")
                await pass_field.first.press("Enter")

            # Wait for navigation away from login page (up to 30s)
            for _ in range(15):
                await asyncio.sleep(2)
                url = page.url
                if "/login" not in url and "checkpoint" not in url:
                    break

            await asyncio.sleep(2)

        except Exception as e:
            logger.warning("Auto-login error: %s", e)

    @staticmethod
    async def _is_logged_in(page: Page) -> bool:
        """Check if the user is logged into Facebook by looking for logged-in UI elements."""
        url = page.url
        # If we're on the login page, definitely not logged in
        if "/login" in url or "/checkpoint" in url:
            return False

        # Look for elements that only appear when logged in
        selectors = [
            'svg[aria-label="Your profile"]',
            'div[aria-label="Account"]',
            'a[aria-label="Messenger"]',
            'a[aria-label="Notifications"]',
            'input[aria-label="Search Facebook"]',
        ]
        for selector in selectors:
            locator = page.locator(selector)
            if await locator.count() > 0:
                return True

        return False
