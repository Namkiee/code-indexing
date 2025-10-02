"""Cross-encoder reranker provider interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Lock
from typing import Callable, Sequence, Tuple

from sentence_transformers import CrossEncoder

from .registry import ProviderRegistry


class CrossEncoderProvider(ABC):
    """Abstract base class for cross-encoder rerankers."""

    @abstractmethod
    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float]:
        """Return scores for the given passages."""


class HFCrossEncoderProvider(CrossEncoderProvider):
    """Cross-encoder provider backed by Hugging Face models."""

    def __init__(
        self,
        model_name: str,
        loader: Callable[[str], CrossEncoder] | None = None,
    ) -> None:
        self._model_name = model_name
        self._loader = loader or CrossEncoder
        self._model: CrossEncoder | None = None
        self._lock = Lock()

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = self._loader(self._model_name)
        return self._model

    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float]:
        pairs = [(query, passage) for passage in passages]
        model = self._get_model()
        scores = model.predict(pairs)
        if hasattr(scores, "tolist"):
            return scores.tolist()
        return list(scores)


_reranker_registry: ProviderRegistry[CrossEncoderProvider] = ProviderRegistry("huggingface")


def register_reranker_provider(
    key: str,
    *,
    aliases: Sequence[str] | None = None,
):
    """Public decorator for registering reranker providers."""

    return _reranker_registry.register(key, aliases=aliases)


@register_reranker_provider(
    "huggingface",
    aliases=("hf", "cross-encoder"),
)
def _build_hf_reranker_provider(model_name: str) -> CrossEncoderProvider:
    return HFCrossEncoderProvider(model_name)


def build_reranker_provider(
    provider: str | None,
    model_name: str,
) -> Tuple[CrossEncoderProvider, str, str | None]:
    """Factory for reranker providers.

    Returns a tuple of ``(provider, resolved_key, fallback_from)``.
    """

    return _reranker_registry.create(provider, model_name)
