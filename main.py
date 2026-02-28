import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from trouve.config.settings import Settings
from trouve.scrapers.marketplace import MarketplaceScraper
from trouve.utils.browser import BrowserManager
from trouve.utils.storage import save_listings


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="trouve",
        description="Scrape Facebook Marketplace listings and find deals",
    )
    parser.add_argument("-q", "--query", type=str, help="Search term (e.g. 'guitar')")
    parser.add_argument("-l", "--location", type=str, help="City/area (e.g. 'seattle')")
    parser.add_argument("--min-price", type=int, help="Minimum price filter")
    parser.add_argument("--max-price", type=int, help="Maximum price filter")
    parser.add_argument("-n", "--max-listings", type=int, help="Max listings to scrape (default: random 90-115)")
    parser.add_argument("--unlimited", action="store_true", help="Scrape with no listing limit (scroll until exhausted)")
    parser.add_argument("--days-listed", type=int, help="Filter by days since listed")
    parser.add_argument("--sort-by", type=str, help="Sort order (e.g. 'creation_time_descend')")
    parser.add_argument("-o", "--output-dir", type=str, help="Output directory")
    parser.add_argument("--headless", action="store_true", default=None, help="Run browser in headless mode")


    parser.add_argument("--find-deals", action="store_true", help="Run deal evaluation on scraped listings")
    parser.add_argument("--evaluate", type=str, metavar="FILE", help="Evaluate deals from a previously scraped JSON file")
    parser.add_argument("--threshold", type=float, help="Minimum deal score to show (0.0-1.0, default 0.30)")
    parser.add_argument("--notify-telegram", action="store_true", help="Send deal alerts to Telegram")
    return parser.parse_args()


def apply_overrides(settings: Settings, args: argparse.Namespace) -> None:
    """Apply CLI argument overrides to settings."""
    # Search params
    if args.query is not None:
        settings.search.query = args.query
    if args.location is not None:
        settings.search.location = args.location
    if args.min_price is not None:
        settings.search.min_price = args.min_price
    if args.max_price is not None:
        settings.search.max_price = args.max_price
    if args.days_listed is not None:
        settings.search.days_listed = args.days_listed
    if args.sort_by is not None:
        settings.search.sort_by = args.sort_by

    # Top-level settings
    if args.unlimited:
        settings.max_listings = 0
    elif args.max_listings is not None:
        settings.max_listings = args.max_listings
    if args.output_dir is not None:
        settings.output_dir = Path(args.output_dir)
    if args.headless:
        settings.browser_headless = True
    if args.threshold is not None:
        settings.deal_score_threshold = args.threshold


async def scrape(settings: Settings) -> list:
    """Run the scraper and save results."""
    from trouve.models.listing import Listing

    logger = logging.getLogger(__name__)
    logger.info("Search URL: %s", settings.search.build_url())
    if settings.max_listings == 0:
        logger.info("Max listings: unlimited")
    else:
        logger.info("Max listings: %d", settings.max_listings)

    async with BrowserManager(settings) as browser:
        scraper = MarketplaceScraper(browser, settings)
        listings = await scraper.scrape()

    if listings:
        filepath = save_listings(
            listings=listings,
            output_dir=settings.output_dir,
            query=settings.search.query,
            location=settings.search.location,
        )
        logger.info("Results saved to: %s", filepath)
    else:
        logger.warning("No listings scraped")

    return listings


async def evaluate_deals(
    settings: Settings, listings: list, notify_telegram: bool = False
) -> None:
    """Run deal evaluation on listings."""
    from trouve.agents.evaluator import DealEvaluator
    from trouve.notifications.console import print_deals
    from trouve.notifications.report import save_deal_report

    logger = logging.getLogger(__name__)

    if not listings:
        logger.warning("No listings to evaluate")
        return

    evaluator = DealEvaluator(
        identifier_model=settings.identifier_model,
        evaluator_model=settings.evaluator_model,
        reverb_token=settings.reverb_api_token,
        deal_threshold=settings.deal_score_threshold,
        max_concurrency=settings.max_eval_concurrency,
        anthropic_api_key=settings.anthropic_api_key,
    )

    evaluations = await evaluator.evaluate_listings(listings)

    # Print to terminal
    print_deals(evaluations, threshold=settings.deal_score_threshold)

    # Save report
    save_deal_report(
        evaluations,
        output_dir=settings.output_dir,
        query=settings.search.query,
        location=settings.search.location,
    )

    # Telegram notifications
    if notify_telegram and settings.telegram_bot_token and settings.telegram_chat_id:
        from trouve.notifications.telegram import send_deals

        await send_deals(
            evaluations,
            threshold=settings.deal_score_threshold,
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
        )
    elif notify_telegram:
        logger.warning(
            "Telegram notification requested but TELEGRAM_BOT_TOKEN and/or "
            "TELEGRAM_CHAT_ID not set in .env"
        )


async def run(args: argparse.Namespace) -> None:
    settings = Settings()
    apply_overrides(settings, args)

    logger = logging.getLogger(__name__)

    if args.evaluate:
        # Evaluate a previously scraped file
        from trouve.models.listing import Listing

        filepath = Path(args.evaluate)
        if not filepath.exists():
            logger.error("File not found: %s", filepath)
            sys.exit(1)

        logger.info("Loading listings from: %s", filepath)
        data = json.loads(filepath.read_text())
        listings = [Listing(**item) for item in data.get("listings", [])]
        logger.info("Loaded %d listings", len(listings))

        await evaluate_deals(settings, listings, notify_telegram=args.notify_telegram)
    else:
        # Scrape (and optionally evaluate)
        listings = await scrape(settings)

        if args.find_deals and listings:
            await evaluate_deals(settings, listings, notify_telegram=args.notify_telegram)


def main() -> None:
    setup_logging()
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
