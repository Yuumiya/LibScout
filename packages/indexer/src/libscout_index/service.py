from __future__ import annotations

import hashlib
import json
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import chromadb

from libscout_parser import ParseError, UnsupportedLanguageError, extract_cst_chunks, parse_file
from libscout_scraper.downloader import download_repo

from .embeddings import HashedEmbeddingModel
from .models import GitHubRepoSeed, IndexReport, InjectedRepository, RagAnswer, SearchHit
from .registry import RepositoryRegistry
from .seeds import DEFAULT_GITHUB_REPO_SEEDS

logger = logging.getLogger(__name__)
_QUERY_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")
_NON_CODE_LANGUAGES = {"markdown", "text", "yaml", "toml", "json"}
_QUERY_LIBRARY_ALIASES = {
    "fastapi": "fastapi",
    "httpx": "httpx",
    "typer": "typer",
    "pydantic": "pydantic",
    "chroma": "chroma",
    "langchain": "langchain",
    "ruff": "ruff",
    "uv": "uv",
    "tree-sitter": "tree_sitter",
    "treesitter": "tree_sitter",
}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "do",
    "does",
    "for",
    "how",
    "i",
    "in",
    "is",
    "of",
    "the",
    "to",
    "use",
    "using",
    "what",
    "where",
    "with",
}


