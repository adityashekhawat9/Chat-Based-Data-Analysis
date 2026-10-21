from __future__ import annotations
import uuid
from typing import Optional, List, Tuple
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse

from backend.app.models.dataset import (
    ValidationResponse,
    ValidationIssue,
    Severity,
    IssueCode,
    RegisterDatasetRequest,
    RegisteredDatasetResponse,
    SessionDatasetsResponse,
    BatchRegisterRequest,
    BatchRegisterResponse,
)
from backend.app.models.upload import (
    UploadInitRequest,
    UploadInitResponse,
    UploadStatusResponse,
    UploadCompleteRequest,
)
from backend.app.auth.tenant import get_current_tenant
from backend.app.validation.file_validator import FileValidator
from backend.app.validation.schema_profiler import SchemaProfiler
from backend.app.validation.data_quality import DataQualityChecker
from backend.app.validation.dataset_registry import DatasetRegistry
from backend.app.validation.chunked_uploader import ChunkedUploadService

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# Global singleton services with local persistence
registry = DatasetRegistry()
file_validator = FileValidator()
schema_profiler = SchemaProfiler()
data_quality_checker = DataQualityChecker()
chunked_uploader = ChunkedUploadService()

Tuple_Validation = Tuple[ValidationResponse, bool]

def _run_validation_pipeline(
    filename: str,
    content_bytes: bytes,
    session_id: str,
    tenant_id: str,
) -> Tuple_Validation:

    content_hash = registry.compute_content_hash(content_bytes)

    # 1. Idempotency Check: Already registered in this session?
    existing = registry.get_existing_registration(session_id, content_hash, tenant_id=tenant_id)
    if existing:
        return ValidationResponse(
            status="passed",
            session_id=session_id,
            filename=filename,
            file_size_bytes=len(content_bytes),
            content_hash=content_hash,
            is_duplicate=True,
            existing_dataset_id=existing.dataset_id,
            row_count=existing.row_count,
            column_count=existing.column_count,
            can_register=True,
            issues=[
                ValidationIssue(
                    code="IDEMPOTENT_DUPLICATE",
                    severity=Severity.WARNING,
                    message=f"Byte-identical dataset is already registered in this tenant session as table '{existing.table_name}' ({existing.dataset_id}).",
                    recommended_action="Use the existing dataset registration or upload a different file."
                )
            ],
            column_profiles=[],
        ), False

    all_issues: List[ValidationIssue] = []

    # 2. File Validation (Format, Size, Encoding, Script Injection)
    file_result = file_validator.validate_file(filename, content_bytes)
    all_issues.extend(file_result.issues)

    if not file_result.is_valid:
        resp = ValidationResponse(
            status="failed",
            session_id=session_id,
            filename=filename,
            file_size_bytes=len(content_bytes),
            content_hash=content_hash,
            is_duplicate=False,
            row_count=0,
            column_count=0,
            can_register=False,
            issues=all_issues,
            column_profiles=[],
        )
        registry.stage_dataset(session_id, filename, content_bytes, resp, tenant_id=tenant_id)
        return resp, True

    # 3. Schema Profiling (Raw Headers, Duplicates, Empties, Types)
    schema_result = schema_profiler.profile_schema(file_result.raw_rows)
    all_issues.extend(schema_result.issues)

    raw_headers = schema_result.raw_headers
    data_rows = file_result.raw_rows[1:] if len(file_result.raw_rows) > 1 else []
    row_count = len(data_rows)
    column_count = len(raw_headers)

    if not schema_result.is_valid:
        resp = ValidationResponse(
            status="failed",
            session_id=session_id,
            filename=filename,
            file_size_bytes=len(content_bytes),
            content_hash=content_hash,
            is_duplicate=False,
            row_count=row_count,
            column_count=column_count,
            can_register=False,
            issues=all_issues,
            column_profiles=[],
        )
        registry.stage_dataset(session_id, filename, content_bytes, resp, tenant_id=tenant_id)
        return resp, True

    # 4. Data Quality Checks (Empty Columns, Index Columns, Duplicate Rows, Missing Rates)
    quality_issues = data_quality_checker.check_quality(
        raw_headers, data_rows, schema_result.column_profiles
    )
    all_issues.extend(quality_issues)

    has_blocking = any(issue.severity == Severity.BLOCKING for issue in all_issues)
    has_warnings = any(issue.severity == Severity.WARNING for issue in all_issues)
    overall_status = "failed" if has_blocking else ("warnings" if has_warnings else "passed")
    can_register = not has_blocking

    response = ValidationResponse(
        status=overall_status,
        session_id=session_id,
        filename=filename,
        file_size_bytes=len(content_bytes),
        content_hash=content_hash,
        is_duplicate=False,
        row_count=row_count,
        column_count=column_count,
        can_register=can_register,
        issues=all_issues,
        column_profiles=schema_result.column_profiles,
    )

    registry.stage_dataset(session_id, filename, content_bytes, response, tenant_id=tenant_id)
    return response, has_blocking

