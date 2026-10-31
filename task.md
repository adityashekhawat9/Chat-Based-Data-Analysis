# Task Checklist & Progress Log

## Project: Conversational Data Analysis Chat

### Milestone 1: Discovery & Planning
- [x] Inspect all 8 CSV files in `Online Shop 2024` (59,206 rows).
- [x] Verify referential integrity, cardinalities, date bounds, and revenue discrepancies.
- [x] Create core documentation artifacts (`AGENTS.md`, `PRD.md`, `docs/architecture.md`, `docs/decisions.md`, `implementation.md`, `task.md`).

### Milestone 2: CSV Upload Validation & Dataset Identity
- [x] Move `Online Shop 2024` into workspace under `data/` and update `.gitignore`.
- [x] Module 1: `FileValidator` (format, 1GB size limit, multi-encoding, script & formula injection defense).
- [x] Module 2: `SchemaProfiler` (raw headers, duplicate columns, empty headers, type inference).
- [x] Module 3: `DataQualityChecker` (empty columns, index columns, duplicate rows, missing rates, mixed types).
- [x] Module 4: `DatasetRegistry` (persistent DuckDB catalog, SHA-256 hash, UUID, TOCTOU staging cache).
- [x] Module 5: `ChunkedUploadService` (resumable 5MB multipart chunks, status recovery, file assembly).
- [x] REST API endpoints (`/api/datasets/validate`, `/api/datasets/register`, `/api/datasets/upload/*`, `/api/datasets/sessions/{session_id}`).
- [x] Next.js frontend validation preview with drag-and-drop (`CsvUploader.tsx`, `DatasetValidationPreview.tsx`).

### Milestone 3: Analytical Query Engine & SQL Guardrails
- [x] Columnar DuckDB query execution with native tuple cursor fetching.
- [x] AST SQL guardrails: strict read-only validation (rejects `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, multi-statement chaining).
- [x] Dynamic schema introspector with dataset date boundary anchoring (`2024-11-04`).
- [x] Groq LLM integration (`llama-3.3-70b-versatile`) with self-correction retry loop and deterministic heuristic fallback.
- [x] Preload sample dataset endpoint (`POST /api/datasets/load-sample`).
- [x] Declarative chart generator (Line, Bar, Pie, Area) rendered with Recharts.

### Milestone 4: Multi-Tenancy, SSE Streaming & Grounding Evaluation
- [x] Physical Multi-Tenancy database isolation (`data/tenants/{tenant_id}/catalog.duckdb` and `X-Tenant-ID` header).
- [x] Crash & Restart recovery (persisting session state and DuckDB catalog locally to survive server reboots).
- [x] Server-Sent Events (SSE) streaming (`POST /api/chat/stream`) with real-time pipeline steps and token streaming (`useChatStream.ts`).
- [x] Traceability & Grounding evaluation ($Precision_{grounding}$ for numerical claims, Table Recall, feasibility checks, unique `trace_id` with JSONL spans).
- [x] Resumable chunked upload UI in `CsvUploader.tsx` (5MB slices, progress bar, pause/resume on network drop).
- [x] Tenant switcher UI in `page.tsx` (`default_tenant`, `tenant_alpha`, `tenant_beta`, custom tenant).
- [x] Grounding audit badge and verified claims inspector in `ChatInterface.tsx`.

### Milestone 6: Executive Dashboard Layout & openai/gpt-oss-120b Integration
- [x] Integrate LLM model `openai/gpt-oss-120b` via Groq client with dynamic SQL planning and narrative streaming.
- [x] Build `ExecutiveDashboardCard.tsx` layout component with KPI metric cards, executive overview callout, structured insight cards, and integrated audit tools.
- [x] Verify live end-to-end workflow on running server (planned SQL, DuckDB execution, token streaming, chart rendering).
- [x] Confirm all 40 automated tests pass and frontend builds with 0 errors.

### Milestone 7: Unauthorized Permissions & NLP UI Formatting
- [x] Intercept unauthorized mutation intents (`DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `UPDATE`, `EDIT`, `REMOVE`) with polite apologies and helpful guidance on read-only capabilities (zero mutating SQL generated or executed).
- [x] Modern NLP Clean Text Formatting (`renderCleanFormattedText` in `ExecutiveDashboardCard.tsx`): convert `**Text**` into clean bold tags, eliminate literal markdown asterisks, strip header hashes (`### 1.`) and escape backslashes (`\*`).
- [x] Structured Tabular Breakdown Component: automatically detect markdown pipe tables (`| Header | Header |`) and render styled dark-mode HTML tables with right-aligned currencies/numbers, alternating hover rows, and clean footnote captions.
- [x] Comprehensive `README.md` update covering setup, architecture, security guardrails, multi-tenancy, and evaluation.
- [x] Verify complete test suite (42 passed, 0 failed in 57.2s).

