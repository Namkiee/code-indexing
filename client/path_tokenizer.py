
import hmac, hashlib, base64
from pathlib import Path
def tokenize_path(path: Path, repo_salt: bytes) -> list[str]:
    segs = path.as_posix().split("/")
    tokens = []
    for s in segs:
        d = hmac.new(repo_salt, s.encode("utf-8"), hashlib.sha256).digest()
        tokens.append(base64.b32encode(d[:10]).decode("ascii").rstrip("="))
    return tokens
