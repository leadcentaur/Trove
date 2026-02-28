from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GuitarIdentity(BaseModel):
    """Structured guitar identity extracted from a listing."""

    brand: str = ""
    model: str = ""
    year: Optional[int] = None
    guitar_type: str = "unknown"  # acoustic, electric, bass, classical, unknown
    condition: Optional[str] = None
    confidence: str = "low"  # high, medium, low
    search_query: str = ""


class ComparableSale(BaseModel):
    """A comparable listing used to estimate market value."""

    title: str = ""
    price: float = 0.0
    url: str = ""
    source: str = ""  # reverb, ebay, claude_estimate


class DealEvaluation(BaseModel):
    """Full deal evaluation for a single listing."""

    listing_id: str
    listing_title: str = ""
    listing_url: str = ""
    asking_price: float = 0.0
    market_value: Optional[float] = None
    market_value_source: str = ""  # reverb_api, claude_estimate
    deal_score: Optional[float] = None
    recommendation: str = "unknown"  # steal, great_deal, good_deal, fair, overpriced, unknown
    reasoning: str = ""
    comparable_sales: list[ComparableSale] = Field(default_factory=list)
    guitar: GuitarIdentity = Field(default_factory=GuitarIdentity)

    def compute_score(self) -> None:
        """Compute deal_score and recommendation from asking_price and market_value."""
        if self.market_value is None or self.market_value <= 0 or self.asking_price <= 0:
            self.deal_score = None
            self.recommendation = "unknown"
            return

        self.deal_score = (self.market_value - self.asking_price) / self.market_value

        if self.deal_score >= 0.50:
            self.recommendation = "steal"
        elif self.deal_score >= 0.30:
            self.recommendation = "great_deal"
        elif self.deal_score >= 0.15:
            self.recommendation = "good_deal"
        elif self.deal_score >= 0.0:
            self.recommendation = "fair"
        else:
            self.recommendation = "overpriced"
