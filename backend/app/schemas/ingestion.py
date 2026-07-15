from pydantic import BaseModel
from typing import Optional

class UploadResponse(BaseModel):
    success: bool
    job_id: str
    document_id: str
    filename: str
    storage_url: str
    file_type: str  # "pdf" | "docx"
    message: str

class JobStatusResponse(BaseModel):
    success: bool
    job_id: str
    document_id: str
    status: str  # "queued", "processing", "completed", "failed"
    progress: int
    pages: int
    chunks: int
    error_message: Optional[str] = None

class IngestionStatusResponse(BaseModel):
    success: bool
    message: str
