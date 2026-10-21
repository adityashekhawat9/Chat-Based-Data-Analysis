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

---

## Executed Verification & Test Status

### Backend Automated Test Suite
- **Command:** `.venv/bin/python -m pytest -v tests/`
- **Result:** **42 passed, 0 failed** in 57.20s
- **Verified Scenarios:**
  1. `test_sql_guardrails_read_only` (PASSED)
  2. `test_chat_without_datasets` (PASSED)
  3. `test_load_sample_dataset_and_chat_monthly_trend` (PASSED)
  4. `test_chat_cross_table_category_sales` (PASSED)
  5. `test_chat_geographic_distribution` (PASSED)
  6. `test_chat_stream_sse_flow` (PASSED)
  7. `test_chunked_resumable_upload_flow` (PASSED)
  8. `test_clean_data_no_warnings` (PASSED)
  9. `test_fully_empty_column` (PASSED)
  10. `test_likely_index_column` (PASSED)
  11. `test_duplicate_rows` (PASSED)
  12. `test_high_missing_rate` (PASSED)
  13. `test_mixed_types` (PASSED)
  14. `test_validate_and_register_valid_csv` (PASSED)
  15. `test_validate_zero_byte_file` (PASSED)
  16. `test_validate_script_injection` (PASSED)
  17. `test_identical_content_uploaded_under_different_filenames` (PASSED)
  18. `test_different_content_uploaded_under_same_filename` (PASSED)
  19. `test_repeated_registration_within_session` (PASSED)
  20. `test_attempts_to_register_rejected_dataset` (PASSED)
  21. `test_toctou_prevention_unknown_hash` (PASSED)
  22. `test_session_datasets_listing` (PASSED)
  23. `test_valid_csv` (PASSED)
  24. `test_zero_byte_empty_file` (PASSED)
  25. `test_header_only_file` (PASSED)
  26. `test_file_size_limit` (PASSED)
  27. `test_unsupported_format` (PASSED)
  28. `test_invalid_encoding` (PASSED)
  29. `test_script_tag_injection` (PASSED)
  30. `test_formula_injection` (PASSED)
  31. `test_grounding_precision_fully_grounded` (PASSED)
  32. `test_grounding_precision_hallucinated_claim` (PASSED)
  33. `test_feasibility_check` (PASSED)
  34. `test_multi_tenant_isolation` (PASSED)
  35. `test_tenant_id_traversal_rejection` (PASSED)
  36. `test_duckdb_and_metadata_persistence_across_restart` (PASSED)
  37. `test_valid_schema` (PASSED)
  38. `test_empty_column_header` (PASSED)
  39. `test_duplicate_column_headers` (PASSED)
  40. `test_identifier_normalization` (PASSED)
  41. `test_mutation_intent_regex_coverage` (PASSED)
  42. `test_api_chat_returns_polite_refusal_for_mutations` (PASSED)
  43. `test_break_vector_1_read_csv_table_function_blocked` (PASSED)
  44. `test_break_vector_1_read_text_and_glob_blocked` (PASSED)
  45. `test_break_vector_2_semicolon_inside_string_literal_allowed` (PASSED)
  46. `test_break_vector_2_mutating_keyword_inside_string_literal_allowed` (PASSED)
  47. `test_break_vector_2_actual_multiple_statements_still_blocked` (PASSED)
  48. `test_break_vector_3_massive_limit_clamped` (PASSED)
  49. `test_break_vector_3_group_by_auto_limit` (PASSED)
  50. `test_break_vector_3_scalar_count_preserved` (PASSED)
  51. `test_break_vector_3_fetchmany_bounds_memory` (PASSED)
  52. `test_break_vector_4_script_injection_on_row_501_blocked` (PASSED)
  53. `test_break_vector_4_formula_injection_on_row_600_blocked` (PASSED)
  54. `test_break_vector_4_large_csv_field_does_not_crash` (PASSED)
  55. `test_break_vector_5_reserved_sql_keywords_sanitized` (PASSED)
  56. `test_break_vector_5_cross_session_table_overwrite_prevented` (PASSED)

### Frontend Production Build
- **Command:** `npm run build` in `frontend/`
- **Result:** **Compiled successfully** in 1.8s (0 lint errors, 0 type errors, static pages generated).

