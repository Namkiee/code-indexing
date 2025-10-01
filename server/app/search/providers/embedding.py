"""Embedding provider interfaces and implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Sequence

from sentence_transformers import SentenceTransformer


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def encode(
        self,
        texts: Sequence[str] | str,
        *,
        normalize_embeddings: bool = True,
    ) -> Sequence[Sequence[float]]:
        """Return embeddings for the given text or texts."""


class HFEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by Hugging Face SentenceTransformers."""

    def __init__(self, model_name: str):
        self._model = SentenceTransformer(model_name)

    def encode(
        self,
        texts: Sequence[str] | str,
        *,
        normalize_embeddings: bool = True,
    ) -> Sequence[Sequence[float]]:
        if isinstance(texts, str):
            batch: Iterable[str] = [texts]
        else:
            batch = texts
        vectors = self._model.encode(batch, normalize_embeddings=normalize_embeddings)
        if hasattr(vectors, "tolist"):
            return vectors.tolist()
        return list(vectors)


def build_embedding_provider(provider: str | None, model_name: str) -> EmbeddingProvider:
    """Factory for embedding providers based on configuration."""

    provider_key = (provider or "huggingface").strip().lower()
    if provider_key in {"hf", "huggingface", "sentence-transformers"}:
        return HFEmbeddingProvider(model_name)
    raise ValueError(f"Unsupported embedding provider: {provider}")
