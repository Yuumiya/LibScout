from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from selenium.webdriver.remote.webdriver import WebDriver


class Platform(StrEnum):
    GITHUB = "github"


@dataclass(frozen=True)
class CrawlSpec:
    platform: Platform
    search_terms: tuple[str, ...]
    max_repos: int = 25


@dataclass(frozen=True)
class CrawlError:
    repository: RepoRef | None
    message: str


@dataclass(frozen=True)
class CrawlResult:
    spec: CrawlSpec
    repositories: tuple[RepoRef, ...]
    errors: tuple[CrawlError, ...] = ()


@runtime_checkable
class ContentFetcher(Protocol):
    def __call__(self, url: str) -> str:  # pragma: no cover - protocol signature
        ...


@runtime_checkable
class FileTraverser(Protocol):
    def __call__(self, driver: WebDriver, repo: RepoRef) -> Iterator[FileRef]:  # pragma: no cover
        ...


@dataclass(frozen=True)
class RepoRef:
    owner: str
    name: str
    driver: WebDriver
    default_branch: str = "main"
    traverser: FileTraverser | None = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    def iter_files(self) -> Iterator[FileRef]:
        if self.traverser is None:
            return iter(())
        return self.traverser(self.driver, self)


@dataclass(frozen=True)
class FileRef:
    repo: RepoRef
    path: str
    sha: str | None = None

    @property
    def raw_url(self) -> str:
        branch = self.sha or self.repo.default_branch
        return f"https://raw.githubusercontent.com/{self.repo.full_name}/{branch}/{self.path}"

    def fetch_text(self, fetcher: ContentFetcher) -> str:
        return fetcher(self.raw_url)