class LibScoutService:
    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._repos_dir = self._root_dir / "repos"
        self._repos_dir.mkdir(parents=True, exist_ok=True)
        self._chunk_cache_dir = self._root_dir / "chunk_cache"
        self._chunk_cache_dir.mkdir(parents=True, exist_ok=True)
        self._rebuild_marker_path = self._root_dir / "reindexing.lock"
        self._registry = RepositoryRegistry(self._root_dir / "repositories.json")
        self._embedding_model = HashedEmbeddingModel()
        self._client = chromadb.PersistentClient(path=str(self._root_dir / "chroma"))
        self._collection = self._client.get_or_create_collection(name="libscout_chunks")
        self._max_batch_size = int(getattr(self._client, "get_max_batch_size", lambda: 5000)())

    def list_repositories(self) -> tuple[InjectedRepository, ...]:
        return self._registry.list()

    def inject_github_repository(
        self,
        *,
        owner: str,
        name: str,
        token: str | None = None,
        ref: str | None = None,
    ) -> InjectedRepository:
        repo_key = f"github:{owner}/{name}:{ref or 'default'}"
        repo_id = _stable_id(repo_key)
        dest_dir = self._repos_dir / repo_id
        result = download_repo(owner, name, token=token, dest_dir=dest_dir, ref=ref)
        repository = InjectedRepository(
            id=repo_id,
            source="github",
            owner=owner,
            name=name,
            full_name=f"{owner}/{name}",
            local_dir=str(result.local_dir),
            default_branch=result.default_branch,
            ref=ref,
        )
        return self._registry.upsert(repository)

    def inject_github_repositories(
        self,
        repositories: tuple[GitHubRepoSeed, ...] = DEFAULT_GITHUB_REPO_SEEDS,
        *,
        token: str | None = None,
        index_now: bool = True,
    ) -> tuple[IndexReport | InjectedRepository, ...]:
        results: list[IndexReport | InjectedRepository] = []
        for repository in repositories:
            injected = self.inject_github_repository(
                owner=repository.owner,
                name=repository.name,
                token=token,
                ref=repository.ref,
            )
            if index_now:
                results.append(self.index_repository(injected.id))
            else:
                results.append(injected)
        return tuple(results)

    def inject_local_repository(self, *, path: str, owner: str | None = None, name: str | None = None) -> InjectedRepository:
        local_dir = Path(path).expanduser().resolve()
        if not local_dir.is_dir():
            raise ValueError(f"Local repository path does not exist: {local_dir}")
        repo_name = name or local_dir.name
        repo_owner = owner or "local"
        repo_key = f"local:{local_dir}"
        repository = InjectedRepository(
            id=_stable_id(repo_key),
            source="local",
            owner=repo_owner,
            name=repo_name,
            full_name=f"{repo_owner}/{repo_name}",
            local_dir=str(local_dir),
        )
        return self._registry.upsert(repository)

    def index_repository(self, repo_id: str) -> IndexReport:
        repository = self._registry.get(repo_id)
        if repository is None:
            raise KeyError(f"Unknown repository: {repo_id}")

        repo_ref = repository.to_repo_ref()
        self._delete_repository_chunks(repository.id)

        ids: list[str] = []
        documents: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, object]] = []
        cache_rows: list[dict[str, object]] = []
        indexed_files = 0
        indexed_chunks = 0
        skipped_files = 0

        for file_ref in repo_ref.iter_files():
            if repo_ref.local_dir is None:
                skipped_files += 1
                continue
            absolute_path = repo_ref.local_dir / file_ref.path
            if not absolute_path.is_file():
                skipped_files += 1
                continue
            try:
                parse_result = parse_file(absolute_path)
            except (UnsupportedLanguageError, ParseError, OSError):
                skipped_files += 1
                continue

            chunks = extract_cst_chunks(parse_result)
            if not chunks:
                skipped_files += 1
                continue

            indexed_files += 1
            for chunk_index, chunk in enumerate(chunks):
                indexed_chunks += 1
                chunk_id = _stable_id(
                    ":".join(
                        [
                            repository.id,
                            file_ref.path,
                            str(chunk_index),
                            str(chunk.start_byte),
                            str(chunk.end_byte),
                            chunk.node_type,
                            chunk.cst_path,
                            chunk.symbol or "",
                        ]
                    )
                )
                ids.append(chunk_id)
                documents.append(chunk.text)
                embeddings.append(
                    self._embedding_model.embed_chunk(
                        repo_name=repository.full_name,
                        path=file_ref.path,
                        language=chunk.language,
                        node_type=chunk.node_type,
                        cst_path=chunk.cst_path,
                        text=chunk.text,
                    )
                )
                metadatas.append(
                    {
                        "repo_id": repository.id,
                        "repo_name": repository.full_name,
                        "path": file_ref.path,
                        "language": chunk.language,
                        "node_type": chunk.node_type,
                        "symbol": chunk.symbol or "",
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "cst_path": chunk.cst_path,
                        "scope_type": chunk.scope_type or "",
                    }
                )
                cache_rows.append(
                    {
                        "repo_id": repository.id,
                        "repo_name": repository.full_name,
                        "path": file_ref.path,
                        "language": chunk.language,
                        "node_type": chunk.node_type,
                        "symbol": chunk.symbol,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "cst_path": chunk.cst_path,
                        "scope_type": chunk.scope_type,
                        "identifiers": list(chunk.identifiers),
                        "calls": list(chunk.calls),
                        "imports": list(chunk.imports),
                        "excerpt": chunk.text[:1200],
                        "text": chunk.text,
                    }
                )

        if ids:
            self._add_in_batches(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        self._write_chunk_cache(repository.id, cache_rows)

        indexed_at = datetime.now(UTC).isoformat()
        updated_repository = repository.with_index_stats(
            file_count=indexed_files,
            chunk_count=indexed_chunks,
            indexed_at=indexed_at,
        )
        self._registry.upsert(updated_repository)
        return IndexReport(
            repository=updated_repository,
            indexed_files=indexed_files,
            indexed_chunks=indexed_chunks,
            skipped_files=skipped_files,
        )

    def rebuild_search_index(self) -> tuple[IndexReport, ...]:
        with self._rebuild_marker():
            try:
                self._client.delete_collection(name="libscout_chunks")
            except Exception:
                pass
            self._collection = self._client.get_or_create_collection(name="libscout_chunks")
            reports: list[IndexReport] = []
            for repository in self._registry.list():
                local_dir = Path(repository.local_dir)
                if not local_dir.is_dir():
                    continue
                reports.append(self.index_repository(repository.id))
            return tuple(reports)

    def search(self, *, query: str, limit: int = 8, repo_ids: tuple[str, ...] = ()) -> tuple[SearchHit, ...]:
        if not query.strip():
            return ()
        structural_hits = self._structural_search(query=query, repo_ids=repo_ids, limit=max(limit * 10, 60))
        if self._rebuild_marker_path.exists():
            return structural_hits[:limit]

        where = _build_repo_where(repo_ids)
        vector_limit = max(limit * 6, 30)
        try:
            result = self._query_collection(query=query, limit=vector_limit, where=where)
        except Exception as exc:
            if _is_missing_id_error(exc):
                logger.warning("Chroma query failed with missing-id error; rebuilding collection and retrying once.")
                self._rebuild_collection()
                result = self._query_collection(query=query, limit=vector_limit, where=where)
            else:
                logger.warning("Chroma query failed; returning structural hits: %s", exc)
                return structural_hits[:limit]

        vector_hits = _hits_from_query(result)
        merged_hits = _merge_and_rerank_hits(query=query, hits=structural_hits + vector_hits)
        return merged_hits[:limit]

    def answer(self, *, query: str, limit: int = 6, repo_ids: tuple[str, ...] = ()) -> RagAnswer:
        hits = self.search(query=query, limit=limit, repo_ids=repo_ids)
        if not hits:
            return RagAnswer(query=query, answer="No indexed source matched the query.", hits=())

        lines = [f"Query: {query}", "", "Relevant evidence:"]
        for hit in hits[: min(4, len(hits))]:
            lines.append(
                f"- {hit.repo_name} {hit.path}:{hit.start_line}-{hit.end_line} "
                f"({hit.language}, {hit.node_type}) score={hit.score:.3f}"
            )
        lines.append("")
        lines.append("Synthesis:")
        lines.append("The strongest matches cluster around the files and CST nodes listed above.")
        lines.append("Use the cited excerpts to ground any final answer or follow-up code inspection.")
        return RagAnswer(query=query, answer="\n".join(lines), hits=hits)

    def _delete_repository_chunks(self, repo_id: str) -> None:
        try:
            self._collection.delete(where={"repo_id": repo_id})
        except Exception:
            return

    def _query_collection(self, *, query: str, limit: int, where: dict[str, object] | None) -> dict[str, object]:
        return self._collection.query(
            query_embeddings=[self._embedding_model.embed_text(query)],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def _add_in_batches(
        self,
        *,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, object]],
    ) -> None:
        batch_size = max(1, self._max_batch_size)
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            self._collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
            )

    def _write_chunk_cache(self, repo_id: str, rows: list[dict[str, object]]) -> None:
        cache_path = self._chunk_cache_dir / f"{repo_id}.jsonl"
        with cache_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=True))
                handle.write("\n")

    def _structural_search(self, *, query: str, repo_ids: tuple[str, ...], limit: int) -> tuple[SearchHit, ...]:
        parsed_query = _parse_structural_query(query)
        allowed_repo_ids = set(repo_ids)
        scored_hits: list[tuple[float, SearchHit]] = []
        for cache_path in sorted(self._chunk_cache_dir.glob("*.jsonl")):
            repo_id = cache_path.stem
            if allowed_repo_ids and repo_id not in allowed_repo_ids:
                continue
            try:
                with cache_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        raw = json.loads(line)
                        if not isinstance(raw, dict):
                            continue
                        hit = SearchHit(
                            repo_id=str(raw.get("repo_id", "")),
                            repo_name=str(raw.get("repo_name", "")),
                            path=str(raw.get("path", "")),
                            language=str(raw.get("language", "")),
                            node_type=str(raw.get("node_type", "")),
                            symbol=str(raw.get("symbol", "")) or None,
                            start_line=int(raw.get("start_line", 0)),
                            end_line=int(raw.get("end_line", 0)),
                            score=0.0,
                            excerpt=str(raw.get("excerpt", "")),
                            cst_path=str(raw.get("cst_path", "")),
                            scope_type=str(raw.get("scope_type", "")) or None,
                            identifiers=tuple(_to_str_list(raw.get("identifiers"))),
                            calls=tuple(_to_str_list(raw.get("calls"))),
                            imports=tuple(_to_str_list(raw.get("imports"))),
                        )
                        structural_score = _structural_score(
                            parsed_query=parsed_query,
                            hit=hit,
                            text=str(raw.get("text", "")),
                        )
                        if structural_score <= 0.0:
                            continue
                        scored_hits.append((structural_score, hit))
            except OSError:
                continue

        scored_hits.sort(key=lambda item: item[0], reverse=True)
        return tuple(_replace_hit_score(hit, score) for score, hit in scored_hits[:limit])

    def _rebuild_collection(self) -> None:
        _ = self.rebuild_search_index()

    @contextmanager
    def _rebuild_marker(self) -> object:
        self._rebuild_marker_path.write_text("rebuilding\n", encoding="utf-8")
        try:
            yield
        finally:
            self._rebuild_marker_path.unlink(missing_ok=True)


