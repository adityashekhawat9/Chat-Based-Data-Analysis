from typing import List, Optional
from pydantic import BaseModel, Field

class UploadInitRequest(BaseModel):
    session_id: str
    filename: str
    file_size_bytes: int
    total_chunks: int
    chunk_size_bytes: int

class UploadInitResponse(BaseModel):
    upload_id: str
    session_id: str
    expected_chunks: int
    chunk_size_bytes: int

class UploadStatusResponse(BaseModel):
    upload_id: str
    uploaded_chunks: List[int]
    total_chunks: int
    is_complete: bool

class UploadCompleteRequest(BaseModel):
    upload_id: str
    session_id: str
    expected_hash: Optional[str] = None
