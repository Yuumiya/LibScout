from __future__ import annotations

import shutil
from pathlib import Path

import uvicorn

from libscout_index.api import create_app
from libscout_index.service import LibScoutService


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / ".playwright-data"
REPOS_ROOT = DATA_ROOT / "repos"
INDEX_ROOT = DATA_ROOT / "index"


def main() -> None:
    _reset_fixture_data()
    app = create_app(INDEX_ROOT)
    uvicorn.run(app, host="127.0.0.1", port=8123, log_level="warning")


def _reset_fixture_data() -> None:
    shutil.rmtree(DATA_ROOT, ignore_errors=True)
    REPOS_ROOT.mkdir(parents=True, exist_ok=True)

    python_repo = REPOS_ROOT / "fixture-py"
    python_repo.mkdir()
    (python_repo / "client.py").write_text(
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
    (python_repo / "fastapi_app.py").write_text(
        """
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str

@app.get("/items/{item_id}")
def read_item(item_id: str) -> Item:
    return Item(name=item_id)
""".strip(),
        encoding="utf-8",
    )
    (python_repo / "cli.py").write_text(
        """
import typer

def delete(force: bool = typer.Option(False, "--force")) -> None:
    print(f"delete force={force}")
""".strip(),
        encoding="utf-8",
    )

    typescript_repo = REPOS_ROOT / "fixture-ts"
    typescript_repo.mkdir()
    (typescript_repo / "usage.ts").write_text(
        """
import { request } from "./client"

export async function loadUser(userId: string) {
  const response = await request(`/users/${userId}`)
  return response.json()
}
""".strip(),
        encoding="utf-8",
    )

    service = LibScoutService(INDEX_ROOT)
    for path, name in ((python_repo, "fixture-py"), (typescript_repo, "fixture-ts")):
        repository = service.inject_local_repository(path=str(path), owner="tests", name=name)
        service.index_repository(repository.id)


if __name__ == "__main__":
    main()