def _stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _build_repo_where(repo_ids: tuple[str, ...]) -> dict[str, object] | None:
    if not repo_ids:
        return None
    if len(repo_ids) == 1:
        return {"repo_id": repo_ids[0]}
    return {"$or": [{"repo_id": repo_id} for repo_id in repo_ids]}


def _is_missing_id_error(exc: Exception) -> bool:
    return "Error finding id" in str(exc)


def _merge_and_rerank_hits(*, query: str, hits: tuple[SearchHit, ...]) -> tuple[SearchHit, ...]:
    merged: dict[tuple[str, str, int, int], SearchHit] = {}
    parsed_query = _parse_structural_query(query)
    for hit in hits:
        key = (hit.repo_id, hit.path, hit.start_line, hit.end_line)
        reranked_score = max(hit.score, _structural_score(parsed_query=parsed_query, hit=hit, text=hit.excerpt))
        candidate = _replace_hit_score(hit, reranked_score)
        current = merged.get(key)
        if current is None or candidate.score > current.score:
            merged[key] = candidate
    ordered = sorted(merged.values(), key=lambda hit: hit.score, reverse=True)
    return tuple(ordered)


def _replace_hit_score(hit: SearchHit, score: float) -> SearchHit:
    return SearchHit(
        repo_id=hit.repo_id,
        repo_name=hit.repo_name,
        path=hit.path,
        language=hit.language,
        node_type=hit.node_type,
        symbol=hit.symbol,
        start_line=hit.start_line,
        end_line=hit.end_line,
        score=score,
        excerpt=hit.excerpt,
        cst_path=hit.cst_path,
        scope_type=hit.scope_type,
        identifiers=hit.identifiers,
        calls=hit.calls,
        imports=hit.imports,
    )


