from __future__ import annotations

import argparse
from pathlib import Path

from libscout_index.service import LibScoutService
from libscout_index.seeds import DEFAULT_GITHUB_REPO_SEEDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject a curated list of GitHub repositories without the scraper.")
    _ = parser.add_argument("--root-dir", default=".libscout", help="LibScout data directory.")
    _ = parser.add_argument("--no-index", action="store_true", help="Inject repositories without indexing them.")
    _ = parser.add_argument("--github-token", default=None, help="GitHub token for higher API limits.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = LibScoutService(root_dir=Path(args.root_dir))
    results = service.inject_github_repositories(
        DEFAULT_GITHUB_REPO_SEEDS,
        token=args.github_token,
        index_now=not args.no_index,
    )
    print(f"Seeded {len(results)} repositories:")
    for result in results:
        if hasattr(result, "repository"):
            print(
                f"- {result.repository.full_name}: "
                f"{result.indexed_files} files, {result.indexed_chunks} chunks, {result.skipped_files} skipped"
            )
        else:
            print(f"- {result.full_name}")


if __name__ == "__main__":
    main()