### Milestone 8: Multi-File Selection & Batch Upload Queue
- [x] Multi-file selection (`<input multiple />`) and batch drag-and-drop ingestion (`CsvUploader.tsx`).
- [x] Visual batch ingestion queue dashboard with per-item progress, status pills (`queued`, `uploading`, `validating`, `validated`, `blocked`, `registering`, `registered`, `failed`), and retry/inspection controls.
- [x] Backend batch registration endpoint (`POST /api/datasets/register-batch`) with TOCTOU content hash verification and atomic catalog commit.
- [x] Sequential queue processor preventing DuckDB single-writer file lock contention (`Conflicting lock is held`).
- [x] Full documentation update in `implementation.md` (Sections 4 & 5).

### Milestone 9: Real-World Break Vectors Hardening & Comprehensive Testing
- [x] **Break Vector 1: Filesystem Exfiltration Defense:** Block DuckDB file table functions (`read_csv`, `read_text`, `read_parquet`, `read_json`, `glob`, `scan_*`) and direct filesystem path queries in `SQLGuardrails`.
- [x] **Break Vector 2: Quote-Aware Semicolon Parsing:** Eliminate false-positive query rejections on valid data filters containing semicolons or keywords within quotes (`'...'` or `"..."`).
- [x] **Break Vector 3: Memory Exhaustion & Result Clamping:** Hard clamp queries with excessive limits (down to `MAX_RESULT_LIMIT = 1000`), enforce limits on `GROUP BY` queries, and use bounded `cursor.fetchmany(1001)` in `llm_service.py` to prevent OOM.
- [x] **Break Vector 4: Comprehensive Ingestion Security:** Expand `csv.field_size_limit(sys.maxsize)` and scan the complete file stream for script tags (`<script>`) and formula commands (`=cmd|...`) past row 500.
- [x] **Break Vector 5: Table Name Sanitization & Cross-Session Overwrite Prevention:** Sanitize candidate table names, prefix SQL reserved keywords (`order`, `group`, `user`), and auto-disambiguate table names across sessions to prevent silent table overwrites.
- [x] **Automated Test Suite:** Created `tests/test_break_vectors.py` with 14 targeted unit/integration tests covering all 5 break vectors (all passed).

### Milestone 10: UI Streamlining & Non-Breaking Content Refinement
- [x] Removed **Analytical Takeaways & Breakdown** cards section from `frontend/src/components/ExecutiveDashboardCard.tsx` (previously Section 3).
- [x] Removed **Hide SQL & Execution Trace** drawer section from `frontend/src/components/ExecutiveDashboardCard.tsx` (previously Section 7).
- [x] Removed floating **Jump to latest** button and scroll handlers from `frontend/src/components/ChatInterface.tsx` to eliminate UI obstruction and overlap.
- [x] Verified zero breakage of Executive Overview, KPI cards, Tabular Breakdown, dynamic Recharts chart, Grounding badges, TypeScript types, and Next.js production build (`npm run build`).

### Milestone 11: Comprehensive README Documentation Sync
- [x] Updated Table of Contents and section anchor links in `README.md`.
- [x] Documented the dedicated Grounding Verification & Claims Audit Tray (`Audit N Claims`) and header verification badge.
- [x] Documented the decoupling of technical DuckDB SQL execution traces to backend structured JSONL telemetry (`trace_id`).
- [x] Documented the Multi-File Batch Ingestion Queue (`POST /api/datasets/register-batch`), sequential worker, and status states.
- [x] Documented the 5 real-world Break Vector defenses in Subsystem 4.
- [x] Synchronized test coverage breakdown to all 57 automated tests across 12 test modules.

