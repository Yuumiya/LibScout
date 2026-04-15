from __future__ import annotations

from pathlib import Path

from libscout_index.service import LibScoutService


def main() -> None:
    service = LibScoutService(Path(".libscout"))
    repositories = service.list_repositories()
    print(f"Reindexing {len(repositories)} repositories...")
    reports = service.rebuild_search_index()
    for report in reports:
        print(
            f"- {report.repository.full_name}: "
            f"{report.indexed_files} files, {report.indexed_chunks} chunks, {report.skipped_files} skipped"
        )


if __name__ == "__main__":
    main()
