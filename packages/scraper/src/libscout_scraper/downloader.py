from __future__ import annotations

import logging
import os
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_API_BASE = "https://api.github.com"
_DOWNLOAD_TIMEOUT = 120.0


@dataclass(frozen=True)
class DownloadResult:
    """Result of downloading and extracting a repository tarball."""

    owner: str
    name: str
    local_dir: Path
    default_branch: str


class RepoDownloadError(Exception):
    """Raised when a repository download or extraction fails."""


def _build_headers(token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "LibScout/0.1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _resolve_token(token: str | None) -> str | None:
    if token is not None:
        return token
    return os.environ.get("GITHUB_TOKEN")


def _fetch_default_branch(
    client: httpx.Client,
    owner: str,
    name: str,
    api_base: str,
) -> str:
    url = f"{api_base}/repos/{owner}/{name}"
    logger.debug("Fetching repo metadata from %s", url)
    resp = client.get(url)
    if resp.status_code == 404:
        raise RepoDownloadError(f"Repository {owner}/{name} not found (404).")
    if resp.status_code == 403:
        raise RepoDownloadError(f"Access denied for {owner}/{name}; check GITHUB_TOKEN or rate limits.")
    _ = resp.raise_for_status()
    data = cast(dict[str, object], resp.json())
    branch = str(data.get("default_branch", "main"))
    return branch


def _download_tarball(
    client: httpx.Client,
    owner: str,
    name: str,
    api_base: str,
    ref: str | None = None,
) -> bytes:
    url = f"{api_base}/repos/{owner}/{name}/tarball"
    if ref:
        url = f"{url}/{ref}"
    logger.info("Downloading tarball from %s", url)
    resp = client.get(url, follow_redirects=True)
    if resp.status_code == 404:
        raise RepoDownloadError(f"Tarball not found for {owner}/{name} (404).")
    if resp.status_code == 403:
        raise RepoDownloadError(f"Access denied downloading {owner}/{name}; check GITHUB_TOKEN or rate limits.")
    _ = resp.raise_for_status()
    return resp.content


def _extract_tarball(tarball_bytes: bytes, dest_dir: Path) -> Path:
    tarball_path = dest_dir / "repo.tar.gz"
    _ = tarball_path.write_bytes(tarball_bytes)

    with tarfile.open(tarball_path, "r:gz") as tar:
        # GitHub tarballs contain a single top-level directory like "owner-name-sha1234/"
        members = tar.getmembers()
        if not members:
            raise RepoDownloadError("Downloaded tarball is empty.")

        # Find the common top-level prefix
        top_level_dirs = {m.name.split("/")[0] for m in members if m.name}
        if len(top_level_dirs) != 1:
            # Unusual layout — extract as-is
            tar.extractall(dest_dir, filter="data")
            tarball_path.unlink(missing_ok=True)
            return dest_dir

        top_dir_name = top_level_dirs.pop()
        tar.extractall(dest_dir, filter="data")

    tarball_path.unlink(missing_ok=True)
    extracted = dest_dir / top_dir_name
    if extracted.is_dir():
        return extracted
    return dest_dir


def download_repo(
    owner: str,
    name: str,
    *,
    token: str | None = None,
    api_base: str = _DEFAULT_API_BASE,
    dest_dir: Path | None = None,
    ref: str | None = None,
) -> DownloadResult:
    """Download a GitHub repository tarball and extract it to a local directory.

    Args:
        owner: Repository owner (user or org).
        name: Repository name.
        token: GitHub personal access token. Falls back to ``GITHUB_TOKEN`` env var.
        api_base: GitHub API base URL.
        dest_dir: Directory to extract into. A temporary directory is created if not provided.
        ref: Git ref (branch/tag/sha) to download. Defaults to the repo's default branch.

    Returns:
        A ``DownloadResult`` with the local extraction path and resolved default branch.

    Raises:
        RepoDownloadError: If the download or extraction fails.
    """
    resolved_token = _resolve_token(token)
    headers = _build_headers(resolved_token)

    with httpx.Client(headers=headers, timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        default_branch = _fetch_default_branch(client, owner, name, api_base)
        download_ref = ref or default_branch

        tarball_bytes = _download_tarball(client, owner, name, api_base, ref=download_ref)

    if dest_dir is None:
        dest_dir = Path(tempfile.mkdtemp(prefix=f"libscout-{owner}-{name}-"))

    dest_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting %s/%s to %s", owner, name, dest_dir)
    local_dir = _extract_tarball(tarball_bytes, dest_dir)

    return DownloadResult(
        owner=owner,
        name=name,
        local_dir=local_dir,
        default_branch=default_branch,
    )
