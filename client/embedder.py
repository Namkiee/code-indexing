
from sentence_transformers import SentenceTransformer
class LocalEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5"):
        self.model = SentenceTransformer(model_name)
    def encode(self, texts: list[str]):
        return self.model.encode(texts, normalize_embeddings=True).tolist()
