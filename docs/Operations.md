# Operations

## Environment variables
- ALPHA_VEC, BETA_BM25, RRF_K, TOP_K_VECTOR/BM25/FINAL_K,
  EMBED_MODEL, RERANKER_MODEL, LEARNED_RANKER_PATH,
  REQUIRE_API_KEY, LIMIT_SEARCH_PER_MINUTE, EMBED_CACHE_SIZE, SEARCH_CACHE_TTL_S,
  AB_VARIANT_ALPHA, AB_VARIANT_BETA,
  QDRANT_*, OPENSEARCH_*, S3_*, VAULT_*

## Logging and observability
- Application logs are emitted as structured JSON. See [Logging & Request Tracing](./Logging.md)
  for the schema and usage guidelines.
- Request-scoped identifiers are returned to clients via the `X-Request-ID` header and are
  automatically included in log entries.
- Search level traces are still recorded in `server/data/search_log.jsonl` and feedback in
  `server/data/feedback_log.jsonl` for downstream analytics.
