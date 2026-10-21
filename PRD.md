# PRD.md - Product Requirements Document

## 1. Product Overview
The **Innowhyte Data Analysis Chat** is a web-based analytical platform enabling business analysts, managers, and non-technical stakeholders to upload multiple CSV datasets, inspect data hygiene, and explore insights through a natural language conversational interface. The system delivers mathematically accurate responses paired with dynamic visualizations (charts/graphs) and transparent audit traces.

---

## 2. User Personas & Core Journeys

### Persona A: Financial & Sales Analyst
- **Goal:** Quickly cross-analyze multi-table ecommerce data (orders, payments, line items, customers) without writing manual SQL or Python joins.
- **Workflow:** Uploads 3–8 related CSV files &rarr; Reviews data health & warnings &rarr; Registers datasets &rarr; Asks questions like *"What is the monthly revenue trend for completed payments?"* &rarr; Receives verified metrics and interactive charts with SQL audit logs.

### Persona B: Operations Lead
- **Goal:** Identify logistics bottlenecks and supplier performance.
- **Workflow:** Ingests shipment and supplier tables &rarr; Validates column consistency &rarr; Asks *"Which carrier has the highest delivery delay rate?"* &rarr; Views comparative bar chart.

---

## 3. Functional Requirements

### 3.1 Dataset Ingestion & Validation Pipeline (Current Focus)
- **FR-1.1 File Format & Extension:** Accept `.csv` (and `.xlsx` / `.xls` via standard parsing). Reject unsupported extensions.
- **FR-1.2 File Size & Content Checks:** Enforce maximum upload limit (e.g., 50MB per file). Reject 0-byte files.
- **FR-1.3 Encoding & Parsing:** Auto-detect UTF-8, Latin-1/ISO-8859-1, ASCII, UTF-16. Reject unparseable or corrupted streams.
- **FR-1.4 Script & Formula Injection Defense:** Inspect headers and cell values for formula prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) or script tags (`<script>`, `javascript:`) to prevent CSV injection / XSS.
- **FR-1.5 Raw Header Inspection:**
  - Detect empty column headers (e.g. `col1,,col3`).
  - Detect duplicate column headers (e.g. `id,name,id`).
  - Report exact positions of problematic headers.
- **FR-1.6 Data Quality Profiling (Non-destructive):**
  - Detect fully empty columns (100% null/empty).
  - Detect likely generated index columns (e.g. `Unnamed: 0`, strictly monotonic integers matching row indices).
  - Detect duplicate data rows and report count and percentage.
  - Profile null/missing rates per column.
  - Detect invalid type conversions (e.g., column with 99% integers and 1% alphanumeric strings).
- **FR-1.7 Severity Separation:**
  - **Blocking Errors:** File cannot be safely parsed or registered (malformed CSV, empty file, duplicate header names, script injection).
  - **Non-blocking Warnings:** File is structurally sound but has data quality caveats (missing values, fully empty columns, duplicate rows).
- **FR-1.8 Dataset Identity & Idempotency:**
  - Compute SHA-256 hash of raw file bytes.
  - Scope identity to the active session.
  - If a byte-identical file is uploaded within the same session, idempotently return the existing registration.
  - Generate a unique UUIDv4 for each registered dataset.
  - Prevent TOCTOU (Time-of-Check to Time-of-Use): Registration must guarantee that registered bytes match validated bytes.

### 3.2 Analytical Query Engine (Upcoming Milestone)
- **FR-2.1 In-Memory Relational Engine:** Ingest registered datasets into DuckDB.
- **FR-2.2 Safe Read-Only Execution:** AST validation restricting queries to `SELECT` statements.
- **FR-2.3 Temporal Anchoring:** Anchor relative temporal phrases ("last year", "last 6 months") to the dataset's maximum date (`2024-11-04`).

### 3.3 LLM Semantic & Synthesis Layer (Upcoming Milestone)
- **FR-3.1 LLM Provider:** Groq API (`llama-3.3-70b-versatile` or `mixtral-8x7b-32768`) for low-latency reasoning and SQL planning.
- **FR-3.2 Grounded Synthesis:** Natural language responses must cite figures directly from DuckDB query results.
- **FR-3.3 Chart Generation:** Declarative chart specifications (bar, line, pie, area) returned for frontend rendering.

---

## 4. Non-Functional Requirements
- **Performance:** Dataset validation of 20,000 rows in < 500ms; query execution in < 100ms.
- **Reliability:** 100% deterministic calculations; zero mathematical hallucination.
- **Security:** No arbitrary code execution; formula injection sanitization; API keys isolated via environment variables.
- **Usability:** Actionable error messages indicating row/column location and remediation advice.
