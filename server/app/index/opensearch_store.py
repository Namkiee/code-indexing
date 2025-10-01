
from opensearchpy import OpenSearch, helpers
from app.config import settings

class OSStore:
    def __init__(self, client: OpenSearch | None = None):
        self.client = client or OpenSearch(settings.opensearch_url)

    def ensure_index(self, tenant: str):
        idx = settings.index_for(tenant)
        if self.client.indices.exists(index=idx):
            return idx
        mapping = {
          "settings": {
            "index":{"number_of_shards":1,"number_of_replicas":0},
            "analysis": {
              "analyzer": {
                "code_text": {"type":"custom","tokenizer":"standard","filter":["lowercase","word_delimiter_graph","asciifolding","edge_2_20"]},
                "path_analyzer": {"type":"custom","tokenizer":"path_hierarchy","filter":["lowercase"]}
              },
              "filter": {"edge_2_20":{"type":"edge_ngram","min_gram":2,"max_gram":20}}
            }
          },
          "mappings": {
            "properties":{
              "repo_id":{"type":"keyword"},
              "chunk_id":{"type":"keyword"},
              "path_tokens":{"type":"keyword"},
              "rel_path":{"type":"text","analyzer":"path_analyzer","fields":{"keyword":{"type":"keyword"}}},
              "lang":{"type":"keyword"},
              "line_start":{"type":"integer"},
              "line_end":{"type":"integer"},
              "text":{"type":"text","analyzer":"code_text","search_analyzer":"standard"}
            }
          }
        }
        self.client.indices.create(index=idx, body=mapping)
        return idx

    def bulk_upsert_tenant(self, tenant: str, docs: list[dict]):
        idx = self.ensure_index(tenant)
        actions = [{"_op_type":"index","_index":idx,"_id":d["chunk_id"],"_source":d} for d in docs]
        helpers.bulk(self.client, actions)

    def bm25_tenant(self, tenant: str, repo_id: str, query: str, top_k: int, lang: str | None = None, dir_hint: str | None = None, exclude_tests: bool = False):
        idx = settings.index_for(tenant)
        filters = [{"term":{"repo_id.keyword": repo_id}}]
        if lang: filters.append({"term":{"lang": lang}})
        if dir_hint: filters.append({"prefix":{"rel_path": dir_hint}})
        must_not = [{"wildcard":{"rel_path":"*test*"}}] if exclude_tests else []
        body = {
            "size": top_k,
            "query": {"bool":{"must":[{"match":{"text":query}}],"filter":filters,"must_not":must_not}},
            "_source": ["chunk_id","path_tokens","rel_path","line_start","line_end","repo_id","text"]
        }
        resp = self.client.search(index=idx, body=body)
        hits = []
        for h in resp["hits"]["hits"]:
            s = h["_source"]; s["score"] = h["_score"]; hits.append(s)
        return hits
