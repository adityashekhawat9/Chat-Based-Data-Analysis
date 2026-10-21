# System Architecture & Technical Specifications

## 1. System Topology

The application is structured as a decoupled two-tier architecture communicating over HTTP REST:

```
+-----------------------------------------------------------------------------------+
|                            Next.js Frontend (TypeScript)                          |
|                                                                                   |
|  +--------------------+   +-----------------------+   +------------------------+  |
|  | File Upload Modal  |   |  Validation Report    |   | Chat & Chart Display   |  |
|  | (Multipart Stream) |   |  (Errors & Warnings)  |   | (Recharts + SQL Tray)  |  |
|  +--------------------+   +-----------------------+   +------------------------+  |
+-----------------------------------------|-----------------------------------------+
                                          | HTTP REST (JSON & Multipart)
+-----------------------------------------v-----------------------------------------+
|                               FastAPI Backend (Python)                            |
|                                                                                   |
|  [ Ingestion & Validation Pipeline ]                                              |
|  +-----------------------------------------------------------------------------+  |
|  | 1. FileValidator       -> Format, Size, Encoding, Script/Formula Injection  |  |
|  | 2. SchemaProfiler      -> Raw Headers, Duplicates, Empties, Type Inference  |  |
|  | 3. DataQualityChecker  -> Index Cols, Empty Cols, Duplicate Rows, Anomalies |  |
|  | 4. DatasetRegistry     -> SHA-256 Hashing, UUID, Session Scope, TOCTOU-Safe |  |
|  +-----------------------------------------------------------------------------+  |
|                                         | Staged -> Registered                    |
|  [ Analytical Engine ]                  v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | DuckDB In-Memory Catalog (Safe Relational ANSI-SQL, Vectorized Aggregations)|  |
|  +-----------------------------------------------------------------------------+  |
|                                         ^                                         |
|  [ LLM Orchestration ]                  | Validated SELECT SQL                    |
|  +-----------------------------------------------------------------------------+  |
|  | Groq API (Llama 3.3 70B) -> Semantic Intent -> SQL Plan -> Grounded Narrative |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Validation Pipeline Architecture (Separated Modules)

To satisfy the strict modularity requirements, the validation subsystem is decomposed into four isolated, single-responsibility modules under `backend/app/validation/`:

### Module 1: `FileValidator` (`backend/app/validation/file_validator.py`)
- **Responsibilities:**
  - File extension & MIME type verification (`.csv`, `.xlsx`, `.xls`).
  - File size bounds checking (0-byte rejection, max size enforcement, e.g. 50 MB).
  - Character encoding resolution (probabilistic detection with fallback UTF-8, Latin-1, Windows-1252).
  - Stream syntax validation: Ensures CSV quotes and delimiters can be parsed without tokenizer crashes.
  - Script & Formula Injection Defense: Flags raw cells starting with dangerous formula triggers (`=`, `+`, `-`, `@`) or containing embedded `<script>` / `javascript:`.

### Module 2: `SchemaProfiler` (`backend/app/validation/schema_profiler.py`)
- **Responsibilities:**
  - Raw header analysis before any normalization:
    - Identifies empty header names (e.g., `id,,price`).
    - Identifies duplicate column names (e.g., `customer_id,name,customer_id`).
  - Column name normalization (safe snake_case identifier creation for DuckDB/SQL engine).
  - Initial type inference per column (INT, FLOAT, DATETIME, BOOLEAN, STRING).

### Module 3: `DataQualityChecker` (`backend/app/validation/data_quality.py`)
- **Responsibilities:**
  - Identifies 100% empty columns (columns with all NULL or blank strings).
  - Detects auto-generated index columns (e.g. `Unnamed: 0`, strictly increasing integers starting from 0 or 1 matching row count).
  - Detects duplicate data rows (full row matches) and reports absolute count and percentage.
  - Calculates missing value percentages per column against configurable warning thresholds (e.g., warning if nulls > 20%).
  - Detects invalid type conversions (mixed data types where >90% match a numeric/date type but rogue strings exist).

### Module 4: `DatasetRegistry` (`backend/app/validation/dataset_registry.py`)
- **Responsibilities:**
  - Computes raw content hash (`SHA-256`) of uploaded bytes.
  - Enforces session-scoped idempotency: if the same file bytes are uploaded under the same or different filename within a session, the existing registration is returned without duplication.
  - Staging & TOCTOU Prevention:
    - Phase 1 (Validation): Uploaded bytes are validated and placed in a staged byte-cache keyed by `(session_id, content_hash)`.
    - Phase 2 (Registration): The client confirms registration using the `content_hash` and `session_id`. The registry verifies byte integrity, assigns a UUIDv4 `dataset_id`, registers metadata, and mounts the data table in DuckDB.
    - If a dataset has blocking errors, it is marked `rejected` and **cannot** be registered or queried.

---

## 3. API Contracts

### 3.1 Validate Dataset Endpoint
`POST /api/datasets/validate` (Multipart Form-Data)
- **Request Parameters:**
  - `file`: UploadFile (binary stream)
  - `session_id`: Optional string (defaults to UUID if not supplied)
- **Response Schema (`ValidationResponse`):**
  ```json
  {
    "status": "passed" | "warnings" | "failed",
    "session_id": "sess_123e4567-e89b-12d3-a456-426614174000",
    "filename": "orders.csv",
    "file_size_bytes": 433045,
    "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "is_duplicate": false,
    "existing_dataset_id": null,
    "row_count": 15000,
    "column_count": 4,
    "can_register": true,
    "issues": [
      {
        "code": "MISSING_VALUES",
        "severity": "WARNING",
        "column": "phone_number",
        "affected_count": 5,
        "message": "Column 'phone_number' contains 5 missing values (0.05%).",
        "recommended_action": "Review whether missing phone numbers should be imputed or filtered in queries."
      }
    ],
    "column_profiles": [
      {
        "name": "order_id",
        "inferred_type": "INT",
        "null_count": 0,
        "null_percentage": 0.0,
        "unique_count": 15000,
        "is_unique": true
      }
    ]
  }
  ```

### 3.2 Register Dataset Endpoint
`POST /api/datasets/register` (JSON)
- **Request Body (`RegisterDatasetRequest`):**
  ```json
  {
    "session_id": "sess_123e4567-e89b-12d3-a456-426614174000",
    "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "table_name": "orders"
  }
  ```
- **Response Schema (`RegisteredDatasetResponse`):**
  ```json
  {
    "dataset_id": "ds_987fcdeb-51a2-43f1-b842-123456789abc",
    "session_id": "sess_123e4567-e89b-12d3-a456-426614174000",
    "table_name": "orders",
    "filename": "orders.csv",
    "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "row_count": 15000,
    "column_count": 4,
    "registered_at": "2026-10-20T12:00:00Z"
  }
  ```

---

## 4. Preventing TOCTOU (Time-of-Check to Time-of-Use)
A common vulnerability in web upload workflows is validating an uploaded file and then asking the user to submit it again to register, allowing a malicious actor or network race to substitute the validated file with a payload containing scripts or corrupted data.
- **Solution:** The backend validates file bytes in memory/staging, stores the exact bytes hashed by `SHA-256`, and pins them to `(session_id, content_hash)`.
- When the registration endpoint is called, it registers the *exact staged bytes* that passed validation. No re-upload or byte substitution can occur.
