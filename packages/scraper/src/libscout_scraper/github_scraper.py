from __future__ import annotations

import logging
import time
import urllib.parse
from collections.abc import Iterator, Sequence

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .downloader import RepoDownloadError, download_repo
from .models import CrawlError, CrawlResult, CrawlSpec, FileRef, FileTraverser, Platform, RepoRef

logger = logging.getLogger(__name__)


def _noop_traverser(driver: WebDriver, repo: RepoRef) -> Iterator[FileRef]:  # pyright: ignore[reportUnusedParameter]
    return iter(())


def _build_repo_search_url(base_url: str, search_terms: Sequence[str], page: int) -> str:
    query = " ".join(search_terms)
    encoded = urllib.parse.quote_plus(query)
    return f"{base_url}/search?p={page}&q={encoded}&type=repositories&o=desc&s=updated"


def _extract_repo_slugs(driver: WebDriver, limit: int) -> list[tuple[str, str]]:
    """Extract (owner, name) pairs from the current search results page."""
    results: list[tuple[str, str]] = []
    repo_items = driver.find_elements(By.CSS_SELECTOR, "article[data-testid='result-item']")
    if not repo_items:
        repo_items = driver.find_elements(By.CSS_SELECTOR, "li.repo-list-item")

    for item in repo_items:
        if len(results) >= limit:
            break
        anchors = item.find_elements(By.CSS_SELECTOR, "a[href*='github.com']") or item.find_elements(By.TAG_NAME, "a")
        href: str | None = None
        for anchor in anchors:
            candidate = anchor.get_attribute("href") or ""  # pyright: ignore[reportUnknownMemberType]
            if "github.com/" in candidate and candidate.rstrip("/").count("/") >= 4:
                continue
            if "github.com/" in candidate:
                href = candidate
                break
        if not href:
            continue
        try:
            owner, name = _parse_owner_repo(href)
        except ValueError:
            continue
        results.append((owner, name))
    return results


def _parse_owner_repo(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"Not a repository URL: {url}")
    owner, name = path_parts[0], path_parts[1]
    return owner, name


def _is_rate_limited(driver: WebDriver) -> bool:
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:  # noqa: BLE001
        return False
    return "too many requests" in body_text and "secondary rate limit" in body_text


class GitHubScraper:
    _driver: WebDriver
    _base_url: str
    _wait_seconds: float
    _file_traverser: FileTraverser
    _github_token: str | None

    def __init__(
        self,
        driver: WebDriver,
        base_url: str = "https://github.com",
        wait_seconds: float = 10.0,
        file_traverser: FileTraverser | None = None,
        github_token: str | None = None,
    ) -> None:
        self._driver = driver
        self._base_url = base_url.rstrip("/")
        self._wait_seconds = wait_seconds
        self._file_traverser = file_traverser or _noop_traverser
        self._github_token = github_token

    def crawl(self, spec: CrawlSpec) -> CrawlResult:
        if spec.platform != Platform.GITHUB:
            raise ValueError("GitHubScraper only supports Platform.GITHUB")

        errors: list[CrawlError] = []
        repo_slugs: list[tuple[str, str]] = []
        driver = self._driver

        page = 1
        while len(repo_slugs) < spec.max_repos:
            search_url = _build_repo_search_url(self._base_url, spec.search_terms, page)
            logger.info("Navigating to search page %s", search_url)
            driver.get(search_url)
            try:
                _ = WebDriverWait(driver, self._wait_seconds).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
                )
            except TimeoutException:
                errors.append(CrawlError(repository=None, message="Timed out waiting for search results page."))
                break

            if _is_rate_limited(driver):
                errors.append(
                    CrawlError(
                        repository=None,
                        message="Encountered GitHub 429 rate limit page; aborting crawl.",
                    )
                )
                break

            page_results = _extract_repo_slugs(driver, spec.max_repos - len(repo_slugs))
            if not page_results:
                logger.info("No more results found on page %s", page)
                break
            repo_slugs.extend(page_results)
            page += 1
            time.sleep(0.5)

        # Download each discovered repo via the GitHub API and build RepoRef objects.
        repo_refs: list[RepoRef] = []
        for owner, name in repo_slugs:
            try:
                result = download_repo(owner, name, token=self._github_token)
                repo_ref = RepoRef(
                    owner=owner,
                    name=name,
                    driver=driver,
                    default_branch=result.default_branch,
                    traverser=self._file_traverser,
                    local_dir=result.local_dir,
                )
                repo_refs.append(repo_ref)
                logger.info("Downloaded %s/%s to %s", owner, name, result.local_dir)
            except RepoDownloadError as exc:
                placeholder = RepoRef(owner=owner, name=name, driver=driver, traverser=self._file_traverser)
                errors.append(CrawlError(repository=placeholder, message=str(exc)))
                logger.warning("Failed to download %s/%s: %s", owner, name, exc)

        return CrawlResult(spec=spec, repositories=tuple(repo_refs), errors=tuple(errors))
