
from pydantic import BaseModel
import os

class Settings(BaseModel):
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "code_chunks")
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    opensearch_index: str = os.getenv("OPENSEARCH_INDEX", "code_chunks")
    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-large-en-v1.5")
    reranker_model: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-large")
    top_k_vector: int = int(os.getenv("TOP_K_VECTOR", 50))
    top_k_bm25: int = int(os.getenv("TOP_K_BM25", 50))
    final_k: int = int(os.getenv("FINAL_K", 12))
    alpha_vec: float = float(os.getenv("ALPHA_VEC", 0.6))
    beta_bm25: float = float(os.getenv("BETA_BM25", 0.4))
    rrf_k: int = int(os.getenv("RRF_K", 60))
    learned_ranker_path: str = os.getenv("LEARNED_RANKER_PATH", "")
    privacy_repo_ids: set[str] = set(os.getenv("PRIVACY_REPOS", "").split(",")) if os.getenv("PRIVACY_REPOS") else set()

    def collection_for(self, tenant: str) -> str: return f"{self.qdrant_collection}_{tenant}"
    def index_for(self, tenant: str) -> str: return f"{self.opensearch_index}_{tenant}"

settings = Settings()
