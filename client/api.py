
import requests
class API:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base = base_url.rstrip("/")
    def upload(self, chunks: list[dict]):
        r = requests.post(self.base + "/v1/index/upload", json={"chunks": chunks}); r.raise_for_status(); return r.json()
    def commit_tus(self, tenant_id: str, repo_id: str, chunk: dict, tus_key: str):
        r = requests.post(self.base + "/v1/index/commit_tus", json={"tenant_id": tenant_id, "repo_id": repo_id, "chunk": chunk, "tus_key": tus_key}); r.raise_for_status(); return r.json()
    def get_salt(self, tenant_id: str = "default"):
        r = requests.get(self.base + "/v1/tenant/salt", params={"tenant_id": tenant_id}); r.raise_for_status(); return r.json()
