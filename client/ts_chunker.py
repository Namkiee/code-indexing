
from tree_sitter import Parser
from tree_sitter_languages import get_language
from pathlib import Path

LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "tsx",
    ".go": "go", ".java": "java", ".rs": "rust", ".cpp": "cpp", ".c": "c",
    ".cs": "c_sharp", ".php": "php", ".rb": "ruby",
}

NODE_TYPES = {
    "python": ["function_definition", "class_definition"],
    "javascript": ["function_declaration", "method_definition", "class_declaration"],
    "typescript": ["function_declaration", "method_signature", "class_declaration", "method_definition"],
    "tsx": ["function_declaration", "method_definition", "class_declaration"],
    "go": ["function_declaration", "method_declaration", "type_declaration"],
    "java": ["method_declaration", "class_declaration"],
    "rust": ["function_item", "impl_item", "struct_item"],
    "cpp": ["function_definition", "class_specifier"],
    "c": ["function_definition"],
    "c_sharp": ["method_declaration", "class_declaration"],
    "php": ["function_definition", "class_declaration", "method_declaration"],
    "ruby": ["method", "class"],
}

def _merge_header_comments(full_lines: list[str], start_line: int, lang_name: str) -> int:
    i = start_line - 2  # line above node (0-based)
    def is_py_header(line:str): return line.strip().startswith(('@','#')) or line.strip()==''
    def is_js_header(line:str):
        ls=line.strip(); return ls.startswith(('/**','*','//')) or ls==''
    check = is_py_header if lang_name=="python" else is_js_header
    opened_block=False
    while i >= 0:
        line = full_lines[i]
        if lang_name!="python":
            if "*/" in line: opened_block=True
            if "/**" in line or line.strip().startswith(("//","*")) or opened_block or line.strip()=="":
                i -= 1; 
                if "/**" in line: opened_block=False
                continue
            else: break
        else:
            if check(line): i -= 1; continue
            else: break
    return i+2

def _node_span_to_lines(source: bytes, node, context_lines:int=2, lang_name:str|None=None):
    start = node.start_point[0] + 1
    end = node.end_point[0] + 1
    full = source.decode("utf-8", errors="ignore").splitlines()
    sctx = max(1, start - context_lines)
    ectx = min(len(full), end + context_lines)
    hdr = _merge_header_comments(full, start, lang_name or "")
    sctx = min(sctx, hdr)
    text = "\n".join(full[sctx-1:ectx])
    return start, end, text

def chunk_by_ast(path: Path, context_lines:int=2) -> list[dict]:
    lang_name = LANG_MAP.get(path.suffix.lower())
    source = path.read_bytes()
    if not lang_name:
        txt = source.decode("utf-8", errors="ignore"); lines = txt.splitlines()
        return [{"line_start": 1, "line_end": len(lines) or 1, "text": txt}]
    try:
        lang = get_language(lang_name)
    except Exception:
        txt = source.decode("utf-8", errors="ignore"); lines = txt.splitlines()
        return [{"line_start": 1, "line_end": len(lines) or 1, "text": txt}]
    parser = Parser(); parser.set_language(lang)
    tree = parser.parse(source); types = NODE_TYPES.get(lang_name, []); chunks = []
    def walk(node):
        if node.type in types:
            s,e,txt = _node_span_to_lines(source, node, context_lines=context_lines, lang_name=lang_name)
            if (e - s) >= 1: chunks.append({"line_start": s, "line_end": e, "text": txt})
        for c in node.children or []: walk(c)
    walk(tree.root_node)
    if not chunks:
        txt = source.decode("utf-8", errors="ignore"); lines = txt.splitlines()
        return [{"line_start": 1, "line_end": len(lines) or 1, "text": txt}]
    return chunks
