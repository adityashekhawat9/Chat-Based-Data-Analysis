import os
import glob
import json
import uuid
import hashlib
from typing import List, Tuple, Optional, Dict, Any
from backend.app.auth.tenant import get_tenant_base_dir
from backend.app.models.upload import (
    UploadInitRequest,
    UploadInitResponse,
    UploadStatusResponse,
)

class ChunkedUploadService:
    def __init__(self, base_storage: str = "data"):
        self.base_storage = base_storage

    def init_upload(
        self, tenant_id: str, req: UploadInitRequest
    ) -> UploadInitResponse:
        upload_id = f"upl_{uuid.uuid4().hex[:16]}"
        tenant_dir = get_tenant_base_dir(self.base_storage, tenant_id)
        staging_dir = os.path.join(tenant_dir, "staging", upload_id)
        os.makedirs(staging_dir, exist_ok=True)

        manifest = {
            "upload_id": upload_id,
            "tenant_id": tenant_id,
            "session_id": req.session_id,
            "filename": req.filename,
            "file_size_bytes": req.file_size_bytes,
            "total_chunks": req.total_chunks,
            "chunk_size_bytes": req.chunk_size_bytes,
        }
        with open(os.path.join(staging_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        return UploadInitResponse(
            upload_id=upload_id,
            session_id=req.session_id,
            expected_chunks=req.total_chunks,
            chunk_size_bytes=req.chunk_size_bytes,
        )

    def save_chunk(
        self, tenant_id: str, upload_id: str, chunk_index: int, chunk_bytes: bytes
    ) -> int:
        tenant_dir = get_tenant_base_dir(self.base_storage, tenant_id)
        staging_dir = os.path.join(tenant_dir, "staging", upload_id)
        if not os.path.exists(staging_dir):
            raise ValueError(f"Upload session '{upload_id}' does not exist or expired.")

        chunk_path = os.path.join(staging_dir, f"chunk_{chunk_index:05d}.part")
        with open(chunk_path, "wb") as f:
            f.write(chunk_bytes)

        return len(chunk_bytes)

    def get_status(
        self, tenant_id: str, upload_id: str
    ) -> UploadStatusResponse:
        tenant_dir = get_tenant_base_dir(self.base_storage, tenant_id)
        staging_dir = os.path.join(tenant_dir, "staging", upload_id)
        if not os.path.exists(staging_dir):
            raise ValueError(f"Upload session '{upload_id}' not found.")

        with open(os.path.join(staging_dir, "manifest.json"), "r", encoding="utf-8") as f:
            manifest = json.load(f)

        part_files = sorted(glob.glob(os.path.join(staging_dir, "chunk_*.part")))
        uploaded_chunks = []
        for pf in part_files:
            fname = os.path.basename(pf)
            idx_str = fname.replace("chunk_", "").replace(".part", "")
            try:
                uploaded_chunks.append(int(idx_str))
            except ValueError:
                pass

        total_chunks = manifest.get("total_chunks", 0)
        is_complete = len(uploaded_chunks) == total_chunks

        return UploadStatusResponse(
            upload_id=upload_id,
            uploaded_chunks=uploaded_chunks,
            total_chunks=total_chunks,
            is_complete=is_complete,
        )

    def assemble_file(
        self, tenant_id: str, upload_id: str
    ) -> Tuple[str, bytes, str, str]:
        """
        Stitches chunk parts together in sequential order, computes SHA-256 digest,
        and cleans up temporary chunk parts.
        Returns: (filename, assembled_bytes, content_hash, session_id)
        """
        tenant_dir = get_tenant_base_dir(self.base_storage, tenant_id)
        staging_dir = os.path.join(tenant_dir, "staging", upload_id)
        if not os.path.exists(staging_dir):
            raise ValueError(f"Upload session '{upload_id}' not found.")

        manifest_path = os.path.join(staging_dir, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        filename = manifest.get("filename", "uploaded.csv")
        session_id = manifest.get("session_id", "default_sess")
        total_chunks = manifest.get("total_chunks", 0)

        # Verify all chunks are present
        part_files = sorted(glob.glob(os.path.join(staging_dir, "chunk_*.part")))
        if len(part_files) < total_chunks:
            missing = set(range(total_chunks)) - {
                int(os.path.basename(pf).replace("chunk_", "").replace(".part", ""))
                for pf in part_files
            }
            raise ValueError(f"Upload incomplete. Missing chunks: {sorted(list(missing))}")

        # Assemble into byte buffer
        assembled_buffer = bytearray()
        hasher = hashlib.sha256()

        for chunk_idx in range(total_chunks):
            chunk_path = os.path.join(staging_dir, f"chunk_{chunk_idx:05d}.part")
            with open(chunk_path, "rb") as cf:
                data = cf.read()
                assembled_buffer.extend(data)
                hasher.update(data)

        final_bytes = bytes(assembled_buffer)
        content_hash = hasher.hexdigest()

        # Clean up chunk parts to free space
        for pf in part_files:
            try:
                os.remove(pf)
            except OSError:
                pass
        try:
            os.remove(manifest_path)
            os.rmdir(staging_dir)
        except OSError:
            pass

        return filename, final_bytes, content_hash, session_id
