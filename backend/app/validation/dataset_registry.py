import os
import json
import glob
import hashlib
import uuid
import datetime
import re
from typing import Dict, List, Optional, Tuple, Any
import duckdb

from backend.app.models.dataset import (
    ValidationResponse,
    RegisteredDatasetResponse,
    ValidationIssue,
    Severity,
)
from backend.app.auth.tenant import get_tenant_base_dir, DEFAULT_TENANT_ID

class StagedDataset:
    def __init__(
        self,
        tenant_id: str,
        session_id: str,
        filename: str,
        content_bytes: bytes,
        content_hash: str,
        validation_response: ValidationResponse,
    ):
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.filename = filename
        self.content_bytes = content_bytes
        self.content_hash = content_hash
        self.validation_response = validation_response
        self.staged_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

class RegisteredDataset:
    def __init__(
        self,
        dataset_id: str,
        tenant_id: str,
        session_id: str,
        table_name: str,
        filename: str,
        content_hash: str,
        row_count: int,
        column_count: int,
        columns: List[str],
        registered_at: str,
    ):
        self.dataset_id = dataset_id
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.table_name = table_name
        self.filename = filename
        self.content_hash = content_hash
        self.row_count = row_count
        self.column_count = column_count
        self.columns = columns
        self.registered_at = registered_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "table_name": self.table_name,
            "filename": self.filename,
            "content_hash": self.content_hash,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns,
            "registered_at": self.registered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegisteredDataset":
        return cls(
            dataset_id=data["dataset_id"],
            tenant_id=data.get("tenant_id", DEFAULT_TENANT_ID),
            session_id=data["session_id"],
            table_name=data["table_name"],
            filename=data["filename"],
            content_hash=data["content_hash"],
            row_count=data["row_count"],
            column_count=data["column_count"],
            columns=data["columns"],
            registered_at=data["registered_at"],
        )

