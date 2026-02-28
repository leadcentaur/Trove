import random
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProxySettings(BaseSettings):
    """Proxy configuration. All fields optional — no proxy if server is empty."""

    model_config = SettingsConfigDict(env_prefix="PROXY_")

    server: str = ""
    username: str = ""
    password: str = ""

    def to_playwright_proxy(self) -> Optional[dict]:
        """Return Playwright-compatible proxy dict, or None if not configured."""
        if not self.server:
            return None
        proxy = {"server": self.server}
        if self.username:
            proxy["username"] = self.username
        if self.password:
            proxy["password"] = self.password
        return proxy


class SearchParams(BaseSettings):
    """Search parameters that map to Marketplace URL query params."""

    model_config = SettingsConfigDict(env_prefix="SEARCH_")

    location: str = "seattle"
    query: str = ""
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    sort_by: str = "creation_time_descend"
    days_listed: Optional[int] = None

    def build_url(self) -> str:
        """Build the Facebook Marketplace search URL from parameters."""
        base = f"https://www.facebook.com/marketplace/{self.location}"

        if self.query:
            base += "/search/"

        params: dict[str, str] = {}
        if self.query:
            params["query"] = self.query
        if self.min_price is not None:
            params["minPrice"] = str(self.min_price)
        if self.max_price is not None:
            params["maxPrice"] = str(self.max_price)
        if self.sort_by and self.query:
            params["sortBy"] = self.sort_by
        if self.days_listed is not None:
            params["daysSinceListed"] = str(self.days_listed)

        if params:
            return f"{base}?{urlencode(params)}"
        return base + "/"


class Settings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Browser
    browser_headless: bool = False
    browser_profile_dir: Path = Path("./data/chrome_profile")
    chrome_channel: str = "chrome"

    # Delays
    min_delay: float = 5.0
    max_delay: float = 12.0
    scroll_pause: float = 3.0

    # Limits (0 = unlimited, default = random 90-115)
    max_listings: int = Field(default_factory=lambda: random.randint(90, 115))

    # Output
    output_dir: Path = Path("./data/raw")

    # Deal finder
    anthropic_api_key: str = ""
    reverb_api_token: str = ""
    deal_score_threshold: float = 0.30
    identifier_model: str = "claude-haiku-4-5-20251001"
    evaluator_model: str = "claude-sonnet-4-5-20250929"
    max_eval_concurrency: int = 5

    # Facebook login
    fb_email: str = ""
    fb_password: str = ""

    # Telegram notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Nested
    proxy: ProxySettings = Field(default_factory=ProxySettings)
    search: SearchParams = Field(default_factory=SearchParams)
