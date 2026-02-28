import logging
import statistics
from typing import Optional

import httpx

from trouve.models.deal import ComparableSale

logger = logging.getLogger(__name__)

REVERB_API_BASE = "https://api.reverb.com/api"


class ReverbClient:
    """Async client for the Reverb API to look up guitar prices."""

    def __init__(self, api_token: str = "") -> None:
        self._token = api_token
        self._headers = {
            "Accept": "application/hal+json",
            "Accept-Version": "3.0",
            "Content-Type": "application/hal+json",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    @property
    def is_configured(self) -> bool:
        return bool(self._token)

    async def search_prices(
        self, query: str, max_results: int = 15
    ) -> tuple[Optional[float], list[ComparableSale]]:
        """Search Reverb for listings matching a query.

        Returns (median_price, list_of_comparable_sales).
        Returns (None, []) if no results or API is not configured.
        """
        if not self._token:
            logger.debug("Reverb API token not configured, skipping")
            return None, []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{REVERB_API_BASE}/listings/all",
                    headers=self._headers,
                    params={
                        "query": query,
                        "per_page": str(max_results),
                        "sort": "price|asc",
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.warning("Reverb API error %d: %s", e.response.status_code, e)
            return None, []
        except Exception as e:
            logger.warning("Reverb API request failed: %s", e)
            return None, []

        return self._parse_listings(data)

    @staticmethod
    def _parse_listings(
        data: dict,
    ) -> tuple[Optional[float], list[ComparableSale]]:
        """Parse Reverb API response into comparable sales."""
        listings = data.get("listings", [])
        if not listings:
            return None, []

        sales: list[ComparableSale] = []
        prices: list[float] = []

        for item in listings:
            price_data = item.get("price", {})
            amount_str = price_data.get("amount", "")
            try:
                price = float(amount_str)
            except (ValueError, TypeError):
                continue

            title = item.get("title", "")
            url = item.get("_links", {}).get("web", {}).get("href", "")

            sales.append(
                ComparableSale(
                    title=title,
                    price=price,
                    url=url,
                    source="reverb",
                )
            )
            prices.append(price)

        if not prices:
            return None, sales

        median_price = statistics.median(prices)
        logger.debug(
            "Reverb: %d results for query, median $%.0f", len(prices), median_price
        )
        return median_price, sales
