from __future__ import annotations

from .api import create_app
from .embeddings import HashedEmbeddingModel
from .models import GitHubRepoSeed, IndexReport, InjectedRepository, RagAnswer, SearchHit
from .seeds import DEFAULT_GITHUB_REPO_SEEDS
from .service import LibScoutService

__all__: list[str] = [
    "DEFAULT_GITHUB_REPO_SEEDS",
    "GitHubRepoSeed",
    "HashedEmbeddingModel",
    "IndexReport",
    "InjectedRepository",
    "LibScoutService",
    "RagAnswer",
    "SearchHit",
    "create_app",
]

__version__ = "0.1.0"
