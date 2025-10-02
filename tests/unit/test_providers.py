import pathlib
import sys
from typing import Sequence

import pytest

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "server"))

from app.search.providers import embedding as embedding_module
from app.search.providers import reranker as reranker_module
from app.search.providers.embedding import (
    EmbeddingProvider,
    HFEmbeddingProvider,
    build_embedding_provider,
    register_embedding_provider,
)
from app.search.providers.reranker import (
    CrossEncoderProvider,
    HFCrossEncoderProvider,
    build_reranker_provider,
)
from app.search.reranker import CrossEncoderReranker


class DummySentenceTransformer:
    created_models: list[str] = []

    def __init__(self, model_name: str):
        type(self).created_models.append(model_name)
        self.model_name = model_name
        self.calls: list[tuple[list[str], bool]] = []

    def encode(self, texts, normalize_embeddings: bool = True):
        batch = list(texts)
        self.calls.append((batch, normalize_embeddings))
        return [[float(len(text))] for text in batch]


class DummyCrossEncoder:
    created_models: list[str] = []

    def __init__(self, model_name: str):
        type(self).created_models.append(model_name)
        self.model_name = model_name
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs):
        self.calls.append(list(pairs))
        return [float(len(q) + len(p)) for q, p in pairs]


class DummyEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.payloads: list[Sequence[str]] = []

    def encode(self, texts, *, normalize_embeddings: bool = True):
        batch = list(texts if isinstance(texts, (list, tuple)) else [texts])
        self.payloads.append(tuple(batch))
        return [[42.0] for _ in batch]


class DummyProvider(CrossEncoderProvider):
    def __init__(self):
        self.requests: list[tuple[str, tuple[str, ...]]] = []

    def rerank(self, query: str, passages):
        self.requests.append((query, tuple(passages)))
        return [42.0 for _ in passages]


@pytest.fixture(autouse=True)
def reset_dummy_state():
    DummySentenceTransformer.created_models = []
    DummyCrossEncoder.created_models = []
    yield


def test_build_embedding_provider_hf(monkeypatch):
    monkeypatch.setattr(embedding_module, "SentenceTransformer", DummySentenceTransformer)
    provider, resolved_key, fallback_from = build_embedding_provider("huggingface", "dummy-model")

    assert isinstance(provider, HFEmbeddingProvider)
    assert resolved_key == "huggingface"
    assert fallback_from is None
    assert DummySentenceTransformer.created_models == []

    vectors = provider.encode(["hello", "world"], normalize_embeddings=False)

    assert DummySentenceTransformer.created_models == ["dummy-model"]
    assert vectors[0][0] == 5.0
    assert vectors[1][0] == 5.0


def test_build_embedding_provider_fallback(monkeypatch):
    monkeypatch.setattr(embedding_module, "SentenceTransformer", DummySentenceTransformer)
    provider, resolved_key, fallback_from = build_embedding_provider("unsupported", "model")

    assert resolved_key == "huggingface"
    assert fallback_from == "unsupported"
    assert provider.encode("x")[0][0] == 1.0


def test_register_custom_embedding_provider():
    @register_embedding_provider("dummy-test", aliases=("custom",))
    def _factory(model_name: str) -> EmbeddingProvider:  # noqa: ARG001 - contract requires signature
        return DummyEmbeddingProvider()

    provider, resolved_key, fallback_from = build_embedding_provider("custom", "unused")

    assert isinstance(provider, DummyEmbeddingProvider)
    assert resolved_key == "dummy-test"
    assert fallback_from is None
    assert provider.encode(["a"])[0][0] == 42.0


def test_build_reranker_provider_hf(monkeypatch):
    monkeypatch.setattr(reranker_module, "CrossEncoder", DummyCrossEncoder)
    provider, resolved_key, fallback_from = build_reranker_provider("hf", "dummy-cross-encoder")

    assert isinstance(provider, HFCrossEncoderProvider)
    assert resolved_key == "huggingface"
    assert fallback_from is None
    assert DummyCrossEncoder.created_models == []

    scores = provider.rerank("q", ["a", "bb"])

    assert DummyCrossEncoder.created_models == ["dummy-cross-encoder"]
    assert list(scores) == [float(len("q") + 1), float(len("q") + 2)]


def test_reranker_provider_fallback(monkeypatch):
    monkeypatch.setattr(reranker_module, "CrossEncoder", DummyCrossEncoder)
    provider, resolved_key, fallback_from = build_reranker_provider("unknown", "dummy")

    assert resolved_key == "huggingface"
    assert fallback_from == "unknown"
    assert list(provider.rerank("q", ["a"])) == [float(len("q") + 1)]


def test_cross_encoder_reranker_delegates():
    provider = DummyProvider()
    reranker = CrossEncoderReranker(provider=provider)

    scores = reranker.rerank("query", ["p1", "p2"])

    assert scores == [42.0, 42.0]
    assert provider.requests == [("query", ("p1", "p2"))]

    with pytest.raises(ValueError):
        CrossEncoderReranker()