class DatasetRegistry:
    def __init__(self, base_storage_dir: str = "data"):
        self.base_storage_dir = base_storage_dir
        # Staged datasets: key = (tenant_id, session_id, content_hash)
        self._staged: Dict[Tuple[str, str, str], StagedDataset] = {}
        # Registered datasets: key = dataset_id
        self._registered: Dict[str, RegisteredDataset] = {}
        # Index: (tenant_id, session_id, content_hash) -> dataset_id
        self._hash_to_dataset: Dict[Tuple[str, str, str], str] = {}
        # Persistent DuckDB connection per tenant: key = tenant_id
        self._duckdb_conns: Dict[str, duckdb.DuckDBPyConnection] = {}

        # Recover persisted state from disk on startup
        self._recover_persisted_state()

    def _recover_persisted_state(self):
        """
        Scans data/tenants/*/metadata.json and reloads registered datasets
        so state survives server restarts.
        """
        tenants_pattern = os.path.join(self.base_storage_dir, "tenants", "*", "metadata.json")
        for meta_path in glob.glob(tenants_pattern):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                    for item in records:
                        dataset = RegisteredDataset.from_dict(item)
                        self._registered[dataset.dataset_id] = dataset
                        key = (dataset.tenant_id, dataset.session_id, dataset.content_hash)
                        self._hash_to_dataset[key] = dataset.dataset_id
            except Exception as e:
                print(f"[DatasetRegistry] Warning: Could not load metadata from {meta_path}: {e}")

    def _persist_metadata(self, tenant_id: str):
        """
        Persists all registered datasets for a tenant to data/tenants/{tenant_id}/metadata.json
        """
        tenant_dir = get_tenant_base_dir(self.base_storage_dir, tenant_id)
        meta_path = os.path.join(tenant_dir, "metadata.json")
        tenant_datasets = [
            ds.to_dict()
            for ds in self._registered.values()
            if ds.tenant_id == tenant_id
        ]
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(tenant_datasets, f, indent=2)

    def compute_content_hash(self, content_bytes: bytes) -> str:
        return hashlib.sha256(content_bytes).hexdigest()

    def get_existing_registration(
        self, session_id: str, content_hash: str, tenant_id: str = DEFAULT_TENANT_ID
    ) -> Optional[RegisteredDataset]:
        key = (tenant_id, session_id, content_hash)
        dataset_id = self._hash_to_dataset.get(key)
        if dataset_id:
            return self._registered.get(dataset_id)
        return None

    def stage_dataset(
        self,
        session_id: str,
        filename: str,
        content_bytes: bytes,
        validation_response: ValidationResponse,
        tenant_id: str = DEFAULT_TENANT_ID,
    ) -> StagedDataset:
        content_hash = validation_response.content_hash
        staged = StagedDataset(
            tenant_id=tenant_id,
            session_id=session_id,
            filename=filename,
            content_bytes=content_bytes,
            content_hash=content_hash,
            validation_response=validation_response,
        )
        self._staged[(tenant_id, session_id, content_hash)] = staged
        return staged

    def register_staged_dataset(
        self,
        session_id: str,
        content_hash: str,
        table_name: Optional[str] = None,
        tenant_id: str = DEFAULT_TENANT_ID,
    ) -> RegisteredDatasetResponse:
        key = (tenant_id, session_id, content_hash)

        # 1. Idempotency check: Already registered for this tenant?
        existing = self.get_existing_registration(session_id, content_hash, tenant_id=tenant_id)
        if existing:
            return RegisteredDatasetResponse(
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

        # 2. Verify staged bytes exist (prevent TOCTOU)
        staged = self._staged.get(key)
        if not staged:
            raise ValueError(
                f"No staged dataset found with hash '{content_hash}' in session '{session_id}' for tenant '{tenant_id}'. Run validation first."
            )

        # 3. Reject if validation failed with blocking errors
        if not staged.validation_response.can_register:
            blocking_issues = [
                i.message
                for i in staged.validation_response.issues
                if i.severity == Severity.BLOCKING
            ]
            raise ValueError(
                f"Cannot register dataset with blocking validation errors: {blocking_issues}"
            )

        # 4. Generate clean, unique table name scoped to this tenant
        clean_table_name = self._resolve_table_name(
            tenant_id, session_id, table_name or staged.filename
        )

        # 5. Persist raw uploaded file to disk for audit & provenance
        tenant_dir = get_tenant_base_dir(self.base_storage_dir, tenant_id)
        uploads_dir = os.path.join(tenant_dir, "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        persisted_csv_path = os.path.join(uploads_dir, f"{content_hash}.csv")
        with open(persisted_csv_path, "wb") as f:
            f.write(staged.content_bytes)

        # 6. Load into Tenant's Persistent DuckDB catalog
        conn = self.get_tenant_duckdb(tenant_id)
        try:
            # Mount table directly from persisted CSV file
            conn.execute(
                f"CREATE OR REPLACE TABLE \"{clean_table_name}\" AS SELECT * FROM read_csv_auto('{persisted_csv_path}')"
            )
        except Exception:
            # Fallback direct string loader
            csv_str = staged.content_bytes.decode("utf-8", errors="replace")
            conn.execute(
                f"CREATE OR REPLACE TABLE \"{clean_table_name}\" AS SELECT * FROM read_csv_auto(?)",
                [csv_str],
            )

        # 7. Assign UUID and persist record
        dataset_id = f"ds_{uuid.uuid4()}"
        columns = [p.name for p in staged.validation_response.column_profiles]
        registered = RegisteredDataset(
            dataset_id=dataset_id,
            tenant_id=tenant_id,
            session_id=session_id,
            table_name=clean_table_name,
            filename=staged.filename,
            content_hash=content_hash,
            row_count=staged.validation_response.row_count,
            column_count=staged.validation_response.column_count,
            columns=columns,
            registered_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

        self._registered[dataset_id] = registered
        self._hash_to_dataset[key] = dataset_id

        # Persist updated metadata to disk
        self._persist_metadata(tenant_id)

        return RegisteredDatasetResponse(
            dataset_id=registered.dataset_id,
            session_id=registered.session_id,
            table_name=registered.table_name,
            filename=registered.filename,
            content_hash=registered.content_hash,
            row_count=registered.row_count,
            column_count=registered.column_count,
            registered_at=registered.registered_at,
            columns=registered.columns,
        )

    def get_session_datasets(
        self, session_id: str, tenant_id: str = DEFAULT_TENANT_ID
    ) -> List[RegisteredDatasetResponse]:
        results = []
        for dataset in self._registered.values():
            if dataset.tenant_id == tenant_id and dataset.session_id == session_id:
                results.append(
                    RegisteredDatasetResponse(
                        dataset_id=dataset.dataset_id,
                        session_id=dataset.session_id,
                        table_name=dataset.table_name,
                        filename=dataset.filename,
                        content_hash=dataset.content_hash,
                        row_count=dataset.row_count,
                        column_count=dataset.column_count,
                        registered_at=dataset.registered_at,
                        columns=dataset.columns,
                    )
                )
        return results

    def get_tenant_duckdb(self, tenant_id: str) -> duckdb.DuckDBPyConnection:
        """
        Returns a persistent connection to the tenant's isolated catalog.duckdb file.
        Physical isolation guarantees zero cross-tenant leakage.
        """
        if tenant_id not in self._duckdb_conns:
            tenant_dir = get_tenant_base_dir(self.base_storage_dir, tenant_id)
            db_path = os.path.join(tenant_dir, "catalog.duckdb")
            # Connect to physical DuckDB file on local disk
            self._duckdb_conns[tenant_id] = duckdb.connect(db_path)
        return self._duckdb_conns[tenant_id]

    def get_session_duckdb(
        self, session_id: str, tenant_id: str = DEFAULT_TENANT_ID
    ) -> duckdb.DuckDBPyConnection:
        return self.get_tenant_duckdb(tenant_id)

    def _resolve_table_name(self, tenant_id: str, session_id: str, candidate_name: str) -> str:
        name = candidate_name.rsplit(".", 1)[0]
        name = re.sub(r"[^\w]", "_", name).strip().lower()
        name = re.sub(r"_+", "_", name)
        if not name or name[0].isdigit():
            name = f"tbl_{name}"

        existing_names = {
            ds.table_name
            for ds in self._registered.values()
            if ds.tenant_id == tenant_id
        }
        final_name = name
        suffix = 1
        while final_name in existing_names:
            final_name = f"{name}_{suffix}"
            suffix += 1
        return final_name
