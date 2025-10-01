
from app.index.qdrant_store import QdrantStore
from app.index.opensearch_store import OSStore
from app.index.rrf import rrf
from app.search.learned_ranker import LearnedRanker
from app.config import settings
import numpy as np

class HybridSearch:
    def __init__(self, qdrant: QdrantStore, os_store: OSStore, embedder):
        self.qdrant = qdrant
        self.os = os_store
        self.embedder = embedder
        self.alpha = settings.alpha_vec
        self.beta = settings.beta_bm25
        self.rrf_k = settings.rrf_k
        self.rankerm = LearnedRanker(settings.learned_ranker_path)

    def _normalize(self, scores):
        if not scores: return []
        arr = np.array(scores, dtype=float)
        lo, hi = float(arr.min()), float(arr.max())
        if hi - lo < 1e-9: return [0.5 for _ in scores]
        return ((arr - lo) / (hi - lo)).tolist()

    def search_with_debug(self, tenant_id: str, repo_id: str, query: str, top_k: int | None = None, filters: dict | None = None):
        top_k = top_k or settings.final_k
        qvec = self.embedder.encode([query], normalize_embeddings=True)[0]
        lang = (filters or {}).get('lang')
        dir_hint = (filters or {}).get('dir_hint')
        exclude_tests = bool((filters or {}).get('exclude_tests'))
        hnsw_ef = max(64, int((settings.top_k_vector or 50)*2))

        v_hits = self.qdrant.search_tenant(tenant_id, qvec, repo_id=repo_id, top_k=settings.top_k_vector,
                                           lang=lang, dir_hint=dir_hint, exclude_tests=exclude_tests, hnsw_ef=hnsw_ef)
        v_pairs = []; v_map = {}
        for h in v_hits:
            cid = h.payload["chunk_id"]
            v_pairs.append((cid, float(h.score)))
            v_map[cid] = h.payload

        b_pairs = []; b_map = {}
        if repo_id not in settings.privacy_repo_ids:
            b_hits = self.os.bm25_tenant(tenant_id, repo_id, query, settings.top_k_bm25, lang=lang, dir_hint=dir_hint, exclude_tests=exclude_tests)
            for h in b_hits:
                b_pairs.append((h["chunk_id"], float(h["score"])))
                b_map[h["chunk_id"]] = h

        ids = set([cid for cid,_ in v_pairs] + [cid for cid,_ in b_pairs])
        vdict = {cid:score for cid,score in v_pairs}
        bdict = {cid:score for cid,score in b_pairs}
        id_list = list(ids)
        vnorm = self._normalize([vdict.get(cid, 0.0) for cid in id_list])
        bnorm = self._normalize([bdict.get(cid, 0.0) for cid in id_list])
        fused = {cid: self.alpha*vnorm[i] + self.beta*bnorm[i] for i,cid in enumerate(id_list)}
        if not fused:
            fused = dict(rrf([v_pairs, b_pairs])) if b_pairs else dict(rrf([v_pairs]))

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:max(top_k, 30)]
        hits = []; passages = []; debug = []
        for cid, _ in ranked:
            data = b_map.get(cid) or v_map.get(cid)
            span = max(0, int(data.get("line_end",0)) - int(data.get("line_start",0)))
            depth = len(data.get("path_tokens",[]) or [])
            hits.append((cid, fused[cid], data))
            passages.append((b_map.get(cid) or {}).get("text",""))
            i = id_list.index(cid) if cid in id_list else 0
            vn = vnorm[i] if i < len(vnorm) else 0.0
            bn = bnorm[i] if i < len(bnorm) else 0.0
            debug.append({"chunk_id": cid, "fused": float(fused[cid]), "vnorm": float(vn), "bnorm": float(bn), "span": int(span), "depth": int(depth)})

        if self.rankerm.available() and any(passages):
            feats = [[d["fused"], d["vnorm"], d["bnorm"], d["span"], d["depth"]] for d in debug]
            lr_scores = self.rankerm.score(feats)
            order = sorted(range(len(hits)), key=lambda i: lr_scores[i], reverse=True)[:top_k]
            final = []
            for i in order:
                cid, s, data = hits[i]
                final.append({"chunk_id": cid, "score": float(lr_scores[i]), "path_tokens": data.get("path_tokens", []),
                              "line_span": [data.get("line_start",0), data.get("line_end",0)], "repo_id": data.get("repo_id",""),
                              "preview": data.get("text")})
            return final, debug

        final = []
        for cid, _ in ranked[:top_k]:
            data = b_map.get(cid) or v_map.get(cid)
            final.append({"chunk_id": cid, "score": fused[cid], "path_tokens": data.get("path_tokens", []),
                          "line_span": [data.get("line_start",0), data.get("line_end",0)], "repo_id": data.get("repo_id",""),
                          "preview": data.get("text")})
        return final, debug
