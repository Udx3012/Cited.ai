from pydantic import BaseModel, Field
from typing import List, Optional

class RetrievalRequest(BaseModel):
    query: str = Field(..., min_length=2, description="The search query text for hybrid matching")
    limit: Optional[int] = Field(5, ge=1, le=50, description="Max fused candidate chunks to return")
    top_k: Optional[int] = Field(20, ge=1, le=100, description="Max candidate points fetched per retrieval stream (dense & sparse)")
    rrf_k: Optional[int] = Field(60, ge=1, le=100, description="Reciprocal Rank Fusion constant parameter")

class ChunkMatch(BaseModel):
    id: str  # Point IDs are represented as UUID strings
    document_name: str
    page: int
    chunk_index: int
    text: str
    vector_score: float
    bm25_score: float
    rerank_score: float

class RetrievalResponse(BaseModel):
    success: bool
    query: str
    results: List[ChunkMatch]
    latency_ms: int
