from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ListingPrice(BaseModel):
    amount: str = ""
    currency: str = "USD"
    formatted: str = ""


class ListingSeller(BaseModel):
    id: Optional[str] = None
    name: str = ""


class ListingLocation(BaseModel):
    name: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Listing(BaseModel):
    """A single Facebook Marketplace listing."""

    id: str
    title: str = ""
    price: ListingPrice = Field(default_factory=ListingPrice)
    location: ListingLocation = Field(default_factory=ListingLocation)
    seller: ListingSeller = Field(default_factory=ListingSeller)
    image_urls: list[str] = Field(default_factory=list)
    listing_url: str = ""
    description: Optional[str] = None
    condition: Optional[str] = None
    date_posted: Optional[str] = None
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "graphql"

    @model_validator(mode="after")
    def build_listing_url(self) -> Listing:
        if not self.listing_url and self.id:
            self.listing_url = f"https://www.facebook.com/marketplace/item/{self.id}/"
        return self

    @classmethod
    def from_graphql_edge(cls, edge: dict) -> Listing:
        """Parse a listing from a GraphQL feed_units edge node."""
        node = edge.get("node", {})
        listing = node.get("listing", {})

        # Price
        price_data = listing.get("listing_price", {}) or {}
        price = ListingPrice(
            amount=price_data.get("amount", ""),
            currency=price_data.get("currency", "USD"),
            formatted=price_data.get("formatted_amount", ""),
        )

        # Location
        loc_data = listing.get("location", {}) or {}
        reverse_geo = loc_data.get("reverse_geocode", {}) or {}
        city = reverse_geo.get("city", "")
        state = reverse_geo.get("state", "")
        location_name = f"{city}, {state}".strip(", ") if city or state else ""
        location = ListingLocation(
            name=location_name,
            latitude=loc_data.get("latitude"),
            longitude=loc_data.get("longitude"),
        )

        # Seller
        seller_data = listing.get("marketplace_listing_seller", {}) or {}
        seller = ListingSeller(
            id=seller_data.get("id"),
            name=seller_data.get("name", ""),
        )

        # Images
        image_urls = []
        primary_photo = listing.get("primary_listing_photo", {}) or {}
        primary_uri = (primary_photo.get("image", {}) or {}).get("uri")
        if primary_uri:
            image_urls.append(primary_uri)

        # Title — try multiple known field names
        title = (
            listing.get("marketplace_listing_title")
            or listing.get("group_commerce_item_title")
            or ""
        )

        return cls(
            id=listing.get("id", node.get("id", "")),
            title=title,
            price=price,
            location=location,
            seller=seller,
            image_urls=image_urls,
            description=listing.get("redacted_description", {}).get("text")
            if isinstance(listing.get("redacted_description"), dict)
            else None,
            condition=listing.get("condition_text"),
            date_posted=str(listing["creation_time"])
            if "creation_time" in listing
            else None,
            source="graphql",
        )

    @classmethod
    def from_html_element(cls, item_data: dict) -> Listing:
        """Parse a listing from HTML-extracted data (fallback)."""
        price_text = item_data.get("price_text", "")
        return cls(
            id=item_data["id"],
            title=item_data.get("title", ""),
            price=ListingPrice(formatted=price_text),
            location=ListingLocation(name=item_data.get("location_text", "")),
            image_urls=[item_data["image_url"]] if item_data.get("image_url") else [],
            source="html_fallback",
        )
