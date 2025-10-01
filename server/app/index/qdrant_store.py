
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, Distance, VectorParams

from app.config import settings

class QdrantStore:
    def __init__(self, client: Optional[QdrantClient] = None):
        self.client = client or QdrantClient(url=settings.qdrant_url)

    def ensure_collection(self, tenant: str, size: int = 1024):
        coll = settings.collection_for(tenant)
        try:
            self.client.get_collection(coll)
        except Exception:
            self.client.recreate_collection(
                collection_name=coll,
                vectors_config=VectorParams(size=size, distance=Distance.COSINE),
                hnsw_config={"m": 32, "ef_construct": 128}
            )
        return coll

    def upsert_tenant(self, tenant: str, points):
        coll = self.ensure_collection(tenant)
        return self.client.upsert(collection_name=coll, points=list(points))

    def search_tenant(self, tenant: str, vector, repo_id: str, top_k: int,
                      lang: str | None = None, dir_hint: str | None = None, exclude_tests: bool = False, hnsw_ef: int | None = None):
        coll = settings.collection_for(tenant)
        flt = {"must":[{"key":"repo_id","match":{"value":repo_id}}]}
        if lang: flt["must"].append({"key":"lang","match":{"value":lang}})
        if dir_hint: flt["must"].append({"key":"rel_path","match":{"text":dir_hint}})
        if exclude_tests: flt.setdefault("must_not", []).append({"key":"rel_path","match":{"text":"test"}})
        params = {"hnsw_ef": hnsw_ef} if hnsw_ef else None
        return self.client.search(collection_name=coll, query_vector=vector, limit=top_k, query_filter=flt, search_params=params)
