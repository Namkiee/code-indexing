
from pathlib import Path
import pathspec
IGNORE_FILES = [".gitignore", ".cursorignore", ".cursorindexingignore"]
def load_ignore_patterns(root: Path) -> pathspec.PathSpec:
    patterns: list[str] = []
    for name in IGNORE_FILES:
        p = root / name
        if p.exists():
            patterns += p.read_text(encoding="utf-8", errors="ignore").splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
def should_ignore(ps: pathspec.PathSpec, root: Path, p: Path) -> bool:
    rel = p.relative_to(root).as_posix()
    return ps.match_file(rel)
