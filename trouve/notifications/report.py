import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from trouve.models.deal import DealEvaluation

logger = logging.getLogger(__name__)


def save_deal_report(
    evaluations: list[DealEvaluation],
    output_dir: Path,
    query: str = "",
    location: str = "",
) -> Path:
    """Save deal evaluations to a timestamped JSON file."""
    deals_dir = output_dir.parent / "deals"
    deals_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    safe_query = query.replace(" ", "-").lower() or "all"
    safe_location = location.replace(" ", "-").lower() or "unknown"

    filename = f"{safe_location}_{safe_query}_deals_{timestamp}.json"
    filepath = deals_dir / filename

    deals_above_threshold = [e for e in evaluations if e.deal_score is not None and e.deal_score >= 0]

    data = {
        "metadata": {
            "query": query,
            "location": location,
            "evaluated_at": timestamp,
            "total_evaluated": len(evaluations),
            "deals_found": len(deals_above_threshold),
        },
        "evaluations": [e.model_dump(mode="json") for e in evaluations],
    }

    filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("Deal report saved to %s", filepath)
    return filepath
