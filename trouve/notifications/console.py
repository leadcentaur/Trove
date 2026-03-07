import sys

from trouve.models.deal import DealEvaluation

# ANSI color codes
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

_RECOMMENDATION_STYLE = {
    "steal": (_GREEN + _BOLD, "STEAL"),
    "great_deal": (_GREEN, "GREAT DEAL"),
    "good_deal": (_YELLOW, "GOOD DEAL"),
    "fair": (_RESET, "FAIR"),
    "overpriced": (_RED, "OVERPRICED"),
    "unknown": (_RESET, "UNKNOWN"),
}


def print_deals(evaluations: list[DealEvaluation], threshold: float = 0.0, currency_symbol: str = "$") -> None:
    """Print deal evaluations to the terminal."""
    deals = [
        e for e in evaluations
        if e.deal_score is not None and e.deal_score >= threshold
    ]

    if not deals:
        print(f"\n{_YELLOW}No deals found above {threshold:.0%} threshold.{_RESET}")
        return

    print(f"\n{_BOLD}{'=' * 70}")
    print(f"  DEAL FINDER RESULTS — {len(deals)} deal(s) found")
    print(f"{'=' * 70}{_RESET}\n")

    for i, deal in enumerate(deals, 1):
        style, label = _RECOMMENDATION_STYLE.get(
            deal.recommendation, (_RESET, deal.recommendation.upper())
        )

        score_pct = f"{deal.deal_score:.0%}" if deal.deal_score is not None else "N/A"

        print(f"  {_BOLD}#{i}{_RESET} {style}[{label}]{_RESET} {score_pct} below market")
        print(f"     {_CYAN}{deal.listing_title}{_RESET}")
        print(f"     Asking: {currency_symbol}{deal.asking_price:,.0f}", end="")
        if deal.market_value:
            print(f"  |  Market value: ~{currency_symbol}{deal.market_value:,.0f} ({deal.market_value_source})")
        else:
            print()

        guitar = deal.guitar
        ident_parts = [guitar.brand, guitar.model]
        if guitar.year:
            ident_parts.append(f"({guitar.year})")
        print(f"     Guitar: {' '.join(p for p in ident_parts if p)}")

        if deal.reasoning:
            print(f"     {deal.reasoning}")

        print(f"     {deal.listing_url}")
        print()

    # Summary
    steals = sum(1 for d in deals if d.recommendation == "steal")
    greats = sum(1 for d in deals if d.recommendation == "great_deal")
    goods = sum(1 for d in deals if d.recommendation == "good_deal")

    summary_parts = []
    if steals:
        summary_parts.append(f"{_GREEN}{_BOLD}{steals} steal(s){_RESET}")
    if greats:
        summary_parts.append(f"{_GREEN}{greats} great deal(s){_RESET}")
    if goods:
        summary_parts.append(f"{_YELLOW}{goods} good deal(s){_RESET}")

    if summary_parts:
        print(f"  Summary: {', '.join(summary_parts)}")
        print()
