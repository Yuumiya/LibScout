from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from libscout_scraper.browser import BrowserConfig, create_webdriver
from libscout_scraper.github_scraper import GitHubScraper
from libscout_scraper.models import CrawlSpec, Platform

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a GitHub crawl for recent repositories.")
    _ = parser.add_argument(
        "--search",
        nargs="+",
        required=True,
        help="Search terms to find repositories (e.g. --search tiny library auth).",
    )
    _ = parser.add_argument("--max-repos", type=int, default=5, help="Maximum repositories to return.")
    _ = parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the browser in headless mode when supported.",
    )
    _ = parser.add_argument(
        "--wait-seconds",
        type=float,
        default=15.0,
        help="Seconds to wait for search page to load.",
    )
    _ = parser.add_argument(
        "--user-agent",
        type=str,
        default=None,
        help="Custom user agent for the browser session.",
    )
    return parser.parse_args()


def run(
    search_terms: Sequence[str], max_repos: int, headless: bool, wait_seconds: float, user_agent: str | None
) -> None:
    config = BrowserConfig(headless=headless, implicit_wait_seconds=wait_seconds, user_agent=user_agent)
    driver = create_webdriver(config)
    scraper = GitHubScraper(driver=driver, wait_seconds=wait_seconds)

    try:
        spec = CrawlSpec(
            platform=Platform.GITHUB,
            search_terms=tuple(search_terms),
            max_repos=max_repos,
        )
        result = scraper.crawl(spec)
    finally:
        driver.quit()

    if result.errors:
        logger.warning("Encountered %d errors during crawl", len(result.errors))
        for err in result.errors:
            repo_name = err.repository.full_name if err.repository else "<search>"
            logger.warning("Error for %s: %s", repo_name, err.message)

    logger.info("Found %d repositories.", len(result.repositories))
    for idx, repo in enumerate(result.repositories, start=1):
        print(f"{idx}. {repo.full_name}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    run(args.search, args.max_repos, args.headless, args.wait_seconds, args.user_agent)  # pyright: ignore[reportAny]


if __name__ == "__main__":
    main()
