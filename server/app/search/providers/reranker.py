"""Cross-encoder reranker provider interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from sentence_transformers import CrossEncoder


class CrossEncoderProvider(ABC):
    """Abstract base class for cross-encoder rerankers."""

    @abstractmethod
    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float]:
        """Return scores for the given passages."""


class HFCrossEncoderProvider(CrossEncoderProvider):
    """Cross-encoder provider backed by Hugging Face models."""

    def __init__(self, model_name: str):
        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, passages: Sequence[str]) -> Sequence[float]:
        pairs = [(query, passage) for passage in passages]
        scores = self._model.predict(pairs)
        if hasattr(scores, "tolist"):
            return scores.tolist()
        return list(scores)


def build_reranker_provider(provider: str | None, model_name: str) -> CrossEncoderProvider:
    """Factory for reranker providers."""

    provider_key = (provider or "huggingface").strip().lower()
    if provider_key in {"hf", "huggingface", "cross-encoder"}:
        return HFCrossEncoderProvider(model_name)
    raise ValueError(f"Unsupported reranker provider: {provider}")
