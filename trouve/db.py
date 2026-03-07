"""SQLite database for deal storage and deduplication."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from trouve.models.deal import DealEvaluation

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    listing_id        TEXT PRIMARY KEY,
    listing_title     TEXT,
    listing_url       TEXT,
    asking_price      REAL,
    market_value      REAL,
    market_value_source TEXT,
    deal_score        REAL,
    recommendation    TEXT,
    reasoning         TEXT,
    guitar_brand      TEXT,
    guitar_model      TEXT,
    guitar_year       INTEGER,
    guitar_type       TEXT,
    notified          INTEGER DEFAULT 0,
    query             TEXT,
    location          TEXT,
    evaluated_at      TEXT
);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create the deals table if it doesn't exist and return a connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(_SCHEMA)
    conn.commit()
    logger.info("Database ready at %s", db_path)
    return conn


def save_evaluations(
    conn: sqlite3.Connection,
    evaluations: list[DealEvaluation],
    query: str,
    location: str,
) -> None:
    """Upsert deal evaluations into the database."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            e.listing_id,
            e.listing_title,
            e.listing_url,
            e.asking_price,
            e.market_value,
            e.market_value_source,
            e.deal_score,
            e.recommendation,
            e.reasoning,
            e.guitar.brand,
            e.guitar.model,
            e.guitar.year,
            e.guitar.guitar_type,
            0,  # notified — preserve existing value via INSERT OR REPLACE
            query,
            location,
            now,
        )
        for e in evaluations
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO deals (
            listing_id, listing_title, listing_url, asking_price,
            market_value, market_value_source, deal_score, recommendation,
            reasoning, guitar_brand, guitar_model, guitar_year, guitar_type,
            notified, query, location, evaluated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            COALESCE((SELECT notified FROM deals WHERE listing_id = ?), ?),
            ?, ?, ?
        )
        """,
        [
            (
                r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                r[8], r[9], r[10], r[11], r[12],
                r[0], r[13],  # listing_id for subquery, default notified value
                r[14], r[15], r[16],
            )
            for r in rows
        ],
    )
    conn.commit()
    logger.info("Saved %d evaluations to database", len(rows))


def get_unsent_deal_ids(conn: sqlite3.Connection, listing_ids: list[str]) -> set[str]:
    """Return the subset of listing_ids that haven't been notified yet."""
    if not listing_ids:
        return set()
    placeholders = ",".join("?" for _ in listing_ids)
    cursor = conn.execute(
        f"SELECT listing_id FROM deals WHERE listing_id IN ({placeholders}) AND notified = 0",
        listing_ids,
    )
    return {row[0] for row in cursor.fetchall()}


def mark_notified(conn: sqlite3.Connection, listing_ids: list[str]) -> None:
    """Set notified=1 for the given listing IDs."""
    if not listing_ids:
        return
    placeholders = ",".join("?" for _ in listing_ids)
    conn.execute(
        f"UPDATE deals SET notified = 1 WHERE listing_id IN ({placeholders})",
        listing_ids,
    )
    conn.commit()
    logger.info("Marked %d deals as notified", len(listing_ids))
