import json
import logging
from typing import Optional

import anthropic

from trouve.models.deal import GuitarIdentity
from trouve.models.listing import Listing

logger = logging.getLogger(__name__)

BATCH_SIZE = 10

SYSTEM_PROMPT = """You are a guitar identification expert. Given Facebook Marketplace listings, extract structured guitar information from the title and description.

For each listing, return a JSON object with:
- brand: Manufacturer name (e.g., "Fender", "Martin", "Gibson"). Empty string if unknown.
- model: Specific model (e.g., "D-28", "Stratocaster", "Les Paul Standard"). Empty string if unknown.
- year: Manufacturing year as integer if mentioned, null if unknown.
- guitar_type: One of "acoustic", "electric", "bass", "classical", "unknown".
- condition: Condition description if mentioned, null if unknown.
- confidence: "high" if brand AND model are clearly identified, "medium" if brand is clear but model is vague, "low" if neither is identifiable.
- search_query: The best search string to find comparable sales on Reverb (e.g., "Martin D-28 1979"). Empty string if confidence is low.

Handle abbreviations (LP = Les Paul, Strat = Stratocaster, Tele = Telecaster, etc.), misspellings, and informal descriptions.

If the listing is not a guitar or is too vague to identify, set confidence to "low".

Return a JSON array of objects, one per listing, in the same order as the input."""


class GuitarIdentifier:
    """Uses Claude to identify guitars from marketplace listing titles."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001", api_key: str = "") -> None:
        kwargs = {"api_key": api_key} if api_key else {}
        self._client = anthropic.Anthropic(**kwargs)
        self._model = model

    async def identify_listings(
        self, listings: list[Listing]
    ) -> dict[str, GuitarIdentity]:
        """Identify guitars for a list of listings. Returns {listing_id: GuitarIdentity}."""
        results: dict[str, GuitarIdentity] = {}

        total_batches = (len(listings) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info("Identifying guitars in %d listings (%d batches)...", len(listings), total_batches)

        for i in range(0, len(listings), BATCH_SIZE):
            batch = listings[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            titles = [l.title for l in batch]
            logger.info("Batch %d/%d — sending to Claude: %s", batch_num, total_batches, titles)
            batch_results = self._identify_batch(batch)
            results.update(batch_results)

            for listing in batch:
                g = batch_results.get(listing.id, GuitarIdentity())
                if g.confidence in ("high", "medium"):
                    logger.info(
                        "  [%s] %s -> %s %s%s (%s)",
                        g.confidence.upper(),
                        listing.title,
                        g.brand,
                        g.model,
                        f" ({g.year})" if g.year else "",
                        g.search_query,
                    )
                else:
                    logger.info("  [LOW] %s -> skipped (too vague)", listing.title)

        high = sum(1 for g in results.values() if g.confidence == "high")
        med = sum(1 for g in results.values() if g.confidence == "medium")
        low = sum(1 for g in results.values() if g.confidence == "low")
        logger.info("Identification results: %d high, %d medium, %d low confidence", high, med, low)

        return results

    def _identify_batch(self, batch: list[Listing]) -> dict[str, GuitarIdentity]:
        """Send a batch of listings to Claude for identification."""
        listings_text = []
        for idx, listing in enumerate(batch):
            parts = [f"Listing {idx + 1}:"]
            parts.append(f"  Title: {listing.title}")
            if listing.description:
                parts.append(f"  Description: {listing.description}")
            if listing.price.formatted:
                parts.append(f"  Price: {listing.price.formatted}")
            if listing.condition:
                parts.append(f"  Condition: {listing.condition}")
            listings_text.append("\n".join(parts))

        user_msg = "\n\n".join(listings_text)
        user_msg += "\n\nReturn a JSON array with one object per listing."

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            return {listing.id: GuitarIdentity() for listing in batch}

        return self._parse_response(response, batch)

    def _parse_response(
        self, response: anthropic.types.Message, batch: list[Listing]
    ) -> dict[str, GuitarIdentity]:
        """Parse Claude's response into GuitarIdentity objects."""
        text = response.content[0].text if response.content else ""

        identities = self._extract_json_array(text)
        if identities is None:
            logger.warning("Failed to parse identifier response as JSON")
            return {listing.id: GuitarIdentity() for listing in batch}

        results: dict[str, GuitarIdentity] = {}
        for idx, listing in enumerate(batch):
            if idx < len(identities):
                try:
                    results[listing.id] = GuitarIdentity(**identities[idx])
                except Exception as e:
                    logger.debug("Failed to parse identity for %s: %s", listing.id, e)
                    results[listing.id] = GuitarIdentity()
            else:
                results[listing.id] = GuitarIdentity()

        return results

    @staticmethod
    def _extract_json_array(text: str) -> Optional[list[dict]]:
        """Extract a JSON array from Claude's response text."""
        # Try parsing the whole text
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        for marker in ("```json", "```"):
            if marker in text:
                start = text.index(marker) + len(marker)
                end = text.index("```", start)
                try:
                    parsed = json.loads(text[start:end].strip())
                    if isinstance(parsed, list):
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    pass

        return None
