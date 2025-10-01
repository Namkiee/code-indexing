
import logging
import time, uuid, threading, json, pathlib, os
from collections import OrderedDict

from fastapi import FastAPI, Request, Header, HTTPException

from app.config import settings
from app.index.opensearch_store import OSStore
from app.index.qdrant_store import QdrantStore
from app.models.schemas import (
    FetchLinesRequest,
    FetchLinesResponse,
    FeedbackRequest,
    FeedbackResponse,
    SearchHit,
    SearchRequest,
    SearchResponse,
    UploadRequest,
)
from app.search.hybrid_search import HybridSearch
from app.search.providers.embedding import build_embedding_provider
from app.search.providers.reranker import build_reranker_provider
from app.search.reranker import CrossEncoderReranker
from app.utils.jsonl import append_jsonl
from app.utils.s3_utils import get_object_text
from app.utils.vault import get_current_salt
from qdrant_client.http.models import PointStruct

logger = logging.getLogger(__name__)

app = FastAPI(title="Hybrid Code Indexing (Advanced)")

embed_provider, embed_provider_key, embed_fallback = build_embedding_provider(
    os.getenv("EMBED_PROVIDER"), settings.embed_model
)
if embed_fallback:
    logger.warning(
        "Unknown embedding provider '%s'; falling back to '%s'",
        embed_fallback,
        embed_provider_key,
    )

qdrant = QdrantStore()
os_store = OSStore()
searcher = HybridSearch(qdrant, os_store, embed_provider)

reranker_provider, reranker_key, reranker_fallback = build_reranker_provider(
    os.getenv("RERANKER_PROVIDER"), settings.reranker_model
)
if reranker_fallback:
    logger.warning(
        "Unknown reranker provider '%s'; falling back to '%s'",
        reranker_fallback,
        reranker_key,
    )
reranker = CrossEncoderReranker(provider=reranker_provider)

# --- RBAC / Rate limit / Cache / Metrics ---
TENANT_KEYS = {}
p = pathlib.Path("/app/server/data/tenants.json")
if p.exists():
    try: TENANT_KEYS = json.loads(p.read_text(encoding="utf-8"))
    except Exception: TENANT_KEYS = {}

REQUIRE_API_KEY = (os.getenv("REQUIRE_API_KEY","false").lower()=="true")
SEARCH_RATE_PER_MIN = int(os.getenv("LIMIT_SEARCH_PER_MINUTE","120"))
EMBED_CACHE_SIZE = int(os.getenv("EMBED_CACHE_SIZE","10000"))
SEARCH_CACHE_TTL_S = int(os.getenv("SEARCH_CACHE_TTL_S","30"))
AB_VARIANT_ALPHA = float(os.getenv("AB_VARIANT_ALPHA", str(settings.alpha_vec)))
AB_VARIANT_BETA  = float(os.getenv("AB_VARIANT_BETA", str(settings.beta_bm25)))

STATS = {"search_total":0, "search_err":0, "feedback_total":0, "index_total":0, "avg_search_ms":0.0}
_stats_lock = threading.Lock()

class EmbedCache:
    def __init__(self, max_size=10000):
        self.max=max_size; self.d=OrderedDict(); self.lock=threading.Lock()
    def get(self, key):
        with self.lock:
            if key in self.d:
                v=self.d.pop(key); self.d[key]=v; return v
            return None
    def put(self, key, val):
        with self.lock:
            if key in self.d: self.d.pop(key)
            self.d[key]=val
            if len(self.d)>self.max: self.d.popitem(last=False)

EMB_CACHE = EmbedCache(EMBED_CACHE_SIZE)

def encode_cached(text: str):
    v = EMB_CACHE.get(text)
    if v is not None: return v
    vec = embed_provider.encode([text], normalize_embeddings=True)[0]
    EMB_CACHE.put(text, vec)
    return vec