def _structural_score(*, parsed_query: StructuralQuery, hit: SearchHit, text: str) -> float:
    if not parsed_query.tokens and not parsed_query.library_tokens:
        return 0.0

    hit_identifiers = {value.lower() for value in hit.identifiers}
    hit_calls = {value.lower() for value in hit.calls}
    hit_imports = {value.lower() for value in hit.imports}
    repo_name_lower = hit.repo_name.lower()
    path_lower = hit.path.lower()
    symbol_lower = (hit.symbol or "").lower()
    scope_lower = (hit.scope_type or hit.node_type).lower()
    text_lower = text.lower()

    score = _code_quality_boost(hit)

    for token in parsed_query.library_tokens:
        if token in repo_name_lower or token in path_lower or token in hit_imports:
            score += 1.4

    if parsed_query.exact_symbol:
        if parsed_query.exact_symbol == symbol_lower:
            score += 8.0
        elif parsed_query.exact_symbol in hit_calls:
            score += 5.0
        elif parsed_query.exact_symbol in hit_identifiers:
            score += 4.0

    for compound in parsed_query.compound_symbols:
        if compound == symbol_lower:
            score += 3.0
        if compound in hit_identifiers:
            score += 2.6
        if compound in hit_calls:
            score += 2.8
        if compound in hit_imports:
            score += 2.2

    for token in parsed_query.symbol_tokens:
        if token in hit_calls:
            score += 1.7
        if token in hit_imports:
            score += 1.3
        if token in hit_identifiers:
            score += 1.1
        if token == symbol_lower or token in symbol_lower:
            score += 1.4
        if token in path_lower:
            score += 0.7

    query_weights = {token: _token_weight(token) for token in parsed_query.tokens}
    total_weight = sum(query_weights.values()) or 1.0
    matched_weight = 0.0
    for token, weight in query_weights.items():
        if (
            token in hit_identifiers
            or token in hit_calls
            or token in hit_imports
            or token in repo_name_lower
            or token in path_lower
            or token in text_lower
        ):
            matched_weight += weight
    score += matched_weight / total_weight

    if parsed_query.intent == "import" and hit.imports:
        score += 0.8
    if parsed_query.intent == "call" and hit.calls:
        score += 0.8
    if parsed_query.intent == "definition" and "function" in scope_lower:
        score += 0.6
    if parsed_query.intent == "class" and "class" in scope_lower:
        score += 0.6

    if "detect_language" in hit_identifiers or "parse_file" in hit_identifiers:
        if {"parse", "language"} & set(parsed_query.tokens):
            score += 0.6

    return score


