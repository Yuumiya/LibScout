from __future__ import annotations

from .browser import BrowserConfig, create_webdriver
from .downloader import DownloadResult, RepoDownloadError, download_repo
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
    "DownloadResult",
    "FileRef",
    "FileTraverser",
    "GitHubScraper",
    "Platform",
    "RepoDownloadError",
    "RepoRef",
    "__version__",
    "create_webdriver",
    "download_repo",
]

__version__ = "0.1.0"