_rate = {}
def check_rate(key: str):
    now = int(time.time()//60)
    b = _rate.get(key)
    if not b or b["minute"]!=now: b={"minute":now,"count":0}; _rate[key]=b
    b["count"] += 1
    if b["count"] > SEARCH_RATE_PER_MIN: raise HTTPException(429, "rate limit exceeded")

def require_key(tenant_id: str, api_key: str | None):
    if not REQUIRE_API_KEY: return
    if not api_key: raise HTTPException(401, "missing x-api-key")
    allowed = set(TENANT_KEYS.get(tenant_id, []))
    if api_key not in allowed: raise HTTPException(403, "invalid api key")

_search_cache = {}
def get_cache(key):
    v=_search_cache.get(key)
    if not v: return None
    if (time.time()-v["t"])>SEARCH_CACHE_TTL_S: _search_cache.pop(key,None); return None
    return v["hits"]
def set_cache(key, hits): _search_cache[key]={"t":time.time(),"hits":hits}

@app.get("/v1/tenant/salt")
async def get_tenant_salt(tenant_id: str = "default"):
    s = get_current_salt(tenant_id)
    if not s: return {"tenant_id": tenant_id, "salt_ver": 0, "salt": ""}
    return {"tenant_id": tenant_id, "salt_ver": s.get("ver", 0), "salt": s.get("value","")}

@app.post("/v1/index/upload")
async def upload(req: UploadRequest, x_api_key: str | None = Header(default=None)):
    require_key(req.chunks[0].tenant_id if req.chunks else "default", x_api_key)
    points = []; os_docs = []
    tenant = req.chunks[0].tenant_id if req.chunks else "default"
    for c in req.chunks:
        payload = {"chunk_id": c.chunk_id, "repo_id": c.repo_id, "path_tokens": c.path_tokens,
                   "line_start": c.line_start, "line_end": c.line_end, "lang": c.lang}
        if c.rel_path is not None: payload["rel_path"] = c.rel_path
        if c.privacy_mode:
            assert c.vector is not None, "privacy_mode=True면 vector 필요"
            vec = c.vector
        else:
            assert c.text is not None, "privacy_mode=False면 text 필요"
            vec = encode_cached(c.text)
            if (c.repo_id not in settings.privacy_repo_ids):
                os_docs.append({"chunk_id": c.chunk_id, "repo_id": c.repo_id, "path_tokens": c.path_tokens,
                                "rel_path": c.rel_path or "", "lang": c.lang,
                                "line_start": c.line_start, "line_end": c.line_end, "text": c.text})
        points.append(PointStruct(id=c.chunk_id, vector=vec, payload=payload))

    if points: qdrant.upsert_tenant(tenant, points)
    if os_docs: os_store.bulk_upsert_tenant(tenant, os_docs)
    with _stats_lock: STATS["index_total"] += len(req.chunks)
    return {"status":"ok","qdrant":len(points),"opensearch":len(os_docs)}

@app.post("/v1/index/commit_tus")
async def commit_tus(body: dict, x_api_key: str | None = Header(default=None)):
    tenant_id = body.get("tenant_id","default")
    require_key(tenant_id, x_api_key)
    repo_id = body.get("repo_id"); chunk = body.get("chunk",{}); tus_key = body.get("tus_key")
    assert repo_id and chunk and tus_key, "invalid payload"
    key = f"uploads/{tus_key}"
    text = get_object_text(key)
    vec = encode_cached(text)
    payload = {"chunk_id": chunk["chunk_id"], "repo_id": repo_id, "path_tokens": chunk["path_tokens"],
               "line_start": chunk.get("line_start",1), "line_end": chunk.get("line_end",1), "lang": chunk.get("lang")}
    if chunk.get("rel_path"): payload["rel_path"] = chunk["rel_path"]
    qdrant.upsert_tenant(tenant_id, [PointStruct(id=chunk["chunk_id"], vector=vec, payload=payload)])
    if repo_id not in settings.privacy_repo_ids:
        os_store.bulk_upsert_tenant(tenant_id, [{"chunk_id": chunk["chunk_id"], "repo_id": repo_id, "path_tokens": chunk["path_tokens"],
                                                 "rel_path": payload.get("rel_path",""), "lang": payload.get("lang"),
                                                 "line_start": payload["line_start"], "line_end": payload["line_end"], "text": text}])
    return {"status":"ok","chunk_id":chunk["chunk_id"]}

@app.post("/v1/search", response_model=SearchResponse)
async def search(req: SearchRequest, request: Request, x_api_key: str | None = Header(default=None)):
    require_key(req.tenant_id, x_api_key); key = x_api_key or request.client.host
    # Rate limit
    now_min = int(time.time()//60)
    ipkey = f"{key}:{now_min}"; 
    # reuse check_rate via simple inline
    hit = getattr(search, "_rate", {}); cnt = hit.get(ipkey,0)+1
    if cnt > int(os.getenv("LIMIT_SEARCH_PER_MINUTE","120")): raise HTTPException(429, "rate limit exceeded")
    hit[ipkey]=cnt; setattr(search, "_rate", hit)

    t0 = time.time()
    cache_key=(req.tenant_id, req.repo_id, req.query, req.lang, req.dir_hint, req.exclude_tests, req.top_k)
    cached = getattr(search, "_cache", {}).get(cache_key)
    if cached and (time.time()-cached["t"])<=int(os.getenv("SEARCH_CACHE_TTL_S","30")):
        hits = cached["hits"]; debug=[]
    else:
        # A/B bucket
        sid = uuid.uuid4().hex[:16]
        bucket = 'control' if int(sid[-1],16)%2==0 else 'variant'
        # override alpha/beta for variant
        orig = (searcher.alpha, searcher.beta)
        if bucket == 'variant':
            searcher.alpha, searcher.beta = float(os.getenv("AB_VARIANT_ALPHA", searcher.alpha)), float(os.getenv("AB_VARIANT_BETA", searcher.beta))
        hits, debug = searcher.search_with_debug(tenant_id=req.tenant_id, repo_id=req.repo_id, query=req.query, top_k=req.top_k,
                                                 filters={"lang": req.lang, "dir_hint": req.dir_hint, "exclude_tests": req.exclude_tests})
        searcher.alpha, searcher.beta = orig
        setattr(search, "_last_bucket", bucket)
        setattr(search, "_last_sid", sid)
        # store to cache
        c = getattr(search, "_cache", {}); c[cache_key]={"t": time.time(), "hits": hits}; setattr(search, "_cache", c)

    need_fetch = (req.repo_id in settings.privacy_repo_ids)
    sid = getattr(search, "_last_sid", uuid.uuid4().hex[:16])
    bucket = getattr(search, "_last_bucket", "control")
    append_jsonl("/app/server/data/search_log.jsonl", {"search_id": sid, "tenant_id": req.tenant_id, "repo_id": req.repo_id,
                                                       "query": req.query, "timestamp": time.time(), "candidates": debug, "bucket": bucket})
    with _stats_lock:
        STATS["search_total"] += 1
        STATS["avg_search_ms"] = (STATS["avg_search_ms"]*0.99 + (time.time()-t0)*1000*0.01)
    return SearchResponse(search_id=sid, bucket=bucket, need_fetch_lines=need_fetch, hits=[SearchHit(**h) for h in hits])

@app.post("/v1/search/fetch-lines", response_model=FetchLinesResponse)
async def fetch_lines(req: FetchLinesRequest, x_api_key: str | None = Header(default=None)):
    require_key(req.tenant_id, x_api_key)
    passages = [it.raw_lines for it in req.items]
    scores = reranker.rerank(req.query, passages)
    pairs = sorted(zip(req.items, scores), key=lambda x: x[1], reverse=True)[:req.top_k]
    hits = [SearchHit(chunk_id=it.chunk_id, score=float(sc), path_tokens=[], line_span=[0,0], repo_id=req.repo_id, preview=None)
            for it, sc in pairs]
    return FetchLinesResponse(hits=hits)

@app.post("/v1/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest, x_api_key: str | None = Header(default=None)):
    append_jsonl("/app/server/data/feedback_log.jsonl", {"search_id": req.search_id, "clicked_chunk_id": req.clicked_chunk_id,
                                                         "grade": int(req.grade), "timestamp": time.time()})
    with _stats_lock: STATS["feedback_total"] += 1
    return FeedbackResponse(status="ok")

@app.get("/v1/metrics")
async def metrics(): return STATS
