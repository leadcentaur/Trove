# Trouve — Local Setup & Usage

## Prerequisites

- Python 3.11+
- Google Chrome installed
- A Facebook account (you'll log in through the browser on first run)

## Setup

### 1. Clone and install

```bash
cd trouve
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Install browser driver

Trouve uses [Patchright](https://github.com/AuroraWright/patchright) (a patched Playwright) to drive Chrome. Install the Chromium driver:

```bash
python -m patchright install chromium
```

### 3. Configure environment

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | For deal finding | Your Anthropic API key |
| `REVERB_API_TOKEN` | No | Reverb API token for price lookups (falls back to Claude estimates without it) |
| `SEARCH_LOCATION` | No | Default city/area (default: `seattle`) |
| `SEARCH_QUERY` | No | Default search term |
| `BROWSER_HEADLESS` | No | Run headless — set `true` to hide the browser (default: `false`) |

All other settings have sensible defaults. See `.env.example` for the full list.

## First Run — Facebook Login

On the first run, Trouve opens a real Chrome window and navigates to Facebook Marketplace. **You need to log in manually** the first time. Your session is saved to `data/chrome_profile/`, so subsequent runs stay logged in.

```bash
trouve -q 'guitar' -l seattle
```

The browser will open. Log in to Facebook if prompted, then let Trouve scrape.

## Usage

### Basic scraping

```bash
# Scrape guitar listings in Seattle
trouve -q 'guitar' -l seattle

# Scrape with price filters
trouve -q 'fender stratocaster' -l portland --min-price 100 --max-price 500

# Limit number of listings
trouve -q 'guitar' -n 50

# Only show listings from the last 7 days
trouve -q 'martin acoustic' --days-listed 7

# Run headless (no browser window)
trouve -q 'guitar' --headless
```

Results are saved as JSON to `data/raw/` by default.

### Deal finding

Scrape and evaluate deals in one shot:

```bash
trouve -q 'guitar' -l seattle --find-deals
```

This runs the full pipeline:

1. **Scrape** listings from Facebook Marketplace
2. **Identify** guitars using Claude Haiku (brand, model, year)
3. **Research prices** via the Reverb API (falls back to Claude Sonnet estimates)
4. **Score deals** and print results to the terminal

Deal reports are saved to `data/deals/`.

### Evaluate a previous scrape

Skip scraping and evaluate an existing JSON file:

```bash
trouve --evaluate data/raw/seattle_guitar_2026-02-27T01-30-00Z.json
```

### Adjust deal threshold

The default threshold is 0.30 (30% below market). Lower it to see more deals, raise it to only see steals:

```bash
# Only show items 40%+ below market
trouve -q 'guitar' --find-deals --threshold 0.40

# Show everything 15%+ below market
trouve -q 'guitar' --find-deals --threshold 0.15
```

### Deal score guide

| Score | Label | Meaning |
|---|---|---|
| >= 0.50 | Steal | 50%+ below market value |
| 0.30–0.49 | Great deal | Significantly underpriced |
| 0.15–0.29 | Good deal | Moderately underpriced |
| 0.00–0.14 | Fair | Priced at or near market |
| < 0.00 | Overpriced | Above market value |

## CLI Reference

```
trouve [-h] [-q QUERY] [-l LOCATION] [--min-price MIN_PRICE]
       [--max-price MAX_PRICE] [-n MAX_LISTINGS] [--days-listed DAYS]
       [--sort-by SORT_BY] [-o OUTPUT_DIR] [--headless]
       [--find-deals] [--evaluate FILE] [--threshold THRESHOLD]
```

| Flag | Short | Description |
|---|---|---|
| `--query` | `-q` | Search term (e.g. `'guitar'`) |
| `--location` | `-l` | City/area (e.g. `'seattle'`) |
| `--min-price` | | Minimum price filter |
| `--max-price` | | Maximum price filter |
| `--max-listings` | `-n` | Max listings to scrape (default: 100) |
| `--days-listed` | | Filter by days since listed |
| `--sort-by` | | Sort order (default: `creation_time_descend`) |
| `--output-dir` | `-o` | Output directory (default: `data/raw`) |
| `--headless` | | Run browser without a visible window |
| `--find-deals` | | Run deal evaluation after scraping |
| `--evaluate` | | Evaluate deals from a previously scraped JSON file |
| `--threshold` | | Minimum deal score to display (0.0–1.0, default: 0.30) |

## Output

- **Raw scrape data:** `data/raw/{location}_{query}_{timestamp}.json`
- **Deal reports:** `data/deals/{location}_{query}_deals_{timestamp}.json`
- **Browser profile:** `data/chrome_profile/` (persistent login session)

## Running Tests

```bash
pytest
```

## Proxy Support

If you need to route traffic through a proxy, set these in `.env`:

```
PROXY_SERVER=http://proxy.example.com:8080
PROXY_USERNAME=user
PROXY_PASSWORD=pass
```

Leave `PROXY_SERVER` empty to disable.