Tuple_Validation = tuple[ValidationResponse, bool]

@router.post("/validate", response_model=ValidationResponse)
async def validate_dataset(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Standard single-payload multipart validation for smaller files.
    """
    effective_session_id = session_id or f"sess_{uuid.uuid4()}"
    filename = file.filename or "uploaded.csv"

    try:
        content_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file stream: {str(e)}"
        )

    response, has_blocking = _run_validation_pipeline(
        filename, content_bytes, effective_session_id, tenant_id
    )

    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY if has_blocking else status.HTTP_200_OK
    return JSONResponse(status_code=http_status, content=response.model_dump())

# --------------------------------------------------------------------------
# Resumable Chunked Multipart Upload Endpoints
# --------------------------------------------------------------------------

@router.post("/upload/init", response_model=UploadInitResponse)
def init_chunked_upload(
    req: UploadInitRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Initializes a resumable chunked upload session for large files.
    """
    try:
        return chunked_uploader.init_upload(tenant_id, req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/upload/chunk")
async def upload_file_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk_file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Uploads an individual chunk part for an ongoing upload session.
    """
    try:
        chunk_bytes = await chunk_file.read()
        bytes_saved = chunked_uploader.save_chunk(
            tenant_id=tenant_id,
            upload_id=upload_id,
            chunk_index=chunk_index,
            chunk_bytes=chunk_bytes,
        )
        return {"status": "chunk_saved", "chunk_index": chunk_index, "bytes": bytes_saved}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save chunk: {str(e)}")

@router.get("/upload/status", response_model=UploadStatusResponse)
def get_upload_status(
    upload_id: str = Query(...),
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Returns the list of uploaded chunk indices so client can resume from where it left off.
    """
    try:
        return chunked_uploader.get_status(tenant_id, upload_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

@router.post("/upload/complete", response_model=ValidationResponse)
def complete_chunked_upload(
    req: UploadCompleteRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Stitches all chunk parts together on disk, verifies integrity, and feeds
    the assembled dataset into the pre-flight validation pipeline.
    """
    try:
        filename, assembled_bytes, content_hash, session_id = chunked_uploader.assemble_file(
            tenant_id, req.upload_id
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assemble chunks: {str(e)}")

    if req.expected_hash and req.expected_hash.lower() != content_hash.lower():
        raise HTTPException(
            status_code=422,
            detail=f"SHA-256 mismatch: expected {req.expected_hash}, calculated {content_hash}"
        )

    response, has_blocking = _run_validation_pipeline(
        filename, assembled_bytes, session_id, tenant_id
    )

    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY if has_blocking else status.HTTP_200_OK
    return JSONResponse(status_code=http_status, content=response.model_dump())

# --------------------------------------------------------------------------
# Dataset Registration Endpoints
# --------------------------------------------------------------------------

@router.post("/register", response_model=RegisteredDatasetResponse, status_code=status.HTTP_201_CREATED)
def register_dataset(
    req: RegisterDatasetRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Registers a validated dataset into the tenant's isolated persistent DuckDB catalog.
    Guarantees that registered bytes match validated bytes (prevents TOCTOU).
    """
    try:
        registered = registry.register_staged_dataset(
            session_id=req.session_id,
            content_hash=req.content_hash,
            table_name=req.table_name,
            tenant_id=tenant_id,
        )
        return registered
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/register-batch", response_model=BatchRegisterResponse, status_code=status.HTTP_200_OK)
def register_batch_datasets(
    req: BatchRegisterRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Registers a batch of staged datasets into the tenant's persistent DuckDB catalog.
    Processes each staged dataset sequentially to ensure safe catalog updates.
    """
    registered_list: List[RegisteredDatasetResponse] = []
    errors_list: List[dict] = []

    for item in req.items:
        try:
            registered = registry.register_staged_dataset(
                session_id=item.session_id,
                content_hash=item.content_hash,
                table_name=item.table_name,
                tenant_id=tenant_id,
            )
            registered_list.append(registered)
        except Exception as e:
            errors_list.append({
                "content_hash": item.content_hash,
                "table_name": item.table_name,
                "error": str(e),
            })

    return BatchRegisterResponse(registered=registered_list, errors=errors_list)

@router.get("/sessions/{session_id}", response_model=SessionDatasetsResponse)
def get_session_datasets(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Returns all registered datasets in the tenant's session catalog.
    """
    datasets = registry.get_session_datasets(session_id, tenant_id=tenant_id)
    return SessionDatasetsResponse(session_id=session_id, datasets=datasets)
