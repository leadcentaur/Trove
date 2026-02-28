import asyncio
import json
import logging
import random
from typing import Optional

from patchright.async_api import Page, Response

from trouve.config.settings import Settings
from trouve.models.listing import Listing
from trouve.utils.browser import BrowserManager

logger = logging.getLogger(__name__)

GRAPHQL_ENDPOINT = "https://www.facebook.com/api/graphql/"
MARKETPLACE_ITEM_SELECTOR = 'a[href*="/marketplace/item/"]'
MARKETPLACE_COLLECTION_SELECTOR = 'div[aria-label="Collection of Marketplace items"]'


class MarketplaceScraper:
    """Scrapes Facebook Marketplace listings.

    Primary strategy: Intercept GraphQL responses from /api/graphql/.
    Fallback: Parse rendered HTML using stable aria-label selectors.
    """

    def __init__(self, browser: BrowserManager, settings: Settings) -> None:
        self._browser = browser
        self._settings = settings
        self._listings: dict[str, Listing] = {}
        self._graphql_captured: bool = False

    async def scrape(self) -> list[Listing]:
        """Execute the full scraping flow and return unique listings."""
        page = await self._browser.new_page()

        try:
            page.on("response", self._on_response)

            url = self._settings.search.build_url()

            # Ensure we're logged into Facebook before navigating to marketplace
            await self._browser.ensure_login(page, url)
            await self._wait_for_content(page)
            await self._scroll_for_listings(page)

            if len(self._listings) < 3:
                logger.warning(
                    "GraphQL captured only %d listings, trying HTML fallback",
                    len(self._listings),
                )
                await self._parse_html_fallback(page)

            logger.info("Total unique listings scraped: %d", len(self._listings))
            return list(self._listings.values())

        except Exception as e:
            logger.error("Scraping failed: %s", e, exc_info=True)
            raise
        finally:
            await page.close()

    async def _on_response(self, response: Response) -> None:
        """Intercept GraphQL responses containing marketplace data."""
        if GRAPHQL_ENDPOINT not in response.url:
            return
        if response.status != 200:
            return

        try:
            body = await response.json()
        except Exception:
            try:
                text = await response.text()
                body = json.loads(text.split("\n")[0])
            except Exception:
                return

        edges = self._extract_edges(body)
        if not edges:
            return

        self._graphql_captured = True
        for edge in edges:
            try:
                listing = Listing.from_graphql_edge(edge)
                if listing.id and listing.id not in self._listings:
                    self._listings[listing.id] = listing
                    logger.debug("Captured: %s — %s", listing.id, listing.title)
            except Exception as e:
                logger.debug("Failed to parse edge: %s", e)

        logger.info(
            "GraphQL batch: +%d edges (total: %d)", len(edges), len(self._listings)
        )

    @staticmethod
    def _extract_edges(body: dict) -> list[dict]:
        """Extract listing edges from a GraphQL response, trying known paths."""
        paths = [
            ("data", "marketplace_search", "feed_units", "edges"),
            ("data", "viewer", "marketplace_search", "feed_units", "edges"),
            ("data", "marketplace_search", "feed_units", "edges"),
        ]
        for path in paths:
            node = body
            for key in path:
                if isinstance(node, dict):
                    node = node.get(key)
                else:
                    node = None
                    break
            if isinstance(node, list) and len(node) > 0:
                return node
        return []

    async def _wait_for_content(self, page: Page) -> None:
        """Wait for marketplace content to load on the page."""
        try:
            await page.wait_for_selector(
                f"{MARKETPLACE_COLLECTION_SELECTOR}, {MARKETPLACE_ITEM_SELECTOR}",
                timeout=15000,
            )
            logger.info("Marketplace content detected")
        except Exception:
            logger.warning("Content selector not found, waiting 5s")
            await asyncio.sleep(5)

        await self._browser.random_delay(min_s=2.0, max_s=4.0)

    async def _scroll_for_listings(self, page: Page) -> None:
        """Scroll to trigger lazy-loading of additional listings."""
        max_listings = self._settings.max_listings
        unlimited = max_listings == 0
        no_new_count = 0
        max_stale = 3

        while unlimited or len(self._listings) < max_listings:
            prev_count = len(self._listings)

            scroll_amount = random.randint(600, 1200)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(self._settings.scroll_pause)
            await self._browser.random_delay(min_s=1.0, max_s=3.0)

            if len(self._listings) == prev_count:
                no_new_count += 1
                logger.debug("No new listings after scroll (%d/%d)", no_new_count, max_stale)
                if no_new_count >= max_stale:
                    logger.info("No new listings after %d scrolls, stopping", max_stale)
                    break
            else:
                no_new_count = 0
                logger.info("Listings after scroll: %d", len(self._listings))

    async def _parse_html_fallback(self, page: Page) -> None:
        """Fallback: Parse listings from rendered HTML."""
        logger.info("Running HTML fallback parser")
        items = await page.query_selector_all(MARKETPLACE_ITEM_SELECTOR)
        logger.info("Found %d item links in HTML", len(items))

        for item in items:
            try:
                href = await item.get_attribute("href") or ""
                listing_id = self._extract_id_from_href(href)
                if not listing_id or listing_id in self._listings:
                    continue

                text = await item.inner_text()
                lines = [l.strip() for l in text.strip().split("\n") if l.strip()]

                img = await item.query_selector("img")
                image_url = await img.get_attribute("src") if img else ""

                item_data = {
                    "id": listing_id,
                    "title": lines[0] if lines else "",
                    "price_text": lines[1] if len(lines) > 1 else "",
                    "location_text": lines[2] if len(lines) > 2 else "",
                    "image_url": image_url or "",
                }
                listing = Listing.from_html_element(item_data)
                self._listings[listing.id] = listing

            except Exception as e:
                logger.debug("Failed to parse HTML item: %s", e)

        logger.info("HTML fallback total: %d listings", len(self._listings))

    @staticmethod
    def _extract_id_from_href(href: str) -> Optional[str]:
        """Extract listing ID from /marketplace/item/{id}/."""
        marker = "/marketplace/item/"
        idx = href.find(marker)
        if idx == -1:
            return None
        rest = href[idx + len(marker) :]
        listing_id = rest.split("/")[0].split("?")[0]
        return listing_id if listing_id.isdigit() else None
