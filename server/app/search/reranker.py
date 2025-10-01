
from typing import List
from sentence_transformers import CrossEncoder

class CrossEncoderReranker:
    def __init__(self, model_name: str):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, passages: List[str]) -> list[float]:
        pairs = [(query, p) for p in passages]
        return self.model.predict(pairs).tolist()
