
# Quickstart

```bash
docker-compose up -d

export PYTHONPATH=server
python server/scripts/init_qdrant.py
python server/scripts/init_opensearch.py

uvicorn server.app.main:app --reload --port 8000
```

### 인덱싱
```bash
# privacy OFF
python -m client.cli_index ./myrepo myrepo --tenant default
# privacy ON
python -m client.cli_index ./myrepo myrepo --tenant default --privacy --salt mysecretsalt
# tus
python -m client.cli_index ./myrepo myrepo --tenant default --tus --tus-url http://localhost:1080/files/
# incremental
python -m client.cli_index ./myrepo myrepo --tenant default --incremental
```

### 검색
```bash
curl -s http://localhost:8000/v1/search -H "Content-Type: application/json" -H "x-api-key: dev-api-key" -d '{
  "tenant_id": "default",
  "repo_id": "myrepo",
  "query": "http handler",
  "lang": "py",
  "exclude_tests": true,
  "top_k": 12
}' | jq
```
