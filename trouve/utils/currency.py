"""Static location → currency mapping for Facebook Marketplace regions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrencyInfo:
    code: str
    symbol: str


CURRENCIES: dict[str, CurrencyInfo] = {
    "USD": CurrencyInfo(code="USD", symbol="$"),
    "CAD": CurrencyInfo(code="CAD", symbol="CA$"),
    "GBP": CurrencyInfo(code="GBP", symbol="£"),
    "EUR": CurrencyInfo(code="EUR", symbol="€"),
    "AUD": CurrencyInfo(code="AUD", symbol="A$"),
    "NZD": CurrencyInfo(code="NZD", symbol="NZ$"),
    "JPY": CurrencyInfo(code="JPY", symbol="¥"),
    "MXN": CurrencyInfo(code="MXN", symbol="MX$"),
    "BRL": CurrencyInfo(code="BRL", symbol="R$"),
    "SEK": CurrencyInfo(code="SEK", symbol="kr"),
    "NOK": CurrencyInfo(code="NOK", symbol="kr"),
    "DKK": CurrencyInfo(code="DKK", symbol="kr"),
    "CHF": CurrencyInfo(code="CHF", symbol="CHF"),
    "INR": CurrencyInfo(code="INR", symbol="₹"),
    "PHP": CurrencyInfo(code="PHP", symbol="₱"),
    "ZAR": CurrencyInfo(code="ZAR", symbol="R"),
    "KRW": CurrencyInfo(code="KRW", symbol="₩"),
    "SGD": CurrencyInfo(code="SGD", symbol="S$"),
    "HKD": CurrencyInfo(code="HKD", symbol="HK$"),
    "TWD": CurrencyInfo(code="TWD", symbol="NT$"),
    "PLN": CurrencyInfo(code="PLN", symbol="zł"),
    "CZK": CurrencyInfo(code="CZK", symbol="Kč"),
    "HUF": CurrencyInfo(code="HUF", symbol="Ft"),
    "RON": CurrencyInfo(code="RON", symbol="lei"),
    "BGN": CurrencyInfo(code="BGN", symbol="лв"),
    "HRK": CurrencyInfo(code="HRK", symbol="kn"),
    "ILS": CurrencyInfo(code="ILS", symbol="₪"),
    "CLP": CurrencyInfo(code="CLP", symbol="CL$"),
    "COP": CurrencyInfo(code="COP", symbol="CO$"),
    "ARS": CurrencyInfo(code="ARS", symbol="AR$"),
    "PEN": CurrencyInfo(code="PEN", symbol="S/"),
}

_DEFAULT = CURRENCIES["USD"]

# Facebook Marketplace location slugs → currency code.
# Covers common cities; unknown locations fall back to USD.
LOCATION_CURRENCIES: dict[str, str] = {
    # ── United States ──
    "seattle": "USD",
    "portland": "USD",
    "san-francisco": "USD",
    "san-jose": "USD",
    "los-angeles": "USD",
    "san-diego": "USD",
    "sacramento": "USD",
    "las-vegas": "USD",
    "phoenix": "USD",
    "tucson": "USD",
    "denver": "USD",
    "salt-lake-city": "USD",
    "boise": "USD",
    "austin": "USD",
    "dallas": "USD",
    "houston": "USD",
    "san-antonio": "USD",
    "chicago": "USD",
    "detroit": "USD",
    "minneapolis": "USD",
    "milwaukee": "USD",
    "indianapolis": "USD",
    "columbus": "USD",
    "cleveland": "USD",
    "pittsburgh": "USD",
    "philadelphia": "USD",
    "nyc": "USD",
    "new-york": "USD",
    "boston": "USD",
    "baltimore": "USD",
    "dc": "USD",
    "washington": "USD",
    "atlanta": "USD",
    "miami": "USD",
    "tampa": "USD",
    "orlando": "USD",
    "charlotte": "USD",
    "raleigh": "USD",
    "nashville": "USD",
    "memphis": "USD",
    "new-orleans": "USD",
    "st-louis": "USD",
    "kansas-city": "USD",
    "oklahoma-city": "USD",
    "albuquerque": "USD",
    "honolulu": "USD",
    "anchorage": "USD",
    # ── Canada ──
    "toronto": "CAD",
    "vancouver": "CAD",
    "montreal": "CAD",
    "calgary": "CAD",
    "edmonton": "CAD",
    "ottawa": "CAD",
    "winnipeg": "CAD",
    "hamilton": "CAD",
    "quebec": "CAD",
    "halifax": "CAD",
    "victoria": "CAD",
    "saskatoon": "CAD",
    "regina": "CAD",
    # ── United Kingdom ──
    "london": "GBP",
    "manchester": "GBP",
    "birmingham": "GBP",
    "leeds": "GBP",
    "glasgow": "GBP",
    "liverpool": "GBP",
    "edinburgh": "GBP",
    "bristol": "GBP",
    "cardiff": "GBP",
    "belfast": "GBP",
    "sheffield": "GBP",
    "nottingham": "GBP",
    "newcastle": "GBP",
    # ── Ireland ──
    "dublin": "EUR",
    "cork": "EUR",
    "galway": "EUR",
    # ── Germany ──
    "berlin": "EUR",
    "munich": "EUR",
    "hamburg": "EUR",
    "cologne": "EUR",
    "frankfurt": "EUR",
    "stuttgart": "EUR",
    "dusseldorf": "EUR",
    # ── France ──
    "paris": "EUR",
    "lyon": "EUR",
    "marseille": "EUR",
    "toulouse": "EUR",
    "bordeaux": "EUR",
    # ── Spain ──
    "madrid": "EUR",
    "barcelona": "EUR",
    "valencia": "EUR",
    "seville": "EUR",
    # ── Italy ──
    "rome": "EUR",
    "milan": "EUR",
    "naples": "EUR",
    "turin": "EUR",
    # ── Netherlands ──
    "amsterdam": "EUR",
    "rotterdam": "EUR",
    "the-hague": "EUR",
    # ── Belgium ──
    "brussels": "EUR",
    "antwerp": "EUR",
    # ── Portugal ──
    "lisbon": "EUR",
    "porto": "EUR",
    # ── Austria ──
    "vienna": "EUR",
    # ── Finland ──
    "helsinki": "EUR",
    # ── Greece ──
    "athens": "EUR",
    # ── Australia ──
    "sydney": "AUD",
    "melbourne": "AUD",
    "brisbane": "AUD",
    "perth": "AUD",
    "adelaide": "AUD",
    "gold-coast": "AUD",
    "canberra": "AUD",
    # ── New Zealand ──
    "auckland": "NZD",
    "wellington": "NZD",
    "christchurch": "NZD",
    # ── Japan ──
    "tokyo": "JPY",
    "osaka": "JPY",
    "kyoto": "JPY",
    "yokohama": "JPY",
    # ── Mexico ──
    "mexico-city": "MXN",
    "guadalajara": "MXN",
    "monterrey": "MXN",
    "tijuana": "MXN",
    # ── Brazil ──
    "sao-paulo": "BRL",
    "rio-de-janeiro": "BRL",
    # ── Sweden ──
    "stockholm": "SEK",
    "gothenburg": "SEK",
    # ── Norway ──
    "oslo": "NOK",
    "bergen": "NOK",
    # ── Denmark ──
    "copenhagen": "DKK",
    # ── Switzerland ──
    "zurich": "CHF",
    "geneva": "CHF",
    # ── India ──
    "mumbai": "INR",
    "delhi": "INR",
    "bangalore": "INR",
    "chennai": "INR",
    # ── Philippines ──
    "manila": "PHP",
    "cebu": "PHP",
    # ── South Africa ──
    "cape-town": "ZAR",
    "johannesburg": "ZAR",
    # ── South Korea ──
    "seoul": "KRW",
    "busan": "KRW",
    # ── Singapore ──
    "singapore": "SGD",
    # ── Hong Kong ──
    "hong-kong": "HKD",
    # ── Taiwan ──
    "taipei": "TWD",
    # ── Poland ──
    "warsaw": "PLN",
    "krakow": "PLN",
    # ── Czech Republic ──
    "prague": "CZK",
    # ── Hungary ──
    "budapest": "HUF",
    # ── Romania ──
    "bucharest": "RON",
    # ── Israel ──
    "tel-aviv": "ILS",
    # ── South America ──
    "santiago": "CLP",
    "bogota": "COP",
    "buenos-aires": "ARS",
    "lima": "PEN",
}


def get_currency(location: str) -> CurrencyInfo:
    """Resolve a Facebook Marketplace location slug to its currency.

    Case-insensitive lookup. Falls back to USD for unknown locations.
    """
    code = LOCATION_CURRENCIES.get(location.lower())
    if code is None:
        return _DEFAULT
    return CURRENCIES[code]
