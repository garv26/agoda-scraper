"""Agoda Hotel Scraper Package"""

__version__ = "1.1.0"

from .multi_browser_scraper import (
    multi_browser_scrape,
    load_hotels_from_csv,
    set_proxies,
    PROXY_LIST,
)