### Milestone 12: NLP Semantic Security Hardening & Vulnerability Remediation
- [x] **Threat Modeling & Hardening Architecture:** Modeled 8 real-world query vulnerability vectors (V1-V8) including semantic intent evasion, false-positive analytical interrogatives, direct prompt injection, DuckDB system exfiltration, ReDoS/DoS buffer flooding, indirect stored-data injection, verbose error disclosure, and date/time grounding imprecision.
- [x] **spaCy Dependency & Pipeline Integration:** Integrated spaCy NLP engine (`en_core_web_sm` / `spacy.blank("en")` fallback) in `backend/app/query/nlp_guardrails.py` with singleton model management.
- [x] **Vector 1 & 2: Semantic Intent Classification & Voice Analysis:** Replaced brittle regex with lemma-based dependency parsing over 28 destructive action lemmas. Analyzed grammatical voice (`auxpass`), adjectival participle clauses (`acl`, `amod`), and interrogative cues (`which`, `what`, `how many`, `show`, `list`) to distinguish actual destructive intent from legitimate historical queries.
- [x] **Vector 3: Prompt Injection Defense & Sandboxing:** Implemented pre-flight pattern screening against system overrides and jailbreaks (`DAN mode`, `developer mode`, system prompt leakage), coupled with XML prompt sandboxing (`<active_database_schema>`, `<untrusted_user_query>`, etc.) in `prompt_builder.py`.
- [x] **Vector 4: DuckDB Internal System & Metadata Protection:** Blocked all internal functions and pragmas (`duckdb_*`, `pragma_*`, `current_setting`, `current_user`) in `sql_guardrails.py` to prevent environment exfiltration.
- [x] **Vector 5: Buffer Flooding & ReDoS Prevention:** Implemented 1,000-character input length boundaries and DuckDB `statement_timeout = '15s'` against complex execution DoS.
- [x] **Vector 6 & 7: Stored-Data Boundary Sandboxing & Error Sanitization:** Sanitized database exceptions to scrub host filesystem paths, Python traceback lines, and hexadecimal memory addresses before returning to users.
- [x] **Vector 8: Semantic Entity Recognition in Grounding:** Leveraged spaCy NER to isolate `DATE` and `TIME` entities in narratives, preventing false-positive hallucination penalties on calendar years in `grounding_evaluator.py`.
- [x] **Comprehensive Automated Test Suite:** Created `tests/test_nlp_security.py` with 38 unit and integration tests covering all 8 threat vectors (100% passing).
- [x] **Full Regression Verification:** Verified entire test suite (95 passed, 0 failed in 73.2s) and Next.js production build (`npm run build`).

---

## Executed Verification & Test Status

### Backend Automated Test Suite
- **Command:** `PYTHONPATH=. .venv/bin/pytest tests/`
- **Result:** **95 passed** across 13 test suites (100% pass rate)
- **Verified Suites:**
  1. `tests/test_break_vectors.py` (14 passed)
  2. `tests/test_chat_query.py` (5 passed)
  3. `tests/test_chat_stream.py` (1 passed)
  4. `tests/test_chunked_upload.py` (1 passed)
  5. `tests/test_data_quality.py` (6 passed)
  6. `tests/test_dataset_api.py` (10 passed)
  7. `tests/test_file_validator.py` (8 passed)
  8. `tests/test_grounding_evaluator.py` (3 passed)
  9. `tests/test_multi_tenancy.py` (2 passed)
  10. `tests/test_nlp_security.py` (38 passed)
  11. `tests/test_persistence.py` (1 passed)
  12. `tests/test_schema_profiler.py` (4 passed)
  13. `tests/test_unauthorized_permissions.py` (2 passed)

### Frontend Production Build
- **Command:** `npm run build` in `frontend/`
- **Result:** **Compiled successfully** in 1.8s (0 lint errors, 0 type errors, static pages generated).

