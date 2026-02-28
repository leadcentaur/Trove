import logging

import httpx

from trouve.models.deal import DealEvaluation

logger = logging.getLogger(__name__)

_RECOMMENDATION_EMOJI = {
    "steal": "\U0001f525 STEAL",
    "great_deal": "\U0001f4b0 GREAT DEAL",
    "good_deal": "\U0001f44d GOOD DEAL",
}


def _format_deal(deal: DealEvaluation) -> str:
    """Format a single deal evaluation as a Telegram message."""
    label = _RECOMMENDATION_EMOJI.get(deal.recommendation, deal.recommendation.upper())
    score_pct = f"{deal.deal_score:.0%}" if deal.deal_score is not None else "N/A"

    guitar = deal.guitar
    ident_parts = [guitar.brand, guitar.model]
    if guitar.year:
        ident_parts.append(f"({guitar.year})")
    guitar_name = " ".join(p for p in ident_parts if p) or "Unknown Guitar"

    lines = [
        f"{label} — {score_pct} below market",
        "",
        f"{guitar_name}",
        f"Asking: ${deal.asking_price:,.0f} | Market: ~${deal.market_value:,.0f}",
        f"Source: {deal.market_value_source}",
    ]

    if deal.listing_url:
        lines += ["", f"\U0001f517 {deal.listing_url}"]

    return "\n".join(lines)


async def send_deals(
    evaluations: list[DealEvaluation],
    threshold: float,
    bot_token: str,
    chat_id: str,
) -> None:
    """Send deal notifications to Telegram."""
    deals = [
        e for e in evaluations
        if e.deal_score is not None and e.deal_score >= threshold
    ]

    if not deals:
        logger.info("No deals above threshold to send to Telegram")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with httpx.AsyncClient() as client:
        for deal in deals:
            text = _format_deal(deal)
            payload = {
                "chat_id": chat_id,
                "text": text,
            }
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                logger.info("Telegram message sent for listing %s", deal.listing_id)
            except httpx.HTTPError as exc:
                logger.error(
                    "Failed to send Telegram message for listing %s: %s",
                    deal.listing_id,
                    exc,
                )
