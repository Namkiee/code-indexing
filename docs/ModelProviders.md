# Model Provider Abstractions

The search service now uses dependency-injected providers for both embedding and cross-encoder reranking models. This pattern makes it easy to swap model implementations and improves testability.

## Embedding providers

* **Environment variable:** `EMBED_PROVIDER`
* **Default:** `huggingface`
* **Implementation:** `HFEmbeddingProvider` wraps a Hugging Face `SentenceTransformer` model specified by `settings.embed_model`.

When `HybridSearch` needs embeddings, it calls the provider interface instead of constructing a model directly. Implement custom providers by subclassing `EmbeddingProvider` in `server/app/search/providers/embedding.py` and implementing `encode`.

## Reranker providers

* **Environment variable:** `RERANKER_PROVIDER`
* **Default:** `huggingface`
* **Implementation:** `HFCrossEncoderProvider` wraps the Hugging Face `CrossEncoder` referenced by `settings.reranker_model`.

The `/v1/search/fetch-lines` endpoint uses a provider-backed `CrossEncoderReranker`, enabling A/B testing or vendor changes without code edits.

## Adding a new provider

1. Create a subclass of the relevant abstract base class (`EmbeddingProvider` or `CrossEncoderProvider`).
2. Register it in the corresponding `build_*_provider` factory.
3. Set the environment variable to the new provider key.
4. (Optional) Extend the unit tests under `tests/unit/test_providers.py` to cover the new provider.

This design keeps provider wiring in `server/app/main.py` and isolates vendor-specific logic, simplifying configuration-driven model swaps.
