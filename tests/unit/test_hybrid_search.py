import pathlib
import sys
from typing import Any, Iterable

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "server"))

from app.search.hybrid_search import HybridSearch  # noqa: E402


class DummyRanker:
    def __init__(self, *_: Any, **__: Any) -> None:
        self._available = False

    def available(self) -> bool:
        return False

    def score(self, _: Iterable[Iterable[float]]):  # pragma: no cover - not used in test
        raise AssertionError("score should not be called when ranker unavailable")


class DummyEmbedder:
    def encode(self, texts, normalize_embeddings: bool = True):  # noqa: D401 - simple stub
        return [[1.0] for _ in texts]


class DummyHit:
    def __init__(self, chunk_id: str, score: float, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.score = score


class DummyQdrant:
    def search_tenant(self, *_: Any, **__: Any):
        return [
            DummyHit(
                "chunk-a",
                0.8,
                {
                    "chunk_id": "chunk-a",
                    "repo_id": "repo",
                    "path_tokens": ["src"],
                    "line_start": 1,
                    "line_end": 5,
                },
            ),
            DummyHit(
                "chunk-b",
                0.2,
                {
                    "chunk_id": "chunk-b",
                    "repo_id": "repo",
                    "path_tokens": ["src"],
                    "line_start": 10,
                    "line_end": 15,
                },
            ),
        ]


class DummyOS:
    def bm25_tenant(self, *_: Any, **__: Any):
        return [
            {
                "chunk_id": "chunk-b",
                "repo_id": "repo",
                "path_tokens": ["src"],
                "rel_path": "src/file.py",
                "line_start": 10,
                "line_end": 15,
                "text": "body",
                "score": 2.0,
            }
        ]


def test_hybrid_search_uses_override_weights(monkeypatch):
    monkeypatch.setattr("app.search.hybrid_search.LearnedRanker", DummyRanker)

    searcher = HybridSearch(DummyQdrant(), DummyOS(), DummyEmbedder())
    original_alpha = searcher.alpha
    original_beta = searcher.beta

    hits_default, _ = searcher.search_with_debug("tenant", "repo", "query", top_k=2)
    assert searcher.alpha == original_alpha
    assert searcher.beta == original_beta
    assert hits_default[0]["chunk_id"] == "chunk-a"

    hits_variant, _ = searcher.search_with_debug(
        "tenant",
        "repo",
        "query",
        top_k=2,
        alpha=0.1,
        beta=0.9,
    )

    assert searcher.alpha == original_alpha
    assert searcher.beta == original_beta
    assert hits_variant[0]["chunk_id"] == "chunk-b"
    assert hits_variant[0]["score"] == pytest.approx(0.9)
