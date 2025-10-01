
import json
from pathlib import Path

def append_jsonl(path: str, obj: dict):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def iter_jsonl(path: str):
    p = Path(path)
    if not p.exists(): return []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if line:
                try: yield json.loads(line)
                except Exception: continue
