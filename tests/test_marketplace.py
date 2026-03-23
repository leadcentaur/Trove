import json
from pathlib import Path

from trouve.config.settings import SearchParams
from trouve.models.listing import Listing
from trouve.scrapers.marketplace import MarketplaceScraper
from trouve.utils.storage import save_listings

#Update 
class TestSearchParams:
    def test_build_url_basic(self):
        params = SearchParams(location="toronto", query="couch")
        url = params.build_url()
        assert "facebook.com/marketplace/toronto/search" in url
        assert "query=couch" in url

    def test_build_url_with_price_range(self):
        params = SearchParams(location="toronto", query="tv", min_price=50, max_price=200)
        url = params.build_url()
        assert "minPrice=50" in url
        assert "maxPrice=200" in url

    def test_build_url_omits_none_params(self):
        params = SearchParams(location="toronto", query="desk")
        url = params.build_url()
        assert "minPrice" not in url
        assert "daysSinceListed" not in url

    def test_build_url_no_query_browse(self):
        params = SearchParams(location="portland", query="")
        url = params.build_url()
        assert url.endswith("/marketplace/portland/")
        assert "search" not in url


class TestListingModel:
    def test_from_graphql_edge_full(self):
        edge = {
            "node": {
                "listing": {
                    "id": "123456789",
                    "marketplace_listing_title": "Blue Couch",
                    "listing_price": {
                        "amount": "150",
                        "currency": "USD",
                        "formatted_amount": "$150",
                    },
                    "location": {
                        "reverse_geocode": {"city": "toronto", "state": "WA"}
                    },
                    "primary_listing_photo": {
                        "image": {"uri": "https://scontent.xx.fbcdn.net/photo.jpg"}
                    },
                    "marketplace_listing_seller": {
                        "id": "987654321",
                        "name": "John Doe",
                    },
                }
            }
        }
        listing = Listing.from_graphql_edge(edge)
        assert listing.id == "123456789"
        assert listing.title == "Blue Couch"
        assert listing.price.amount == "150"
        assert listing.price.formatted == "$150"
        assert listing.location.name == "toronto, WA"
        assert listing.seller.name == "John Doe"
        assert len(listing.image_urls) == 1
        assert listing.source == "graphql"

    def test_from_graphql_edge_minimal(self):
        edge = {"node": {"listing": {"id": "111"}}}
        listing = Listing.from_graphql_edge(edge)
        assert listing.id == "111"
        assert listing.title == ""
        assert listing.price.amount == ""

    def test_from_graphql_edge_alt_title_field(self):
        edge = {
            "node": {
                "listing": {
                    "id": "222",
                    "group_commerce_item_title": "Vintage Lamp",
                }
            }
        }
        listing = Listing.from_graphql_edge(edge)
        assert listing.title == "Vintage Lamp"

    def test_from_html_element(self):
        data = {
            "id": "555",
            "title": "Nice Table",
            "price_text": "$75",
            "location_text": "Bellevue, WA",
            "image_url": "https://example.com/img.jpg",
        }
        listing = Listing.from_html_element(data)
        assert listing.id == "555"
        assert listing.title == "Nice Table"
        assert listing.price.formatted == "$75"
        assert listing.source == "html_fallback"

    def test_listing_url_auto_generated(self):
        listing = Listing(id="999")
        assert "marketplace/item/999" in listing.listing_url


class TestExtractEdges:
    def test_standard_path(self):
        body = {
            "data": {
                "marketplace_search": {
                    "feed_units": {
                        "edges": [{"node": {"listing": {"id": "1"}}}]
                    }
                }
            }
        }
        edges = MarketplaceScraper._extract_edges(body)
        assert len(edges) == 1

    def test_viewer_path(self):
        body = {
            "data": {
                "viewer": {
                    "marketplace_search": {
                        "feed_units": {
                            "edges": [{"node": {"listing": {"id": "2"}}}]
                        }
                    }
                }
            }
        }
        edges = MarketplaceScraper._extract_edges(body)
        assert len(edges) == 1

    def test_missing_path_returns_empty(self):
        body = {"data": {"other_query": {}}}
        edges = MarketplaceScraper._extract_edges(body)
        assert edges == []

    def test_empty_edges_returns_empty(self):
        body = {
            "data": {
                "marketplace_search": {
                    "feed_units": {"edges": []}
                }
            }
        }
        edges = MarketplaceScraper._extract_edges(body)
        assert edges == []


class TestExtractIdFromHref:
    def test_standard_href(self):
        assert MarketplaceScraper._extract_id_from_href("/marketplace/item/12345/") == "12345"

    def test_href_with_query_params(self):
        assert MarketplaceScraper._extract_id_from_href("/marketplace/item/67890/?ref=search") == "67890"

    def test_invalid_href(self):
        assert MarketplaceScraper._extract_id_from_href("/some/other/path") is None

    def test_non_numeric_id(self):
        assert MarketplaceScraper._extract_id_from_href("/marketplace/item/abc/") is None


class TestStorage:
    def test_save_listings_creates_file(self, tmp_path: Path):
        listings = [Listing(id="100", title="Test Item")]
        filepath = save_listings(listings, tmp_path, query="test", location="toronto")

        assert filepath.exists()
        assert filepath.suffix == ".json"
        assert "toronto" in filepath.name
        assert "test" in filepath.name

        data = json.loads(filepath.read_text())
        assert data["metadata"]["total_listings"] == 1
        assert data["listings"][0]["id"] == "100"

    def test_save_listings_creates_directory(self, tmp_path: Path):
        output_dir = tmp_path / "nested" / "dir"
        filepath = save_listings([], output_dir, query="q", location="loc")
        assert output_dir.exists()
        assert filepath.exists()

    def test_save_empty_listings(self, tmp_path: Path):
        filepath = save_listings([], tmp_path, query="", location="")
        data = json.loads(filepath.read_text())
        assert data["metadata"]["total_listings"] == 0
        assert data["listings"] == []
