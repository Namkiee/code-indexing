
# API
- `POST /v1/index/upload`, `POST /v1/index/commit_tus`
- `POST /v1/search` (필터: lang, dir_hint, exclude_tests; A/B bucket 반환)
- `POST /v1/search/fetch-lines` (Cross-Encoder 재랭킹)
- `POST /v1/feedback`
- `GET /v1/tenant/salt`, `GET /v1/metrics`
- 인증: `x-api-key` (REQUIRE_API_KEY=true 시 필수)
