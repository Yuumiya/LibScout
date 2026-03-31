from __future__ import annotations

# demo_scrape_and_parse.py — LibScout end-to-end pipeline demo
#
# Demonstrates the full scraper → parser workflow:
#   1. Downloads the WeetHet/holonomy repository via the GitHub API
#   2. Wraps the result in a RepoRef and walks the file tree
#   3. Locates a known short Python file (holonomy/__init__.py)
#   4. Parses it with tree-sitter via libscout-parser
#   5. Prints repo info, file content, detected language, and the CST S-expression
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from libscout_parser import parse_file
from libscout_scraper.downloader import DownloadResult, download_repo
from libscout_scraper.models import FileRef, RepoRef

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

_OWNER = "WeetHet"
_NAME = "holonomy"
_TARGET_SUFFIX = "holonomy/__init__.py"

# ── Helpers ──────────────────────────────────────────────────────────────────


def _banner(title: str) -> None:
    """Print a simple section banner to stdout."""
    rule = "─" * 60
    print(f"\n{rule}")
    print(f"  {title}")
    print(rule)


def _find_target_file(files: list[FileRef], suffix: str) -> FileRef | None:
    """Return the first FileRef whose path ends with *suffix*, or ``None``."""
    for f in files:
        if f.path.endswith(suffix):
            return f
    return None


# ── Pipeline ─────────────────────────────────────────────────────────────────


def _run_pipeline(result: DownloadResult) -> None:
    """Core pipeline logic: build RepoRef, walk files, parse, and display."""

    # 2. Build a RepoRef from the DownloadResult
    repo: RepoRef = RepoRef(
        owner=result.owner,
        name=result.name,
        default_branch=result.default_branch,
        local_dir=result.local_dir,
    )

    _banner("Repository Info")
    print(f"  repo          : {repo.full_name}")
    print(f"  branch        : {repo.default_branch}")
    print(f"  local_dir     : {repo.local_dir}")

    # 3. Walk the repository file tree
    logger.info("Walking repository file tree …")
    all_files: list[FileRef] = list(repo.iter_files())
    file_count: int = len(all_files)

    _banner("File Summary")
    print(f"  total files   : {file_count}")

    sample_size: int = min(10, file_count)
    for f in all_files[:sample_size]:
        print(f"    • {f.path}")
    if file_count > sample_size:
        print(f"    … and {file_count - sample_size} more")

    # 4. Locate the target Python file
    target: FileRef | None = _find_target_file(all_files, _TARGET_SUFFIX)
    if target is None:
        logger.error("Could not find %s in the repository.", _TARGET_SUFFIX)
        sys.exit(1)

    logger.info("Found target file: %s", target.path)
    content: str = target.fetch_text()

    _banner(f"File Content — {target.path}")
    print(content)

    # 5. Parse with tree-sitter via libscout-parser
    assert repo.local_dir is not None
    absolute_path: Path = repo.local_dir / target.path

    logger.info("Parsing %s with tree-sitter …", absolute_path.name)
    parse_result = parse_file(absolute_path)

    _banner("Parse Result")
    print(f"  language      : {parse_result.language}")
    print(f"  source_path   : {parse_result.source_path}")
    print(f"  root node     : {parse_result.root_node.type}  (children: {parse_result.root_node.child_count})")

    _banner("S-Expression (CST)")
    print(parse_result.s_expression)

    _banner("Done ✓")


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    tmp_dir: Path = Path(tempfile.mkdtemp(prefix="libscout-demo-"))
    logger.info("Downloading %s/%s → %s", _OWNER, _NAME, tmp_dir)

    try:
        result: DownloadResult = download_repo(_OWNER, _NAME, dest_dir=tmp_dir)
        logger.info("Download complete — local_dir: %s", result.local_dir)
        _run_pipeline(result)
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
    finally:
        logger.info("Cleaning up %s", tmp_dir)
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
