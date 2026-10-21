import os
import re
from typing import Optional
from fastapi import Header, HTTPException, status

DEFAULT_TENANT_ID = "default_tenant"
TENANT_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")

def sanitize_tenant_id(tenant_id: str) -> str:
    """
    Validates tenant ID format to prevent directory traversal and injection.
    """
    if not tenant_id or not TENANT_ID_REGEX.match(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tenant_id '{tenant_id}'. Must be alphanumeric with underscores or hyphens."
        )
    if len(tenant_id) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant ID exceeds maximum allowed length of 64 characters."
        )
    return tenant_id

async def get_current_tenant(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")
) -> str:
    """
    FastAPI dependency that extracts and validates the tenant context from the request header.
    Defaults to 'default_tenant' for streamlined local development and testing.
    """
    if not x_tenant_id:
        return DEFAULT_TENANT_ID
    return sanitize_tenant_id(x_tenant_id)

def get_tenant_base_dir(base_storage: str, tenant_id: str) -> str:
    """
    Resolves and verifies that the tenant directory is strictly contained within base_storage.
    Guarantees zero path traversal vulnerability.
    """
    sanitized = sanitize_tenant_id(tenant_id)
    base_abs = os.path.abspath(base_storage)
    tenant_dir = os.path.abspath(os.path.join(base_abs, "tenants", sanitized))

    if os.path.commonpath([base_abs, tenant_dir]) != base_abs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Illegal directory traversal attempt detected in tenant resolution."
        )

    os.makedirs(tenant_dir, exist_ok=True)
    return tenant_dir
