from __future__ import annotations

import json
from pathlib import Path

from .models import InjectedRepository


class RepositoryRegistry:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def list(self) -> tuple[InjectedRepository, ...]:
        payload = self._read()
        return tuple(InjectedRepository(**item) for item in payload)

    def get(self, repo_id: str) -> InjectedRepository | None:
        for repo in self.list():
            if repo.id == repo_id:
                return repo
        return None

    def upsert(self, repository: InjectedRepository) -> InjectedRepository:
        items = list(self._read())
        replaced = False
        for index, current in enumerate(items):
            if current["id"] == repository.id:
                items[index] = repository.to_dict()
                replaced = True
                break
        if not replaced:
            items.append(repository.to_dict())
        self._write(items)
        return repository

    def _read(self) -> list[dict[str, object]]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _write(self, payload: list[dict[str, object]]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
