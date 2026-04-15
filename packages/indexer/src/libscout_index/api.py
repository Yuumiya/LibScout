from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .service import LibScoutService
from .seeds import DEFAULT_GITHUB_REPO_SEEDS


class InjectRepositoryRequest(BaseModel):
    source: Literal["github", "local"]
    owner: str | None = None
    name: str | None = None
    path: str | None = None
    ref: str | None = None
    github_token: str | None = None
    index_now: bool = True


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=25)
    repo_ids: list[str] = Field(default_factory=list)


class RagRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=6, ge=1, le=25)
    repo_ids: list[str] = Field(default_factory=list)


class SeedRepositoriesRequest(BaseModel):
    github_token: str | None = None
    index_now: bool = True


def create_app(root_dir: str | Path | None = None) -> FastAPI:
    service = LibScoutService(Path(root_dir or ".libscout"))
    app = FastAPI(title="LibScout API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/repositories")
    def list_repositories() -> dict[str, object]:
        repositories = [repo.to_dict() for repo in service.list_repositories()]
        return {"repositories": repositories}

    @app.post("/api/repositories/inject")
    def inject_repository(payload: InjectRepositoryRequest) -> dict[str, object]:
        try:
            if payload.source == "github":
                if not payload.owner or not payload.name:
                    raise HTTPException(status_code=400, detail="GitHub injection requires owner and name.")
                repository = service.inject_github_repository(
                    owner=payload.owner,
                    name=payload.name,
                    token=payload.github_token,
                    ref=payload.ref,
                )
            else:
                if not payload.path:
                    raise HTTPException(status_code=400, detail="Local injection requires a path.")
                repository = service.inject_local_repository(
                    path=payload.path,
                    owner=payload.owner,
                    name=payload.name,
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        response: dict[str, object] = {"repository": repository.to_dict()}
        if payload.index_now:
            report = service.index_repository(repository.id)
            response["index_report"] = {
                "repository": report.repository.to_dict(),
                "indexed_files": report.indexed_files,
                "indexed_chunks": report.indexed_chunks,
                "skipped_files": report.skipped_files,
            }
        return response

    @app.post("/api/repositories/seed")
    def seed_repositories(payload: SeedRepositoriesRequest) -> dict[str, object]:
        results = service.inject_github_repositories(
            DEFAULT_GITHUB_REPO_SEEDS,
            token=payload.github_token,
            index_now=payload.index_now,
        )
        serialized: list[dict[str, object]] = []
        for result in results:
            if hasattr(result, "repository"):
                serialized.append(
                    {
                        "repository": result.repository.to_dict(),
                        "indexed_files": result.indexed_files,
                        "indexed_chunks": result.indexed_chunks,
                        "skipped_files": result.skipped_files,
                    }
                )
            else:
                serialized.append({"repository": result.to_dict()})
        return {
            "count": len(results),
            "repositories": serialized,
        }

    @app.post("/api/repositories/{repo_id}/index")
    def index_repository(repo_id: str) -> dict[str, object]:
        try:
            report = service.index_repository(repo_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "repository": report.repository.to_dict(),
            "indexed_files": report.indexed_files,
            "indexed_chunks": report.indexed_chunks,
            "skipped_files": report.skipped_files,
        }

    @app.post("/api/search")
    def search(payload: SearchRequest) -> dict[str, object]:
        hits = service.search(query=payload.query, limit=payload.limit, repo_ids=tuple(payload.repo_ids))
        return {"hits": [hit.__dict__ for hit in hits]}

    @app.post("/api/rag")
    def rag(payload: RagRequest) -> dict[str, object]:
        answer = service.answer(query=payload.query, limit=payload.limit, repo_ids=tuple(payload.repo_ids))
        return {
            "query": answer.query,
            "answer": answer.answer,
            "hits": [hit.__dict__ for hit in answer.hits],
        }

    return app
