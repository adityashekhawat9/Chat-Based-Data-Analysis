# AGENTS.md - Developer & Agent Operating Guidelines

This document governs the engineering standards, safety guardrails, and architectural conventions for developers and autonomous agents working on the Innowhyte Data Analysis Chat application.

## 1. Core Operating Principles

1. **Deterministic Numerical Computation:**
   - Never rely on an LLM to perform mathematical calculations or generate raw aggregate figures.
   - All arithmetic, aggregations, counts, and joins must be computed deterministically using standard relational engines (DuckDB / Pandas).
   - The LLM is strictly used for semantic intent understanding, query planning (SQL generation), and contextual narrative synthesis grounded in deterministic query results.

2. **Security & Zero Arbitrary Code Execution:**
   - **Never** execute arbitrary LLM-generated Python code using `exec()` or `eval()`.
   - All analytical operations must be executed as parameterized or syntax-validated read-only SQL queries (`SELECT` statements only).
   - Script injection vectors (e.g. CSV formula injection starting with `=`, `+`, `-`, `@`, embedded HTML/JS tags `<script>`) must be detected and sanitized during ingestion.

3. **Data Integrity & Non-Destructive Ingestion:**
   - Never silently drop or impute rows or columns during file upload.
   - Distinguish between **blocking errors** (malformed CSV, unsupported encoding, empty file, duplicate header names, script injection) and **non-blocking warnings** (missing values, fully empty columns, high null percentage, duplicate data rows).
   - Always report issues transparently to the user with actionable codes, affected columns, and remediation advice.

4. **Dataset Identity & Idempotent Ingestion:**
   - Each registered dataset must have an assigned `dataset_id` (UUIDv4) and a computed `content_hash` (SHA-256).
   - Duplicate uploads of byte-identical files within the same session must be idempotent—returning the existing dataset registration without duplicating storage or catalog state.
   - Prevent Time-of-Check to Time-of-Use (TOCTOU) issues by staging validated bytes in a secure session cache and verifying the content hash upon registration.

5. **Modularity & Separation of Concerns:**
   - Keep file validation, schema profiling, data-quality inspection, and dataset registration in strictly separate, decoupled Python modules.
   - Adhere to clean typed interfaces using Pydantic models for all API inputs and outputs.

6. **Environment & Secrets:**
   - Never commit API keys or credentials.
   - Use environment variables (e.g. `GROQ_API_KEY`) loaded via standard configurations.

7. **Documentation & Testing Discipline:**
   - Maintain `task.md` with honest, executed test statuses.
   - Never declare a feature or test passed without executing actual tests in the terminal.
