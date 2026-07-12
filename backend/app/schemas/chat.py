from pydantic import BaseModel, Field
from typing import List, Optional

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=2, description="The user's conversational query")
    model_type: Optional[str] = Field("high", description="The LLM model complexity tier ('standard' or 'high')")
    temperature: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="Model generation temperature")
    stream: Optional[bool] = Field(False, description="Toggles Server-Sent Events (SSE) token streaming")

class CitationMeta(BaseModel):
    id: int  # Citation marker index e.g., 1 for [1]
    source: str
    page: int
    chunk: int
    matched_text: str

class ChatResponse(BaseModel):
    success: bool
    answer: str
    citations: List[CitationMeta]
    confidence_score: float
    sufficient_context: bool
    latency_ms: int
