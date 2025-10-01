
from pathlib import Path
import argparse, json, re
from .ignore_rules import load_ignore_patterns, should_ignore
from .ts_chunker import chunk_by_ast
from .path_tokenizer import tokenize_path
from .api import API
from .embedder import LocalEmbedder

def chunk_id_from(rel_path: str, idx: int) -> str:
    import hashlib; return hashlib.sha256((rel_path + f"#{idx}").encode("utf-8")).hexdigest()[:32]

def main():
    import blake3
    p = argparse.ArgumentParser()
    p.add_argument("root"); p.add_argument("repo_id")
    p.add_argument("--tenant", default="default"); p.add_argument("--server", default="http://localhost:8000")
    p.add_argument("--privacy", action="store_true")
    p.add_argument("--salt", default="auto")
    p.add_argument("--tus", action="store_true"); p.add_argument("--tus-url", default="http://localhost:1080/files/")
    p.add_argument("--context", type=int, default=2)
    p.add_argument("--incremental", action="store_true")
    args = p.parse_args()

    root = Path(args.root).resolve(); spec = load_ignore_patterns(root); api = API(args.server)
    salt_value = (api.get_salt(args.tenant).get("salt") or "dev_salt").encode("utf-8") if args.salt=="auto" else args.salt.encode("utf-8")
    embedder = LocalEmbedder() if args.privacy else None

    tus = None
    if args.tus and not args.privacy:
        try:
            from tusclient import client as tusclient
            tus = tusclient.TusClient(args.tus_url.rstrip("/"))
        except Exception as e:
            print("tus unavailable:", e); tus=None

    state_dir = root/'.codeindex'; state_dir.mkdir(exist_ok=True)
    state_path = state_dir/'state.json'
    old = {}
    if args.incremental and state_path.exists():
        try: old = json.loads(state_path.read_text(encoding='utf-8'))
        except Exception: old = {}

    changed = []
    for path in root.rglob("*"):
        if path.is_file() and not should_ignore(spec, root, path):
            h = blake3.blake3(path.read_bytes()).hexdigest()
            rel = path.relative_to(root).as_posix()
            if args.incremental and old.get(rel)==h:
                continue
            changed.append((path, rel, h))

    upload_batch = []
    for path, rel, h in changed:
        tokens = tokenize_path(Path(rel), salt_value)
        chunks = chunk_by_ast(path, context_lines=args.context)
        for i, ch in enumerate(chunks):
            cid = chunk_id_from(rel, i)
            item = {"tenant_id": args.tenant, "chunk_id": cid, "repo_id": args.repo_id, "lang": path.suffix.lstrip("."),
                    "path_tokens": tokens, "rel_path": rel, "is_test": bool(re.search(r'(?:^|/)(test_|tests/|.*_test\.\w+$)', rel)),
                    "line_start": ch["line_start"], "line_end": ch["line_end"], "privacy_mode": bool(args.privacy)}
            if args.privacy:
                vec = embedder.encode([ch["text"]])[0]; item["vector"] = vec; upload_batch.append(item)
            else:
                if tus is not None:
                    from io import BytesIO
                    uploader = tus.uploader(file_stream=BytesIO(ch["text"].encode("utf-8")), chunk_size=5*1024*1024, retries=3,
                                            metadata={"chunk_id": cid, "repo_id": args.repo_id})
                    uploader.upload(); tus_key = uploader.url.rsplit("/",1)[-1]
                    api.commit_tus(args.tenant, args.repo_id, item, tus_key)
                else:
                    item["text"] = ch["text"]; upload_batch.append(item)

    if upload_batch:
        print("Bulk upload:", len(upload_batch)); print(api.upload(upload_batch))

    if args.incremental:
        new_map = old
        for _, rel, h in changed: new_map[rel]=h
        state_path.write_text(json.dumps(new_map, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == "__main__":
    main()
