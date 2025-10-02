"""Embedding provider interfaces and implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Lock
from typing import Callable, Iterable, Sequence, Tuple

from sentence_transformers import SentenceTransformer

from .registry import ProviderRegistry


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

    def __init__(
        self,
        model_name: str,
        loader: Callable[[str], SentenceTransformer] | None = None,
    ) -> None:
        self._model_name = model_name
        self._loader = loader or SentenceTransformer
        self._model: SentenceTransformer | None = None
        self._lock = Lock()

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = self._loader(self._model_name)
        return self._model

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
        model = self._get_model()
        vectors = model.encode(batch, normalize_embeddings=normalize_embeddings)
        if hasattr(vectors, "tolist"):
            return vectors.tolist()
        return list(vectors)


_embedding_registry: ProviderRegistry[EmbeddingProvider] = ProviderRegistry("huggingface")


def register_embedding_provider(
    key: str,
    *,
    aliases: Sequence[str] | None = None,
):
    """Public decorator for registering embedding providers."""

    return _embedding_registry.register(key, aliases=aliases)


@register_embedding_provider(
    "huggingface",
    aliases=("hf", "sentence-transformers"),
)
def _build_hf_embedding_provider(model_name: str) -> EmbeddingProvider:
    return HFEmbeddingProvider(model_name)


def build_embedding_provider(
    provider: str | None,
    model_name: str,
) -> Tuple[EmbeddingProvider, str, str | None]:
    """Factory for embedding providers based on configuration.

    Returns a tuple of ``(provider, resolved_key, fallback_from)`` to allow
    callers to log when a fallback occurs.
    """

    return _embedding_registry.create(provider, model_name)
