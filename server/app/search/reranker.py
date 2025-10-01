
from typing import List

from app.search.providers.reranker import CrossEncoderProvider, HFCrossEncoderProvider

class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str | None = None,
        provider: CrossEncoderProvider | None = None,
    ):
        if provider is None and model_name is None:
            raise ValueError("Either model_name or provider must be provided")
        self.provider = provider or HFCrossEncoderProvider(model_name)

    def rerank(self, query: str, passages: List[str]) -> list[float]:
        scores = self.provider.rerank(query, passages)
        return list(scores)
