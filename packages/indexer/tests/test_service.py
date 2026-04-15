from __future__ import annotations

from pathlib import Path

from libscout_index.service import LibScoutService


def test_local_repository_injection_and_search(tmp_path: Path) -> None:
    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "auth.py").write_text(
        """
class TokenStore:
    def issue_token(self, user_id: str) -> str:
        token = f"tok-{user_id}"
        return token
""".strip(),
        encoding="utf-8",
    )

    service = LibScoutService(tmp_path / "libscout-data")
    repository = service.inject_local_repository(path=str(repo_dir), owner="tests", name="demo")
    report = service.index_repository(repository.id)
    hits = service.search(query="issue token for user", limit=3)

    assert report.indexed_files == 1
    assert report.indexed_chunks >= 1
    assert hits
    assert hits[0].path == "auth.py"
