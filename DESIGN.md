# Trouve Deal Finder — Design Doc

## Problem

Facebook Marketplace is full of underpriced items listed by people who don't know what they have. A 1979 Martin D-12-20 listed for $200 is a $2,000+ guitar. The scraper already collects listings — now we need a pipeline that identifies these diamonds in the rough and alerts us before someone else buys them.

## Architecture Overview

```
                          TROUVE PIPELINE

  [FB Marketplace]                              [User]
       |                                           ^
       v                                           |
  +-----------+     +-------------+     +----------+--------+
  |  Scraper  | --> | Identifier  | --> | Evaluator/Scorer  |
  | (exists)  |     | (Claude)    |     | (price research)  |
  +-----------+     +-------------+     +-------------------+
                                                   |
                          +------------------------+
                          |
                    +-----v------+
                    |  Notifier  |
                    +------------+
```

### Stage 1: Scrape (exists)

The scraper produces `list[Listing]` with title, price, location, images, and URL.

### Stage 2: Identify

**Goal:** Turn a vague listing title into a structured guitar identity.

Input: `"Fender acoustic guitar"` or `"Martin D-12-20 1979 — great condition"`
Output:
```json
{
  "brand": "Martin",
  "model": "D-12-20",
  "year": 1979,
  "guitar_type": "acoustic",
  "condition": "great",
  "confidence": "high",
  "search_query": "Martin D-12-20 1979"
}
```

**Approach:** Use Claude Haiku for cheap, fast extraction. Process listings in batches of ~10. Cache results keyed on normalized title to avoid re-identifying duplicates.

Low-confidence results (e.g., title is just "guitar") get filtered out early — no point researching something we can't identify.

### Stage 3: Evaluate (Price Research)

**Goal:** Determine the fair market value and compare it to the asking price.

For each identified guitar, the evaluator:

1. **Queries Reverb API** — search active + sold listings for the same make/model/year. Reverb is the gold standard for used instrument pricing.
2. **Falls back to Claude with web search context** — if Reverb data is thin, use Claude Sonnet with the listing details and ask it to estimate market value based on its training knowledge of guitar markets.
3. **Computes a deal score:**

```
deal_score = (market_value - asking_price) / market_value
```

| Score | Label | Action |
|-------|-------|--------|
| >= 0.50 | Steal | Notify immediately |
| 0.30–0.49 | Great deal | Notify |
| 0.15–0.29 | Good deal | Log, optional notify |
| 0.00–0.14 | Fair price | Log only |
| < 0.00 | Overpriced | Skip |

**Example:** Martin D-12-20 (1979) listed at $200, market value ~$2,000.
Score = (2000 - 200) / 2000 = **0.90 (Steal)**

### Stage 4: Notify

Deals scoring above the threshold get surfaced. Start simple:

- **Terminal output** — color-coded deal summary printed during the run
- **JSON report** — saved alongside raw scrape data in `data/deals/`
- **Future:** Desktop notifications, email, SMS, Discord webhook

## Data Models

### New: `GuitarIdentity`
```python
class GuitarIdentity(BaseModel):
    brand: str
    model: str
    year: int | None
    guitar_type: str          # acoustic, electric, bass, classical, unknown
    condition: str | None
    confidence: str           # high, medium, low
    search_query: str         # best query for price lookup
```

### New: `DealEvaluation`
```python
class DealEvaluation(BaseModel):
    listing_id: str
    listing_title: str
    listing_url: str
    asking_price: float
    market_value: float | None
    market_value_source: str  # "reverb_api", "claude_estimate", "ebay_sold"
    deal_score: float | None
    recommendation: str       # "steal", "great_deal", "good_deal", "fair", "overpriced", "unknown"
    reasoning: str
    comparable_listings: list[dict]  # [{title, price, url, source}]
    guitar: GuitarIdentity
```

## New File Structure

```
trouve/
  agents/
    __init__.py
    identifier.py       # Claude-based guitar identification
    evaluator.py        # Price research + deal scoring
  services/
    __init__.py
    reverb.py           # Reverb API client
  models/
    listing.py          # (existing, unchanged)
    deal.py             # GuitarIdentity, DealEvaluation
  notifications/
    __init__.py
    console.py          # Terminal deal alerts
    report.py           # JSON deal reports
```

## New Dependencies

```toml
dependencies = [
    # ... existing ...
    "anthropic>=0.52",    # Claude API
    "httpx>=0.27",        # Async HTTP for Reverb API
]
```

## Configuration (new .env vars)

```
# API Keys
ANTHROPIC_API_KEY=sk-ant-...
REVERB_API_TOKEN=...

# Deal finder
DEAL_SCORE_THRESHOLD=0.30       # minimum score to notify
IDENTIFIER_MODEL=claude-haiku-4-5-20251001
EVALUATOR_MODEL=claude-sonnet-4-5-20250929
MAX_EVAL_CONCURRENCY=5          # parallel evaluations
```

## CLI Integration

```bash
# Scrape + evaluate in one shot
trouve -q 'guitar' -l seattle --find-deals

# Evaluate a previously scraped file
trouve --evaluate data/raw/seattle_guitar_2026-02-27.json

# Adjust deal threshold
trouve -q 'guitar' --find-deals --threshold 0.40
```

## Pipeline Flow (detailed)

```
1. Scrape 50 guitar listings from FB Marketplace
   |
2. Batch listings into groups of 10
   |
3. Send each batch to Claude Haiku:
   "Extract guitar identity from these 10 listings"
   -> Returns 10 GuitarIdentity objects
   -> Filter out confidence="low" (e.g., "stuff for sale")
   |
4. Deduplicate by (brand, model, year) — cache Reverb lookups
   |
5. For each unique guitar identity:
   a. Query Reverb API: GET /api/listings/all?query={search_query}
   b. Collect prices from active listings
   c. If enough data (3+ comps): compute median as market_value
   d. If insufficient data: ask Claude Sonnet to estimate
   |
6. For each listing, compute deal_score
   |
7. Sort by deal_score descending
   |
8. Output:
   - Print top deals to terminal
   - Save full evaluation to data/deals/{timestamp}.json
```

## Cost Estimates (per run of 100 listings)

| Component | Model | Est. Cost |
|-----------|-------|-----------|
| Identification (100 listings in 10 batches) | Haiku | ~$0.05 |
| Evaluation (30 medium/high confidence) | Sonnet | ~$0.30 |
| Reverb API | Free tier | $0.00 |
| **Total per run** | | **~$0.35** |

## What This Does NOT Do (intentionally)

- **No continuous monitoring / polling loop** — run it when you want, cron it if you want. Keeping it simple.
- **No database** — JSON files are fine for this scale. Add SQLite later if needed.
- **No image analysis** — listing titles and descriptions are enough for identification. Could add vision later for condition assessment.
- **No auto-purchasing** — surface the deals, human decides.

## Implementation Order

1. `models/deal.py` — data models
2. `agents/identifier.py` — Claude identification pipeline
3. `services/reverb.py` — Reverb API client
4. `agents/evaluator.py` — deal scoring logic
5. `notifications/console.py` — terminal output
6. Wire into `main.py` with `--find-deals` flag
7. Tests
