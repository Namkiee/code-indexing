
import os, joblib, numpy as np
from typing import List

class LearnedRanker:
    def __init__(self, path: str):
        self.model = joblib.load(path) if path and os.path.exists(path) else None

    def available(self) -> bool: return self.model is not None

    def score(self, features: List[List[float]]) -> List[float]:
        assert self.model is not None, "Learned ranker not loaded"
        X = np.array(features, dtype=float)
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)[:,1].tolist()
        return self.model.predict(X).tolist()
