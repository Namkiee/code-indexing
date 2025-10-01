
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from app.config import settings

client = QdrantClient(url=settings.qdrant_url)
client.recreate_collection(collection_name=settings.qdrant_collection, vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
print("Qdrant base collection ready")
