from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
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
    driver: WebDriver | None = None
    default_branch: str = "main"
    traverser: FileTraverser | None = None
    local_dir: Path | None = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    def iter_files(self) -> Iterator[FileRef]:
        """Yield ``FileRef`` objects for every file in the repository.

        When *local_dir* is set the method walks the local directory tree,
        yielding a ``FileRef`` for each regular file it finds.  This is the
        primary mechanism after API-based repo download.

        Falls back to the legacy ``FileTraverser`` protocol when *local_dir*
        is ``None`` and a *traverser* + *driver* are available.
        """
        if self.local_dir is not None:
            yield from _walk_local_dir(self, self.local_dir)
            return

        # Legacy traverser path (backward compat)
        if self.traverser is not None and self.driver is not None:
            yield from self.traverser(self.driver, self)
            return

        # Nothing configured – yield nothing.
        return


def _walk_local_dir(repo: RepoRef, local_dir: Path) -> Iterator[FileRef]:
    """Walk *local_dir* and yield a ``FileRef`` per regular file."""
    root = str(local_dir)
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in sorted(filenames):
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, root)
            yield FileRef(repo=repo, path=rel_path)


@dataclass(frozen=True)
class FileRef:
    repo: RepoRef
    path: str
    sha: str | None = None

    @property
    def raw_url(self) -> str:
        branch = self.sha or self.repo.default_branch
        return f"https://raw.githubusercontent.com/{self.repo.full_name}/{branch}/{self.path}"

    def fetch_text(self, fetcher: ContentFetcher | None = None) -> str:
        """Return the file content as a string.

        When the owning ``RepoRef`` has a *local_dir*, the file is read
        directly from the local filesystem and *fetcher* is ignored.

        Otherwise *fetcher* is called with ``self.raw_url`` (the legacy
        remote-fetch path).  A ``ValueError`` is raised if neither a local
        directory nor a fetcher is available.
        """
        if self.repo.local_dir is not None:
            local_path = self.repo.local_dir / self.path
            return local_path.read_text(encoding="utf-8", errors="replace")

        if fetcher is not None:
            return fetcher(self.raw_url)

        raise ValueError("Cannot fetch file text: RepoRef has no local_dir and no ContentFetcher was provided.")
