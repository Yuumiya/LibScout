from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from libscout_index.api import create_app


def test_mcp_search_usage_returns_hits_and_sampling_request(tmp_path: Path) -> None:
    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "usage.py").write_text(
        """
import httpx

def fetch_user(user_id: str) -> dict:
    response = httpx.get(f"https://example.test/users/{user_id}")
    return response.json()
""".strip(),
        encoding="utf-8",
    )

    app = create_app(tmp_path / "libscout-data")
    client = TestClient(app)
    inject_response = client.post(
        "/api/repositories/inject",
        json={
            "source": "local",
            "path": str(repo_dir),
            "owner": "tests",
            "name": "demo",
            "index_now": True,
        },
    )
    assert inject_response.status_code == 200

    response = client.post("/mcp/search_usage", json={"query": "call:httpx.get", "limit": 3})

    assert response.status_code == 200
    payload = response.json()
    assert payload["hits"]
    assert payload["hits"][0]["symbol"] == "fetch_user"
    assert "sampling_request" in payload
    assert payload["sampling_request"]["method"] == "sampling/createMessage"
