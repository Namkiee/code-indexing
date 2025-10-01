
# Hybrid Ranking
- `fused = α * vector_norm + β * bm25_norm` (기본 α=0.6, β=0.4)
- 후보 희소 시 RRF 보완
- 학습 랭커(LogReg 예시)로 최종 정렬 대체 가능
- Qdrant HNSW: m=32, ef_construct=128 / 검색 시 ef≈2*TOP_K_VECTOR
