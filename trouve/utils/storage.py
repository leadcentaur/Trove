import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from trouve.models.listing import Listing

logger = logging.getLogger(__name__)


def save_listings(
    listings: list[Listing],
    output_dir: Path,
    query: str = "",
    location: str = "",
) -> Path:
    """Save listings to a timestamped JSON file.

    Returns the path to the saved file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    safe_query = _sanitize(query) or "all"
    safe_location = _sanitize(location) or "unknown"

    filename = f"{safe_location}_{safe_query}_{timestamp}.json"
    filepath = output_dir / filename

    data = {
        "metadata": {
            "query": query,
            "location": location,
            "scraped_at": timestamp,
            "total_listings": len(listings),
        },
        "listings": [listing.model_dump(mode="json") for listing in listings],
    }

    filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("Saved %d listings to %s", len(listings), filepath)
    return filepath


def _sanitize(s: str) -> str:
    """Replace non-alphanumeric characters with hyphens, lowercase."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip()).strip("-").lower()
    return s
