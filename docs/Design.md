
# Design
- tree-sitter 함수/클래스 청킹 + 헤더 주석/JSDoc/데코레이터 병합
- Qdrant(벡터) + OpenSearch(BM25) 하이브리드, α/β 결합 + RRF + (옵션)학습랭커
- HNSW 튜닝(m=32, ef_construct=128), 동적 EF
- 필터: lang / dir_hint / exclude_tests
- Incremental 인덱싱(blake3), tus 이어올리기
- RBAC(x-api-key), rate-limit, 임베딩/검색 캐시, /v1/metrics, A/B bucket
- FastAPI 진입점은 `app.api` 패키지의 라우터와 `app.services` 계층으로 모듈화되어 있으며, 라우터는 `AppContext`를 통해 캐시·레이트리밋·검색기 등을 주입 받아 테스트와 향후 Redis 교체가 용이하다.
