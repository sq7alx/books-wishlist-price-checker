"""
app package initialization.
This package contains the core functionality for:
- Scraping Goodreads shelves (goodreads_scraper.py)
- Searching SkupSzop for prices (skupszop_search.py)
"""
from .goodreads_scraper import (
    scrape_goodreads_shelf,
    save_to_csv,
    run_goodreads_scraper,
)

__all__ = [
    "scrape_goodreads_shelf",
    "save_to_csv",
    "run_goodreads_scraper",
    "run_skupszop_search",
    "is_title_similar",
    "is_author_match",
]