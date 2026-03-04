import asyncio
import json
import logging
from typing import Optional

import anthropic

from trouve.agents.identifier import GuitarIdentifier
from trouve.models.deal import ComparableSale, DealEvaluation, GuitarIdentity
from trouve.models.listing import Listing
from trouve.services.reverb import ReverbClient

logger = logging.getLogger(__name__)

ESTIMATE_SYSTEM_PROMPT = """You are a guitar market valuation expert. Given a guitar's brand, model, year, and condition, estimate its fair market value for a used sale.

Consider:
- Actual sold prices on Reverb, eBay, and other marketplaces
- How year/vintage affects value
- Condition impact on pricing
- Regional price variations
- Facebook Marketplace typically runs 10-30% below Reverb (no fees, local pickup)

Return a JSON object with:
- market_value: Your best estimate in USD (number, not string)
- confidence: "high", "medium", or "low"
- reasoning: Brief explanation of how you arrived at the estimate
- comparable_examples: Array of {title, price} objects representing what similar guitars typically sell for"""


class DealEvaluator:
    """Orchestrates guitar identification, price research, and deal scoring."""

    def __init__(
        self,
        identifier_model: str = "claude-haiku-4-5-20251001",
        evaluator_model: str = "claude-sonnet-4-5-20250929",
        reverb_token: str = "",
        deal_threshold: float = 0.30,
        max_concurrency: int = 5,
        anthropic_api_key: str = "",
    ) -> None:
        self._identifier = GuitarIdentifier(model=identifier_model, api_key=anthropic_api_key)
        self._reverb = ReverbClient(api_token=reverb_token)
        kwargs = {"api_key": anthropic_api_key} if anthropic_api_key else {}
        self._client = anthropic.Anthropic(**kwargs)
        self._evaluator_model = evaluator_model
        self._deal_threshold = deal_threshold
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def evaluate_listings(
        self, listings: list[Listing]
    ) -> list[DealEvaluation]:
        """Run the full evaluation pipeline on a list of listings."""
        logger.info("Starting evaluation of %d listings", len(listings))

        # Stage 1: Identify guitars
        identities = await self._identifier.identify_listings(listings)

        # Filter to high confidence only (brand AND model identified)
        evaluable = [
            (listing, identities[listing.id])
            for listing in listings
            if listing.id in identities
            and identities[listing.id].confidence == "high"
            and identities[listing.id].model  # must have a specific model
        ]
        logger.info(
            "%d/%d listings identified with known model",
            len(evaluable),
            len(listings),
        )

        if not evaluable:
            logger.info("No listings to evaluate — all were too vague to identify")
            return []

        # Stage 2: Evaluate each listing
        logger.info("--- Price Research ---")
        tasks = [
            self._evaluate_single(listing, guitar)
            for listing, guitar in evaluable
        ]
        evaluations = await asyncio.gather(*tasks)

        # Sort by deal score (best deals first), unknowns at end
        evaluations.sort(
            key=lambda e: e.deal_score if e.deal_score is not None else -1,
            reverse=True,
        )

        deals = [e for e in evaluations if e.deal_score is not None and e.deal_score >= self._deal_threshold]
        logger.info(
            "Found %d deals above threshold (%.0f%%)",
            len(deals),
            self._deal_threshold * 100,
        )

        return evaluations

    async def _evaluate_single(
        self, listing: Listing, guitar: GuitarIdentity
    ) -> DealEvaluation:
        """Evaluate a single listing: look up price, compute score."""
        async with self._semaphore:
            asking_price = self._parse_price(listing.price.amount)
            guitar_desc = f"{guitar.brand} {guitar.model}{f' ({guitar.year})' if guitar.year else ''}"

            logger.info(
                "Evaluating: \"%s\" — asking $%.0f (identified as %s)",
                listing.title, asking_price, guitar_desc,
            )

            evaluation = DealEvaluation(
                listing_id=listing.id,
                listing_title=listing.title,
                listing_url=listing.listing_url,
                asking_price=asking_price,
                guitar=guitar,
            )

            # Try Reverb first
            if self._reverb.is_configured:
                logger.info("  Searching Reverb for: \"%s\"", guitar.search_query)
            market_value, comparables = await self._reverb.search_prices(
                guitar.search_query
            )

            if market_value is not None and len(comparables) >= 3:
                evaluation.market_value = market_value
                evaluation.market_value_source = "reverb_api"
                evaluation.comparable_sales = comparables
                logger.info(
                    "  Reverb: found %d comps, median $%.0f",
                    len(comparables), market_value,
                )
            else:
                # Fall back to Claude estimate
                if comparables:
                    logger.info("  Reverb: only %d comps (need 3+), falling back to Claude estimate", len(comparables))
                else:
                    logger.info("  No Reverb data, asking Claude for market estimate...")
                estimate = self._claude_estimate(guitar, comparables)
                if estimate:
                    evaluation.market_value = estimate["market_value"]
                    evaluation.market_value_source = "claude_estimate"
                    evaluation.reasoning = estimate.get("reasoning", "")
                    logger.info(
                        "  Claude estimate: ~$%.0f (%s)",
                        estimate["market_value"],
                        estimate.get("reasoning", "")[:100],
                    )
                    # Merge any Reverb comparables with Claude's examples
                    for ex in estimate.get("comparable_examples", []):
                        try:
                            comp_price = self._parse_price(str(ex.get("price", 0)))
                        except (ValueError, TypeError):
                            comp_price = 0.0
                        evaluation.comparable_sales.append(
                            ComparableSale(
                                title=ex.get("title", ""),
                                price=comp_price,
                                source="claude_estimate",
                            )
                        )
                else:
                    logger.warning("  Could not determine market value for %s", guitar_desc)

            evaluation.compute_score()

            if not evaluation.reasoning and evaluation.deal_score is not None:
                evaluation.reasoning = (
                    f"{guitar_desc}"
                    f" — asking ${asking_price:.0f}, market ~${evaluation.market_value:.0f}"
                )

            if evaluation.deal_score is not None:
                logger.info(
                    "  Result: %s (score %.0f%%) — asking $%.0f vs market $%.0f",
                    evaluation.recommendation.upper().replace("_", " "),
                    evaluation.deal_score * 100,
                    asking_price,
                    evaluation.market_value or 0,
                )
            else:
                logger.info("  Result: UNKNOWN — could not determine value")

            return evaluation

    def _claude_estimate(
        self, guitar: GuitarIdentity, existing_comps: list[ComparableSale]
    ) -> Optional[dict]:
        """Ask Claude to estimate market value when Reverb data is insufficient."""
        parts = [f"Guitar: {guitar.brand} {guitar.model}"]
        if guitar.year:
            parts.append(f"Year: {guitar.year}")
        if guitar.condition:
            parts.append(f"Condition: {guitar.condition}")
        parts.append(f"Type: {guitar.guitar_type}")

        if existing_comps:
            parts.append("\nPartial comparable data found:")
            for comp in existing_comps[:5]:
                parts.append(f"  - {comp.title}: ${comp.price:.0f} ({comp.source})")

        user_msg = "\n".join(parts)

        try:
            response = self._client.messages.create(
                model=self._evaluator_model,
                max_tokens=1024,
                system=ESTIMATE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as e:
            logger.error("Claude estimate failed: %s", e)
            return None

        text = response.content[0].text if response.content else ""
        return self._parse_estimate(text)

    @staticmethod
    def _parse_estimate(text: str) -> Optional[dict]:
        """Parse Claude's market value estimate response."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        for marker in ("```json", "```"):
            if marker in text:
                try:
                    start = text.index(marker) + len(marker)
                    end = text.index("```", start)
                    return json.loads(text[start:end].strip())
                except (json.JSONDecodeError, ValueError):
                    pass

        return None

    @staticmethod
    def _parse_price(amount_str: str) -> float:
        """Parse a price string to float. Handles ranges like '$80-150' by taking the first number."""
        if not amount_str:
            return 0.0
        cleaned = amount_str.replace(",", "").replace("$", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            # Handle ranges like "80-150" — take the first number
            import re
            match = re.search(r"[\d.]+", cleaned)
            if match:
                return float(match.group())
            return 0.0
