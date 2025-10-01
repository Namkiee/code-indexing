
from pydantic import BaseModel
from typing import List, Optional

class ChunkMeta(BaseModel):
    tenant_id: str = "default"
    chunk_id: str
    repo_id: str
    lang: Optional[str] = None
    path_tokens: list[str]
    rel_path: Optional[str] = None
    is_test: Optional[bool] = False
    line_start: int
    line_end: int
    token_count: Optional[int] = None
    privacy_mode: bool = False
    text: Optional[str] = None
    vector: Optional[list[float]] = None

class UploadRequest(BaseModel):
    chunks: List[ChunkMeta]

class SearchRequest(BaseModel):
    tenant_id: str = "default"
    repo_id: str
    query: str
    top_k: int = 12
    lang: Optional[str] = None
    dir_hint: Optional[str] = None
    exclude_tests: bool = False

class SearchHit(BaseModel):
    chunk_id: str
    score: float
    path_tokens: list[str]
    line_span: list[int]
    repo_id: str
    preview: Optional[str] = None

class SearchResponse(BaseModel):
    search_id: str | None = None
    bucket: Optional[str] = None
    need_fetch_lines: bool = False
    hits: List[SearchHit]

class FetchLinesItem(BaseModel):
    chunk_id: str
    raw_lines: str

class FetchLinesRequest(BaseModel):
    tenant_id: str = "default"
    repo_id: str
    query: str
    items: List[FetchLinesItem]
    top_k: int = 12

class FetchLinesResponse(BaseModel):
    hits: List[SearchHit]

class FeedbackRequest(BaseModel):
    search_id: str
    clicked_chunk_id: str
    grade: int = 1

class FeedbackResponse(BaseModel):
    status: str
