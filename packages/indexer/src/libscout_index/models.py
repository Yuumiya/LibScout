from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path

from libscout_scraper.models import RepoRef


@dataclass(frozen=True)
class InjectedRepository:
    id: str
    source: str
    owner: str
    name: str
    full_name: str
    local_dir: str
    default_branch: str = "main"
    ref: str | None = None
    indexed_file_count: int = 0
    indexed_chunk_count: int = 0
    last_indexed_at: str | None = None

    def to_repo_ref(self) -> RepoRef:
        return RepoRef(
            owner=self.owner,
            name=self.name,
            default_branch=self.default_branch,
            local_dir=Path(self.local_dir),
        )

    def with_index_stats(self, *, file_count: int, chunk_count: int, indexed_at: str) -> InjectedRepository:
        return replace(
            self,
            indexed_file_count=file_count,
            indexed_chunk_count=chunk_count,
            last_indexed_at=indexed_at,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SearchHit:
    repo_id: str
    repo_name: str
    path: str
    language: str
    node_type: str
    symbol: str | None
    start_line: int
    end_line: int
    score: float
    excerpt: str
    cst_path: str
    scope_type: str | None = None
    identifiers: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()


@dataclass(frozen=True)
class RagAnswer:
    query: str
    answer: str
    hits: tuple[SearchHit, ...]


@dataclass(frozen=True)
class IndexReport:
    repository: InjectedRepository
    indexed_files: int
    indexed_chunks: int
    skipped_files: int


@dataclass(frozen=True)
class GitHubRepoSeed:
    owner: str
    name: str
    ref: str | None = None
