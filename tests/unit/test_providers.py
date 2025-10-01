import pathlib
import sys

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "server"))

from app.search.providers import embedding as embedding_module
from app.search.providers import reranker as reranker_module
from app.search.providers.embedding import EmbeddingProvider, build_embedding_provider
from app.search.providers.reranker import (
    CrossEncoderProvider,
    build_reranker_provider,
)
from app.search.reranker import CrossEncoderReranker


class DummySentenceTransformer:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.calls: list[tuple[list[str], bool]] = []

    def encode(self, texts, normalize_embeddings: bool = True):
        batch = list(texts)
        self.calls.append((batch, normalize_embeddings))
        return [[float(len(text))] for text in batch]


class DummyCrossEncoder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs):
        self.calls.append(list(pairs))
        return [float(len(q) + len(p)) for q, p in pairs]


class DummyProvider(CrossEncoderProvider):
    def __init__(self):
        self.requests: list[tuple[str, tuple[str, ...]]] = []

    def rerank(self, query: str, passages):
        self.requests.append((query, tuple(passages)))
        return [42.0 for _ in passages]


def test_build_embedding_provider_hf(monkeypatch):
    monkeypatch.setattr(embedding_module, "SentenceTransformer", DummySentenceTransformer)
    provider = build_embedding_provider("huggingface", "dummy-model")

    vectors = provider.encode(["hello", "world"], normalize_embeddings=False)

    assert isinstance(provider, EmbeddingProvider)
    assert vectors[0][0] == 5.0
    assert vectors[1][0] == 5.0


def test_build_embedding_provider_unsupported():
    with pytest.raises(ValueError):
        build_embedding_provider("unsupported", "model")


def test_build_reranker_provider_hf(monkeypatch):
    monkeypatch.setattr(reranker_module, "CrossEncoder", DummyCrossEncoder)
    provider = build_reranker_provider("hf", "dummy-cross-encoder")

    scores = provider.rerank("q", ["a", "bb"])

    assert list(scores) == [float(len("q") + 1), float(len("q") + 2)]


def test_cross_encoder_reranker_delegates(monkeypatch):
    provider = DummyProvider()
    reranker = CrossEncoderReranker(provider=provider)

    scores = reranker.rerank("query", ["p1", "p2"])

    assert scores == [42.0, 42.0]
    assert provider.requests == [("query", ("p1", "p2"))]

    with pytest.raises(ValueError):
        CrossEncoderReranker()
