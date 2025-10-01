
def rrf(sets: list[list[tuple[str, float]]], k: int = 60, weight: float = 1.0) -> dict[str, float]:
    scores: dict[str, float] = {}
    for result in sets:
        for rank, (doc_id, _score) in enumerate(result, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight * (1.0 / (k + rank))
    return scores
