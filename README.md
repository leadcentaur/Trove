# Trouve

Trouve scrapes Facebook Marketplace for guitar listings and finds underpriced deals. It uses Claude to identify what a guitar actually is from vague listing titles, looks up real market prices on Reverb, and scores how good the deal is — so you can grab a $2,000 Martin listed for $200 before someone else does.

## How It Works

```
FB Marketplace ──> Scraper ──> Identifier (Claude) ──> Price Research (Reverb) ──> Deal Scorer
                                                                                       |
                                                                              Terminal + JSON report
```

1. **Scrape** — Navigates Facebook Marketplace with a real Chrome session. Intercepts GraphQL responses to capture listing data (title, price, location, images). Falls back to HTML parsing if needed.
2. **Identify** — Sends listing titles to Claude Haiku in batches. Extracts brand, model, year, and type. Filters out anything too vague to research.
3. **Price Research** — Queries the Reverb API for comparable sales. If there aren't enough comps, falls back to a Claude Sonnet estimate.
4. **Score** — Computes `(market_value - asking_price) / market_value`. A Martin D-28 listed at $800 with a market value of $1,600 scores 0.50 (a steal).

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m patchright install chromium
cp .env.example .env   # add your ANTHROPIC_API_KEY
```

```bash
# Scrape listings
trouve -q 'guitar' -l seattle

# Scrape and find deals
trouve -q 'guitar' -l seattle --find-deals

# Evaluate a previous scrape
trouve --evaluate data/raw/seattle_guitar_2026-02-27.json
```

The first run opens a Chrome window — log in to Facebook when prompted. Your session persists across runs.

## Examples

```bash
# Price-filtered search
trouve -q 'fender stratocaster' -l portland --min-price 100 --max-price 500

# Only recent listings, limit to 50
trouve -q 'martin acoustic' --days-listed 7 -n 50

# Headless mode (no browser window)
trouve -q 'guitar' --headless

# Stricter deal threshold (only show 40%+ below market)
trouve -q 'guitar' --find-deals --threshold 0.40
```

## Configuration

All config is via `.env` (see [`.env.example`](.env.example)) or CLI flags. Key variables:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Required for deal finding |
| `REVERB_API_TOKEN` | Reverb API token (optional — falls back to Claude estimates) |
| `SEARCH_LOCATION` | Default city (default: `seattle`) |
| `BROWSER_HEADLESS` | `true` to hide the browser window |

See [USAGE.md](USAGE.md) for the full CLI reference, deal score guide, proxy setup, and detailed documentation.
