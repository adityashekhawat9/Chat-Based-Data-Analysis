import os
import glob
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Body, Depends
from backend.app.auth.tenant import get_current_tenant

from backend.app.models.chat import ChatRequest, ChatResponse
from backend.app.models.dataset import RegisteredDatasetResponse, SessionDatasetsResponse
from backend.app.api.datasets import registry, file_validator, schema_profiler, data_quality_checker
from backend.app.query.llm_service import LLMService

router = APIRouter(prefix="/api", tags=["chat"])
llm_service = LLMService()

SAMPLE_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "Online Shop 2024"
)

@router.post("/chat", response_model=ChatResponse)
def handle_chat_query(
    req: ChatRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Translates user natural-language questions to safe, read-only DuckDB SQL,
    executes deterministically, and synthesizes grounded answers with dynamic charts.
    """
    if not req.message or not req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    conn = registry.get_tenant_duckdb(tenant_id)
    response = llm_service.query(
        session_id=req.session_id,
        user_message=req.message,
        conn=conn,
        history=req.history,
    )
    return response

@router.post("/datasets/load-sample", response_model=SessionDatasetsResponse)
def load_sample_dataset(
    session_id: str = Body(..., embed=True),
    tenant_id: str = Depends(get_current_tenant),
):

    """
    Preloads the default 8 ecommerce CSV tables (Online Shop 2024)
    into the active session DuckDB catalog after running full validation.
    """
    if not os.path.exists(SAMPLE_DATA_DIR):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sample data directory not found at {SAMPLE_DATA_DIR}"
        )

    csv_files = sorted(glob.glob(os.path.join(SAMPLE_DATA_DIR, "*.csv")))
    if not csv_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CSV files found in sample directory."
        )

    registered_list = []
    for csv_path in csv_files:
        filename = os.path.basename(csv_path)
        table_name = filename.replace(".csv", "").strip().lower()

        with open(csv_path, "rb") as f:
            content_bytes = f.read()

        content_hash = registry.compute_content_hash(content_bytes)

        # Check if already registered
        existing = registry.get_existing_registration(session_id, content_hash, tenant_id=tenant_id)
        if existing:
            registered_list.append(
                RegisteredDatasetResponse(
                    dataset_id=existing.dataset_id,
                    session_id=existing.session_id,
                    table_name=existing.table_name,
                    filename=existing.filename,
                    content_hash=existing.content_hash,
                    row_count=existing.row_count,
                    column_count=existing.column_count,
                    registered_at=existing.registered_at,
                    columns=existing.columns,
                )
            )
            continue

        # Run validation pipeline
        f_res = file_validator.validate_file(filename, content_bytes)
        s_res = schema_profiler.profile_schema(f_res.raw_rows)
        data_rows = f_res.raw_rows[1:] if len(f_res.raw_rows) > 1 else []
        q_issues = data_quality_checker.check_quality(s_res.raw_headers, data_rows, s_res.column_profiles)

        all_issues = f_res.issues + s_res.issues + q_issues
        can_register = not any(i.severity.value == "BLOCKING" for i in all_issues)

        from backend.app.models.dataset import ValidationResponse
        v_resp = ValidationResponse(
            status="passed" if can_register else "failed",
            session_id=session_id,
            filename=filename,
            file_size_bytes=len(content_bytes),
            content_hash=content_hash,
            is_duplicate=False,
            row_count=len(data_rows),
            column_count=len(s_res.raw_headers),
            can_register=can_register,
            issues=all_issues,
            column_profiles=s_res.column_profiles,
        )

        registry.stage_dataset(session_id, filename, content_bytes, v_resp, tenant_id=tenant_id)
        reg_item = registry.register_staged_dataset(
            session_id, content_hash, table_name, tenant_id=tenant_id
        )
        registered_list.append(reg_item)

    return SessionDatasetsResponse(session_id=session_id, datasets=registered_list)

