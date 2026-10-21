from __future__ import annotations
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChartSpec(BaseModel):
    type: Literal["line", "bar", "pie", "area", "table"]
    title: str
    x_axis: str
    y_axis: str
    data: List[Dict[str, Any]] = Field(default_factory=list)

class ExecutionMetrics(BaseModel):
    tables_used: List[str] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0

class ChatRequest(BaseModel):
    session_id: str
    message: str
    history: Optional[List[ChatMessage]] = Field(default_factory=list)

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sql_query: str
    chart: Optional[ChartSpec] = None
    data_preview: List[Dict[str, Any]] = Field(default_factory=list)
    execution_metrics: ExecutionMetrics
    error: Optional[str] = None
