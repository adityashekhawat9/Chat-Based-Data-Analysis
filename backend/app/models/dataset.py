from __future__ import annotations
from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class Severity(str, Enum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"

class IssueCode(str, Enum):
    # Blocking Errors
    EMPTY_FILE = "EMPTY_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    INVALID_ENCODING = "INVALID_ENCODING"
    MALFORMED_CSV = "MALFORMED_CSV"
    SCRIPT_INJECTION_RISK = "SCRIPT_INJECTION_RISK"
    DUPLICATE_COLUMNS = "DUPLICATE_COLUMNS"
    EMPTY_COLUMN_HEADER = "EMPTY_COLUMN_HEADER"
    
    # Non-blocking Warnings
    FULLY_EMPTY_COLUMN = "FULLY_EMPTY_COLUMN"
    LIKELY_INDEX_COLUMN = "LIKELY_INDEX_COLUMN"
    DUPLICATE_ROWS = "DUPLICATE_ROWS"
    HIGH_MISSING_RATE = "HIGH_MISSING_RATE"
    MIXED_TYPES = "MIXED_TYPES"

class ValidationIssue(BaseModel):
    code: str
    severity: Severity
    message: str
    column: Optional[str] = None
    affected_count: Optional[int] = None
    recommended_action: str

class ColumnProfile(BaseModel):
    name: str
    raw_name: str
    inferred_type: str
    null_count: int
    null_percentage: float
    unique_count: int
    is_unique: bool
    sample_values: List[str] = Field(default_factory=list)

class ValidationResponse(BaseModel):
    status: str  # "passed", "warnings", "failed"
    session_id: str
    filename: str
    file_size_bytes: int
    content_hash: str
    is_duplicate: bool = False
    existing_dataset_id: Optional[str] = None
    row_count: int
    column_count: int
    can_register: bool
    issues: List[ValidationIssue] = Field(default_factory=list)
    column_profiles: List[ColumnProfile] = Field(default_factory=list)

class RegisterDatasetRequest(BaseModel):
    session_id: str
    content_hash: str
    table_name: Optional[str] = None

class RegisteredDatasetResponse(BaseModel):
    dataset_id: str
    session_id: str
    table_name: str
    filename: str
    content_hash: str
    row_count: int
    column_count: int
    registered_at: str
    columns: List[str] = Field(default_factory=list)

class SessionDatasetsResponse(BaseModel):
    session_id: str
    datasets: List[RegisteredDatasetResponse] = Field(default_factory=list)
