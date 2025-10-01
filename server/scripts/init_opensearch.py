
from opensearchpy import OpenSearch
from app.config import settings

os_client = OpenSearch(settings.opensearch_url)
index = settings.opensearch_index
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
  "mappings": {"properties":{
      "repo_id":{"type":"keyword"},
      "chunk_id":{"type":"keyword"},
      "path_tokens":{"type":"keyword"},
      "rel_path":{"type":"text","analyzer":"path_analyzer","fields":{"keyword":{"type":"keyword"}}},
      "lang":{"type":"keyword"},
      "line_start":{"type":"integer"},
      "line_end":{"type":"integer"},
      "text":{"type":"text","analyzer":"code_text","search_analyzer":"standard"}
  }}
}
if os_client.indices.exists(index=index): os_client.indices.delete(index=index)
os_client.indices.create(index=index, body=mapping)
print("OpenSearch base index ready")