def _code_quality_boost(hit: SearchHit) -> float:
    score = 0.0
    if hit.language not in _NON_CODE_LANGUAGES:
        score += 0.15
    if "docs/" in hit.path or hit.language in _NON_CODE_LANGUAGES or hit.node_type == "document":
        score -= 0.25
    if "test" in hit.path.lower():
        score -= 0.05
    return score


def _tokenize(value: str) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in _QUERY_TOKEN_RE.findall(value):
        normalized = token.lower()
        if normalized in _STOPWORDS:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        tokens.append(normalized)
    return tuple(tokens)


def _token_weight(token: str) -> float:
    if len(token) >= 10:
        return 2.5
    if len(token) >= 7:
        return 2.0
    if len(token) >= 5:
        return 1.5
    return 1.0


@dataclass(frozen=True)
class StructuralQuery:
    raw: str
    tokens: tuple[str, ...]
    library_tokens: tuple[str, ...]
    symbol_tokens: tuple[str, ...]
    compound_symbols: tuple[str, ...]
    exact_symbol: str | None = None
    intent: str | None = None


def _parse_structural_query(query: str) -> StructuralQuery:
    tokens = _tokenize(query)
    library_tokens = tuple(token for token in tokens if token in _QUERY_LIBRARY_ALIASES or token in {"fastapi", "typer", "httpx"})
    symbol_tokens = tuple(token for token in tokens if len(token) >= 4 and token not in library_tokens)
    compound_symbols = _compound_symbols(tokens)
    exact_symbol: str | None = tokens[0] if len(tokens) == 1 else None
    intent: str | None = None
    lowered = query.lower()
    if any(word in lowered for word in {"import", "from "}):
        intent = "import"
    elif any(word in lowered for word in {"call", "invoke", "use "}):
        intent = "call"
    elif "class" in lowered:
        intent = "class"
    elif any(word in lowered for word in {"define", "function", "method", "parse"}):
        intent = "definition"
    return StructuralQuery(
        raw=query,
        tokens=tokens,
        library_tokens=library_tokens,
        symbol_tokens=symbol_tokens,
        compound_symbols=compound_symbols,
        exact_symbol=exact_symbol,
        intent=intent,
    )


def _to_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _compound_symbols(tokens: tuple[str, ...]) -> tuple[str, ...]:
    compounds: list[str] = []
    seen: set[str] = set()
    for size in (2, 3):
        for index in range(0, len(tokens) - size + 1):
            compound = "_".join(tokens[index : index + size])
            if compound in seen:
                continue
            seen.add(compound)
            compounds.append(compound)
    return tuple(compounds)


def _hits_from_query(result: dict[str, object]) -> tuple[SearchHit, ...]:
    documents = result.get("documents", [[]])
    metadatas = result.get("metadatas", [[]])
    distances = result.get("distances", [[]])
    first_documents = documents[0] if isinstance(documents, list) and documents else []
    first_metadatas = metadatas[0] if isinstance(metadatas, list) and metadatas else []
    first_distances = distances[0] if isinstance(distances, list) and distances else []

    hits: list[SearchHit] = []
    for document, metadata, distance in zip(first_documents, first_metadatas, first_distances, strict=False):
        if not isinstance(document, str) or not isinstance(metadata, dict):
            continue
        numeric_distance = float(distance) if isinstance(distance, (int, float)) else 1.0
        score = 1.0 / (1.0 + max(numeric_distance, 0.0))
        hits.append(
            SearchHit(
                repo_id=str(metadata.get("repo_id", "")),
                repo_name=str(metadata.get("repo_name", "")),
                path=str(metadata.get("path", "")),
                language=str(metadata.get("language", "")),
                node_type=str(metadata.get("node_type", "")),
                symbol=str(metadata.get("symbol", "")) or None,
                start_line=int(metadata.get("start_line", 0)),
                end_line=int(metadata.get("end_line", 0)),
                score=score,
                excerpt=document[:1200],
                cst_path=str(metadata.get("cst_path", "")),
                scope_type=str(metadata.get("scope_type", "")) or None,
                identifiers=(),
                calls=(),
                imports=(),
            )
        )
    return tuple(hits)
