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


def test_structural_symbol_call_import_and_scope_search(tmp_path: Path) -> None:
    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "client.py").write_text(
        """
import httpx

class ApiClient:
    def fetch_user(self, user_id: str) -> dict:
        response = httpx.get(f"https://example.test/users/{user_id}")
        return response.json()

def unrelated() -> str:
    return "generic httpx example"
""".strip(),
        encoding="utf-8",
    )

    service = LibScoutService(tmp_path / "libscout-data")
    repository = service.inject_local_repository(path=str(repo_dir), owner="tests", name="demo")
    service.index_repository(repository.id)

    symbol_hits = service.search(query="symbol:fetch_user scope:function", limit=3)
    call_hits = service.search(query="call:httpx.get", limit=3)
    import_hits = service.search(query="import:httpx language:python", limit=3)
    language_mismatch_hits = service.search(query="import:httpx language:typescript", limit=3)

    assert symbol_hits
    assert symbol_hits[0].symbol == "fetch_user"
    assert symbol_hits[0].scope_type == "function"
    assert call_hits
    assert call_hits[0].symbol == "fetch_user"
    assert "httpx.get" in call_hits[0].calls
    assert import_hits
    assert import_hits[0].language == "python"
    assert "httpx" in import_hits[0].imports
    assert language_mismatch_hits == ()
