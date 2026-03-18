from __future__ import annotations

from .browser import BrowserConfig, create_webdriver
from .github_scraper import GitHubScraper
from .models import (
    ContentFetcher,
    CrawlError,
    CrawlResult,
    CrawlSpec,
    FileRef,
    FileTraverser,
    Platform,
    RepoRef,
)

__all__: list[str] = [
    "BrowserConfig",
    "ContentFetcher",
    "CrawlError",
    "CrawlResult",
    "CrawlSpec",
    "FileRef",
    "FileTraverser",
    "GitHubScraper",
    "Platform",
    "RepoRef",
    "__version__",
    "create_webdriver",
]

__version__ = "0.1.0"
