import os
import json
import uuid
import time
from typing import Dict, Any, List, Optional
from backend.app.auth.tenant import get_tenant_base_dir

class TraceSpan:
    def __init__(self, name: str, start_time: float):
        self.name = name
        self.start_time = start_time
        self.duration_ms: float = 0.0
        self.status: str = "running"
        self.metadata: Dict[str, Any] = {}

class RequestTrace:
    def __init__(self, trace_id: str, tenant_id: str, session_id: str, operation: str):
        self.trace_id = trace_id
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.operation = operation
        self.start_time = time.perf_counter()
        self.spans: Dict[str, TraceSpan] = {}
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.metrics: Dict[str, Any] = {}

    def start_span(self, name: str):
        self.spans[name] = TraceSpan(name=name, start_time=time.perf_counter())

    def end_span(self, name: str, status: str = "success", metadata: Optional[Dict[str, Any]] = None):
        if name in self.spans:
            span = self.spans[name]
            span.duration_ms = round((time.perf_counter() - span.start_time) * 1000, 2)
            span.status = status
            if metadata:
                span.metadata.update(metadata)

    def add_warning(self, warning: str):
        self.warnings.append(warning)

    def add_error(self, error: str):
        self.errors.append(error)

    def set_metric(self, key: str, value: Any):
        self.metrics[key] = value

    def to_dict(self) -> Dict[str, Any]:
        total_duration_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
        return {
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "operation": self.operation,
            "total_duration_ms": total_duration_ms,
            "spans": {
                name: {
                    "duration_ms": span.duration_ms,
                    "status": span.status,
                    "metadata": span.metadata,
                }
                for name, span in self.spans.items()
            },
            "warnings": self.warnings,
            "errors": self.errors,
            "metrics": self.metrics,
            "timestamp": time.time(),
        }

class TracingService:
    def __init__(self, base_storage: str = "data"):
        self.base_storage = base_storage

    def create_trace(
        self, tenant_id: str, session_id: str, operation: str = "query"
    ) -> RequestTrace:
        trace_id = f"tr_{uuid.uuid4().hex[:12]}"
        return RequestTrace(
            trace_id=trace_id,
            tenant_id=tenant_id,
            session_id=session_id,
            operation=operation,
        )

    def persist_trace(self, trace: RequestTrace):
        try:
            tenant_dir = get_tenant_base_dir(self.base_storage, trace.tenant_id)
            trace_file = os.path.join(tenant_dir, "traces.jsonl")
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace.to_dict()) + "\n")
        except Exception as e:
            # Tracing should not break application execution if write fails
            print(f"[TracingService] Failed to persist trace: {e}")
