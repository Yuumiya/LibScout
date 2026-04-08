from __future__ import annotations

from .models import GitHubRepoSeed

DEFAULT_GITHUB_REPO_SEEDS: tuple[GitHubRepoSeed, ...] = (
    GitHubRepoSeed(owner="WeetHet", name="holonomy"),
    GitHubRepoSeed(owner="tiangolo", name="fastapi"),
    GitHubRepoSeed(owner="encode", name="httpx"),
    GitHubRepoSeed(owner="pydantic", name="pydantic"),
    GitHubRepoSeed(owner="Textualize", name="rich"),
    GitHubRepoSeed(owner="fastapi", name="typer"),
)
