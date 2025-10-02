# Model Provider Abstractions

The search service now uses dependency-injected providers for both embedding and cross-encoder reranking models. This pattern makes it easy to swap model implementations, improves testability, and now offers graceful fallbacks when configuration is incorrect.

## Embedding providers

* **Environment variable:** `EMBED_PROVIDER`
* **Default:** `huggingface`
* **Implementation:** `HFEmbeddingProvider` wraps a Hugging Face `SentenceTransformer` model specified by `settings.embed_model`.

Providers are looked up through a lightweight registry (`register_embedding_provider`) that supports aliases and lazy loading. The Hugging Face models are instantiated only when `encode` is first called, so startup stays fast even if large checkpoints are in use.

If `EMBED_PROVIDER` is unset or references an unknown key, the application falls back to the default Hugging Face provider and emits a warning log indicating the bad value.

## Reranker providers

* **Environment variable:** `RERANKER_PROVIDER`
* **Default:** `huggingface`
* **Implementation:** `HFCrossEncoderProvider` wraps the Hugging Face `CrossEncoder` referenced by `settings.reranker_model`.

Rerankers share the same registry pattern via `register_reranker_provider`, including lazy model instantiation and fallback logging.

## Adding a new provider

1. Create a subclass of the relevant abstract base class (`EmbeddingProvider` or `CrossEncoderProvider`).
2. Register it with a unique key (and optional aliases) using `register_embedding_provider("my-key")` or `register_reranker_provider("my-key")`. Factories receive the configured model name.
3. Set the environment variable to the new provider key.
4. (Optional) Extend the unit tests under `tests/unit/test_providers.py` to cover the new provider.

This design keeps provider wiring in `server/app/main.py`, isolates vendor-specific logic, and ensures the service continues to boot with sensible defaults even when configuration contains typos.
