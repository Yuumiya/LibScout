from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


@dataclass(frozen=True)
class HashedEmbeddingModel:
    dimension: int = 256

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:2], "big") % self.dimension
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            weight = 1.0 + min(len(token), 24) / 24.0
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def embed_chunk(
        self,
        *,
        repo_name: str,
        path: str,
        language: str,
        node_type: str,
        cst_path: str,
        text: str,
    ) -> list[float]:
        payload = "\n".join(
            [
                repo_name,
                path,
                language,
                node_type,
                cst_path,
                text,
            ]
        )
        return self.embed_text(payload)
