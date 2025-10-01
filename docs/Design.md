
# Design
- tree-sitter 함수/클래스 청킹 + 헤더 주석/JSDoc/데코레이터 병합
- Qdrant(벡터) + OpenSearch(BM25) 하이브리드, α/β 결합 + RRF + (옵션)학습랭커
- HNSW 튜닝(m=32, ef_construct=128), 동적 EF
- 필터: lang / dir_hint / exclude_tests
- Incremental 인덱싱(blake3), tus 이어올리기
- RBAC(x-api-key), rate-limit, 임베딩/검색 캐시, /v1/metrics, A/B bucket
