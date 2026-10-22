# Chat-Based-Data-Analysis

### Conversational Data Analysis Platform

An enterprise-grade, conversational data analysis application that allows business stakeholders and data analysts to upload multiple CSV datasets, inspect schema health and hygiene, and explore insights through a natural language interface with grounded narratives, Server-Sent Events (SSE) streaming, executive dashboard visualizations, and strict read-only security guardrails.

---

## Table of Contents
1. [The Problem Statement](#1-the-problem-statement)
   - [Context & Business Need](#11-context--business-need)
   - [Three Fatal Flaws of Traditional Solutions](#12-three-fatal-flaws-of-traditional-solutions)
   - [The Deterministic Solution: Numerical Analysis & Guardrails](#13-the-deterministic-solution-numerical-analysis--guardrails)
2. [How the System Works](#2-how-the-system-works)
   - [High-Level Architecture Diagram](#21-high-level-architecture-diagram)
   - [Subsystem 1: Batch Upload Queue & Resumable Chunked Ingestion](#22-subsystem-1-batch-upload-queue--resumable-chunked-ingestion)
   - [Subsystem 2: Pre-flight Hygiene & Validation](#23-subsystem-2-pre-flight-hygiene--validation)
   - [Subsystem 3: Physical Multi-Tenant DuckDB Catalog](#24-subsystem-3-physical-multi-tenant-duckdb-catalog)
   - [Subsystem 4: Semantic Query Planning & Break Vector Guardrails](#25-subsystem-4-semantic-query-planning--break-vector-guardrails)
   - [Subsystem 5: Server-Sent Events (SSE) Streaming Pipeline](#26-subsystem-5-server-sent-events-sse-streaming-pipeline)
   - [Subsystem 6: Executive Dashboard Card UI & Clean NLP Typography](#27-subsystem-6-executive-dashboard-card-ui--clean-nlp-typography)
   - [Subsystem 7: Grounding Verification, Telemetry & Crash Recovery](#28-subsystem-7-grounding-verification-telemetry--crash-recovery)
3. [Setup & Running the Project](#3-setup--running-the-project)
   - [Prerequisites](#31-prerequisites)
   - [Environment Variables Configuration](#32-environment-variables-configuration)
   - [Step-by-Step Local Setup](#33-step-by-step-local-setup)
   - [Running with Docker & Docker Compose](#34-running-with-docker--docker-compose)
   - [Running Automated Tests](#35-running-automated-tests)
   - [Core API Endpoints Reference](#36-core-api-endpoints-reference)
4. [Libraries Used & Why](#4-libraries-used--why)
   - [Backend Technology Stack](#41-backend-technology-stack)
   - [Frontend Technology Stack](#42-frontend-technology-stack)
   - [Architectural Trade-offs & Rejected Alternatives](#43-architectural-trade-offs--rejected-alternatives)
5. [How Evaluation Could Be Performed](#5-how-evaluation-could-be-performed)
   - [5.1 Numerical Grounding & Hallucination Elimination](#51-numerical-grounding--hallucination-elimination)
   - [5.2 Deterministic Golden Benchmark Suite](#52-deterministic-golden-benchmark-suite)
   - [5.3 Performance & Scalability Benchmarks](#53-performance--scalability-benchmarks)
   - [5.4 Security, Adversarial & Robustness Testing](#54-security-adversarial--robustness-testing)
   - [5.5 UI/UX & Analytical Communication Quality](#55-uiux--analytical-communication-quality)

---

## 1. The Problem Statement

### 1.1 Context & Business Need
In modern enterprises, business stakeholders (executives, product managers, marketing leaders) need rapid, ad-hoc access to data stored in operational CSV files (such as multi-table ecommerce transactions, inventory records, and customer behavior). Traditional business intelligence (BI) pipelines require data engineering bandwidth to build custom ETL pipelines and dashboards for every new inquiry.

Natural language data analysis has emerged as the promise of instant self-service analytics. However, bridging natural language questions to multi-table databases introduces severe technical challenges:
- Cross-table joins with one-to-many fan-out risks (e.g. duplicating order revenues when joining orders to item lines).
- Temporal boundary adherence (e.g. historical datasets anchored to specific past dates, where standard `CURRENT_DATE` queries fail).
- Data privacy and physical multi-tenant isolation.
- Handling large file uploads reliably over unstable internet connections.

### 1.2 Three Fatal Flaws of Traditional Solutions
Most off-the-shelf "chat-with-data" implementations fall into one of three traps:
1. **Arbitrary Code Execution (Security Vulnerability):**
   Many platforms prompt an LLM to generate raw Python code (using Pandas or NumPy) and execute it on the host server via `exec()` or `eval()`. This creates an open Remote Code Execution (RCE) vector, vulnerabilities to environment variable exfiltration, file system tampering, and Denial of Service (DoS) through unbounded memory allocation.
2. **Mathematical Hallucination (Reliability Risk):**
   LLMs are autoregressive next-token predictors trained on probabilistic language distributions, not mathematical reasoning engines. When tasked with calculating aggregations, sums, margins, or counts, LLMs frequently invent plausible-sounding numbers that cannot be verified or reproduced. Business decisions based on hallucinated metrics lead to flawed capital allocation and revenue loss.
3. **Cluttered Markdown & Unformatted Output (User Friction):**
   Standard chat interfaces output raw markdown text, cluttered with unparsed asterisks (`**bold**`), raw pipe tables (`| Col1 | Col2 |`), and harsh database exception stack traces. When users prompt for actions outside the application scope (e.g. asking to delete or edit records), traditional bots either fail with cryptic syntax errors or return mutating code instructions.

### 1.3 The Deterministic Solution: Numerical Analysis & Guardrails
The platform enforces a strict separation of concerns:
- **Zero Arbitrary Code Execution:** Zero Python `exec()` or `eval()`. All analytical calculations are performed inside an embedded, vectorized relational engine (**DuckDB**) using strictly validated, read-only ANSI-SQL (`SELECT` and `WITH` only).
- **100% Deterministic Grounding:** The LLM (Groq `openai/gpt-oss-120b`) is utilized exclusively for semantic query planning (mapping natural language questions to SQL) and grounded narrative summarization. Every figure, percentage, or currency amount cited in the output is cross-referenced against raw DuckDB query results.
- **Strict Read-Only Guardrails & Polite Intent Interception:** Mutating actions (`DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `UPDATE`, `EDIT`, `REMOVE`, `INSERT`) are intercepted before reaching the database, returning a polite apology and helpful guidance on read-only analytical views.
- **Executive Dashboard UI:** The user interface transforms raw tabular output into an executive brief featuring dynamic KPI cards, clean NLP typography, styled dark-mode tables, multi-series Recharts visualizations, and a deterministic Grounding & Claims Audit Tray. Technical SQL code and runtime traces are decoupled from business presentation and captured in backend telemetry.

---

## 2. How the System Works

### 2.1 High-Level Architecture Diagram

```
+-----------------------------------------------------------------------------------------+
|                               Next.js 16 Frontend (TypeScript)                         |
|                                                                                         |
|  +--------------------+   +-----------------------+   +------------------------------+  |
|  | Batch Upload Queue |   |  Data Quality Preview |   | Executive Dashboard Card     |  |
|  | (Multi-file & 5MB) |   |  (Errors & Warnings)  |   | - Executive Overview Box     |  |
|  +--------------------+   +-----------------------+   | - Primary KPI Metric Cards   |  |
|                                                       | - Structured Tabular Table   |  |
|                                                       | - Dynamic Chart (Recharts)   |  |
|                                                       | - Grounding & Claims Audit   |  |
|                                                       +------------------------------+  |
+--------------------------------------------|--------------------------------------------+
                                             | HTTP REST (JSON / Multipart / SSE Stream)
+--------------------------------------------v--------------------------------------------+
|                                  FastAPI Backend (Python 3.13)                          |
|                                                                                         |
|  [ Multi-Tenancy & Authorization ]                                                      |
|  └── X-Tenant-ID Header -> Physical Tenant Isolation (/data/tenants/{tenant_id}/)       |
|                                                                                         |
|  [ Ingestion & Validation Pipeline ]                                                    |
|  ├── BatchQueueService    -> Multi-file drag-drop, atomic batch registration            |
|  ├── ChunkedUploadService -> Resumable 5MB chunks, status recovery, file assembly       |
|  ├── FileValidator        -> Format, Size (1GB), Encoding, Full-stream Injection Check  |
|  ├── SchemaProfiler       -> Raw Headers, Duplicates, Empties, Type Inference           |
|  ├── DataQualityChecker   -> Index Cols, Empty Cols, Duplicate Rows, Mixed Types        |
|  └── DatasetRegistry      -> SHA-256 Hashing, UUID, TOCTOU Prevention, Restart Recovery |
|                                            | Staged -> Registered                       |
|  [ Analytical Engine ]                     v                                            |
|  └── Persistent DuckDB Catalog (Safe ANSI-SQL, Native Fast Cursor Fetch)                |
|                                            ^                                            |
|  [ LLM Orchestration & Guardrails ]        | Validated Read-Only SELECT SQL             |
|  ├── Groq API (openai/gpt-oss-120b)        |                                            |
|  │   ├── Semantic Intent & SQL Planner     |                                            |
|  │   └── Grounded Narrative Synthesizer    |                                            |
|  ├── SQLGuardrails (Break Vector Defenses) |                                            |
|  │   ├── Mutation Intent Interception      -> Polite Generic Refusal & Helpful Guidance |
|  │   ├── Strict Read-Only AST Validation   -> Rejects DROP, DELETE, ALTER, UPDATE       |
|  │   ├── Table Function & Path Blocking    -> Blocks read_csv, read_text, glob          |
|  │   ├── Quote-Aware Semicolon Parsing     -> Allows semicolons inside string literals  |
|  │   └── Memory & Result Clamping          -> LIMIT 1000 & cursor.fetchmany(1001)       |
|  ├── GroundingValidator                    -> Precision Grounding Score & Table Recall  |
|  └── TracingService                        -> JSONL Structured Trace Logging (trace_id) |
+-----------------------------------------------------------------------------------------+
```

### 2.2 Subsystem 1: Batch Upload Queue & Resumable Chunked Ingestion
Uploading large multi-megabyte or gigabyte files over public networks frequently suffers from dropped connections and multi-file coordination friction.
- **Multi-File Selection & Drag-and-Drop:** Users can drag-and-drop multiple CSV files or select batches via native file selection (`<input multiple />`).
- **Visual Ingestion Queue (`CsvUploader.tsx`):** Displays real-time progress for each file in the batch with discrete lifecycle states (`queued`, `uploading`, `validating`, `validated`, `blocked`, `registering`, `registered`, `failed`).
- **Sequential Ingestion Worker:** Processes files sequentially to avoid DuckDB single-writer file lock contention (`Conflicting lock is held`).
- **Atomic Batch Registration (`/api/datasets/register-batch`):** Once all files in the batch pass pre-flight validation, an atomic registration transaction registers them into the tenant DuckDB catalog with cryptographic SHA-256 verification.
- **Client-Side Slicing (Large Files):** Large individual files (>5MB) are sliced into 5MB chunks using `File.slice()`.
- **Initialization (`/api/datasets/upload/init`):** Pre-registers the upload with file size, total chunks, and client metadata.
- **Sequential Chunk Upload (`/api/datasets/upload/chunk`):** Sends chunks labeled with `chunk_index` to disk under `data/tenants/{tenant_id}/chunks/{upload_id}/`.
- **Status Recovery (`/api/datasets/upload/status`):** If a disconnect occurs, the client queries for uploaded chunk indices and resumes from the exact missing slice.
- **Assembly & Verification (`/api/datasets/upload/complete`):** Stitches chunks into a contiguous file, computes SHA-256 digest, and submits to pre-flight validation.

### 2.3 Subsystem 2: Pre-flight Hygiene & Validation
Before uploaded data is registered into DuckDB, it passes through four decoupled validation layers:
1. **File Format & Size Guard:** Ensures the file is non-empty (>0 bytes), contains valid data beyond headers, and remains within the 1GB safety boundary.
2. **Multi-Encoding Resilience:** Probes byte signatures to automatically decode files in `UTF-8`, `Latin-1`, or `Windows CP1252`.
3. **Formula Injection Defense:** Scans string cells for spreadsheet formula triggers (`=`, `+`, `-`, `@`). Malicious commands (e.g. `=cmd|' /C calc'!A0`) are flagged as blocking security errors.
4. **Script & XSS Sanitization:** Rejects CSVs containing unescaped HTML/JavaScript tags (`<script>`).
5. **Schema & Quality Inspection:**
   - *Blocking Errors:* Duplicate column headers, completely empty header names, or unparseable delimiters.
   - *Non-Blocking Warnings:* High missing value percentages (>80%), fully empty columns, likely database index columns (monotonic integers), duplicate data rows, and mixed data types.
6. **TOCTOU Prevention:** Validated files reside in a temporary staging cache. Registration requires matching the cryptographic SHA-256 digest, preventing Time-of-Check to Time-of-Use race conditions.

### 2.4 Subsystem 3: Physical Multi-Tenant DuckDB Catalog
Enterprise environments require strict data segregation between different clients or teams:
- Every API request must pass the `X-Tenant-ID` header (defaulting to `default_tenant`).
- Path traversal attacks (e.g. `../../etc`) are rejected at the authentication layer.
- Each tenant owns a dedicated physical database: `data/tenants/{tenant_id}/catalog.duckdb`.
- Cross-tenant queries are impossible: tables registered in Tenant A cannot be seen, queried, or joined by Tenant B.
- When the backend restarts, the catalog recovers state from the local tenant DuckDB database and metadata JSON records.

### 2.5 Subsystem 4: Semantic Query Planning & Break Vector Guardrails
1. **Schema Introspection:** Dynamically generates DuckDB catalog summaries (table names, column types, row counts, and sample row tuples) to inform the LLM planner.
2. **Temporal & Business Boundary Anchoring:**
   - The ecommerce dataset spans November 5, 2023 through November 4, 2024.
   - The SQL prompt strictly anchors relative queries (e.g. "past 12 months", "last year") to `2024-11-04` rather than `CURRENT_DATE`.
   - Fan-out protection: instructs the planner to avoid running `SUM(orders.total_price)` after joining `orders` with `order_items`.
3. **Read-Only AST Guardrails (`sql_guardrails.py`):**
   - The query must begin with `SELECT` or `WITH`.
   - Prohibits mutating keywords: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`, `PRAGMA`, `GRANT`, `REVOKE`.
   - Automatically appends `LIMIT 500` to unbound queries without aggregations.
4. **Polite Mutation Intent Interception:**
   - If a user prompts: *"delete customer 177"*, *"drop table orders"*, or *"edit the status to completed"*, the intent is caught upfront before query planning.
   - Returns a polite apology explaining the read-only mode and suggesting analytical alternatives (filtering out records, aggregating, comparing). Zero mutating SQL is output.
5. **Real-World Break Vector Hardening:**
   - **Filesystem Exfiltration Defense:** Blocks DuckDB table-producing functions (`read_csv`, `read_text`, `read_parquet`, `read_json`, `glob`, `scan_*`) and direct file path queries in `SQLGuardrails` to prevent host file inspection.
   - **Quote-Aware Semicolon Parsing:** Tokenizes SQL with stateful quote tracking (`'...'` and `"..."`), ensuring valid queries filtering on text containing semicolons or keywords are never falsely rejected.
   - **Memory Exhaustion & Result Clamping:** Hard-clamps queries with excessive limits to `MAX_RESULT_LIMIT = 1000`, enforces automatic limits on `GROUP BY` queries, and bounds DuckDB execution in `llm_service.py` via `cursor.fetchmany(1001)` to prevent memory exhaustion (OOM).
   - **Full-Stream Ingestion Security:** Scans the entire file stream for script tags (`<script>`) and formula commands (`=cmd|...`) past row 500, with expanded `csv.field_size_limit(sys.maxsize)` to safely handle large multi-line text fields.
   - **Table Name Sanitization & Cross-Session Conflict Defense:** Normalizes candidate table names, prefixes SQL reserved keywords (`order`, `group`, `user`), and auto-disambiguates table names across sessions to prevent silent table overwrites.

### 2.6 Subsystem 5: Server-Sent Events (SSE) Streaming Pipeline
Real-time interaction is achieved over HTTP using Server-Sent Events (`POST /api/chat/stream`):
- **Progressive Stage Emission:**
  1. `pipeline_step` &rarr; Emits execution stage names: *"Introspecting catalog..."*, *"Planning SQL with LLM..."*, *"Executing in DuckDB..."*.
  2. `sql` &rarr; Streams the generated and validated read-only SQL query.
  3. `execution` &rarr; Returns query execution latency (ms), row count, tables joined, and preview data.
  4. `chart` &rarr; Emits the dynamic chart specification with resolved data columns.
  5. `token` &rarr; Streams the narrative synthesis tokens progressively as generated by the LLM.
  6. `grounding` &rarr; Streams mathematical precision score, table recall, and feasibility status.
  7. `done` &rarr; Signals complete stream transmission.

### 2.7 Subsystem 6: Executive Dashboard Card UI & Clean NLP Typography
Instead of generic bullet points or raw markdown text, responses are displayed in an executive dashboard format:
- **Card Header Bar:** Displays the Executive Analysis Brief title, request `trace_id`, and a visual `Grounded in DuckDB` verification badge.
- **Executive Overview Box:** Highlights the core analytical synthesis in high-contrast clean typography.
- **Clean NLP Text Renderer:** Uses regex tokenization to transform `**bold**` markdown into styled HTML `<strong>` nodes, removes raw asterisks, eliminates escape backslashes (`\*`), and formats inline code pills.
- **Key Performance Indicator (KPI) Grid:** Displays 1 to 4 metric cards with auto-detected currency formatting (`$XX,XXX.XX`), numeric formatting, and domain icons (revenue, trends, orders, completions).
- **Structured Tabular Breakdown:** Detects markdown pipe tables (`| Month | Total Sales |`), automatically aligns numbers and currencies to the right in emerald green typography, aligns text to the left, and renders trailing footnotes as clean warning captions.
- **Dynamic Multi-Series Charts:** Powered by **Recharts**:
  - Automatically discovers all numeric series columns.
  - Performs client-side and backend auto-pivoting for two-factor groupings (e.g. plotting 2023 vs 2024 side-by-side per product category).
  - Y-axis ticks scale automatically to `$1.0M`, `$500k`, etc.
- **Streaming Viewport Anchoring (UX):** Anchors the chat viewport smoothly to the top of the current message exchange as tokens stream in. This ensures users can read responses from the very first word without disorienting auto-scroll jumps to the bottom.

### 2.8 Subsystem 7: Grounding Verification, Telemetry & Crash Recovery
- **Grounding Evaluation:** Regex extracts all numbers and dollar amounts from the LLM narrative, verifying that each number matches a value in the DuckDB result set within a 3% rounding tolerance.
- **Grounding & Claims Audit Tray:** Positioned at the base of the Executive Dashboard Card, providing:
  - Numerical Grounding Precision score pill (`98% Grounded in Data` / `ShieldCheck`).
  - Table Recall percentage pill (`Table Recall: 100%`).
  - Feasibility status indicator (`Feasible Query`).
  - Interactive Claims Audit toggle (`Audit N Claims`), which expands to inspect individual verified numerical values cited in the narrative and calculation notes.
- **Decoupled Technical Tracing:** Raw DuckDB SQL queries, execution runtimes, row counts, and data preview snapshots are decoupled from the user-facing executive card and logged to structured JSONL trace files via unique `trace_id` for backend observability and auditing.
- **Table Recall:** Evaluates whether the planner joined all necessary tables required to answer the query.
- **Crash Recovery:** Local tenant DuckDB databases and metadata JSON files persist across server restarts, ensuring sessions and datasets remain accessible without re-uploading.

---

## 3. Setup & Running the Project

### 3.1 Prerequisites
- **Python:** 3.11 or higher (Python 3.13 verified)
- **Node.js:** 18.0.0 or higher
- **npm:** 9.0.0 or higher
- (Optional) **Groq API Key:** for live LLM reasoning (the application includes deterministic heuristic fallbacks if no key is provided).

---

### 3.2 Environment Variables Configuration
A template configuration file [`.env.example`](.env.example) is provided in the repository root containing all required keys. Create your local environment file by copying the template:

```bash
cp .env.example .env
```

Populate `.env` with your API credentials and configurations:

```bash
# Groq API Configuration (obtain from https://console.groq.com/keys)
GROQ_API_KEY="your-groq-api-key-here"

# LLM Model Selection (Recommended: openai/gpt-oss-120b)
GROQ_MODEL="openai/gpt-oss-120b"

# Local Storage Directory for DuckDB Catalogs & Chunked Uploads
DATA_DIR="data"
```

---

### 3.3 Step-by-Step Local Setup

#### Step 1: Clone Repository & Set Up Backend
```bash
# From workspace root:
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies:
pip install -r requirements.txt

# Start FastAPI server on port 8000:
uvicorn backend.app.main:app --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger Documentation: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/health`

#### Step 2: Set Up and Start Frontend
In a separate terminal window:
```bash
# Navigate to frontend:
cd frontend

# Install Node dependencies:
npm install

# Start Next.js development server:
npm run dev
```
- Application Web Dashboard: `http://localhost:3000`

---

### 3.4 Running with Docker & Docker Compose
To run the entire system in isolated containers:

```bash
# Export your API key:
export GROQ_API_KEY="your-groq-api-key-here"
export GROQ_MODEL="openai/gpt-oss-120b"

# Build and start services:
docker compose up --build
```
- Frontend UI: `http://localhost:3000`
- Backend API: `http://localhost:8000`

---

### 3.5 Running Automated Tests

#### Backend Test Suite (pytest)
```bash
# Run all 57 automated tests:
.venv/bin/python -m pytest -v tests/
```
**Test Coverage Breakdown (57/57 Passing):**
- `test_break_vectors.py` (14 tests): Filesystem exfiltration blocking, quote-aware semicolon parsing, memory exhaustion & limit clamping, full-stream injection scanning, and cross-session table conflict prevention.
- `test_dataset_api.py` (10 tests): Registration, atomic batch registration (`/register-batch`), zero-byte screening, script injection, deduplication, TOCTOU defense, session listing.
- `test_unauthorized_permissions.py` (2 tests): Mutation intent detection and polite refusal handling.
- `test_chat_query.py` (5 tests): Read-only guardrails, multi-table joins, category sales, geographic grouping.
- `test_chat_stream.py` (1 test): SSE event sequence and live token streaming.
- `test_chunked_upload.py` (1 test): 5MB chunk slicing, status recovery, file assembly.
- `test_data_quality.py` (6 tests): Empty columns, index columns, duplicate rows, missing rates, mixed types.
- `test_file_validator.py` (8 tests): Size bounds (1GB), formula injection, encoding detection.
- `test_grounding_evaluator.py` (3 tests): Precision grounding, hallucination flagging, query feasibility.
- `test_multi_tenancy.py` (2 tests): Physical DuckDB catalog isolation, path traversal rejection.
- `test_persistence.py` (1 test): Persistence across process reboots.
- `test_schema_profiler.py` (4 tests): Header normalization, duplicate headers, empty headers.

#### Frontend Production Build Verification
```bash
cd frontend && npm run build
```
Verifies TypeScript compilation, zero lint warnings, and Next.js page generation.

---

### 3.6 Core API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health check and version status |
| `POST` | `/api/datasets/upload/init` | Initializes a resumable 5MB chunked file upload |
| `POST` | `/api/datasets/upload/chunk` | Uploads an individual 5MB file slice |
| `GET` | `/api/datasets/upload/status` | Returns list of completed chunks for drop recovery |
| `POST` | `/api/datasets/upload/complete` | Assembles chunks, verifies SHA-256, runs hygiene validation |
| `POST` | `/api/datasets/validate` | Pre-flight validation on uploaded CSV bytes |
| `POST` | `/api/datasets/register` | Registers validated staged dataset into DuckDB catalog |
| `POST` | `/api/datasets/register-batch` | Atomically registers multiple validated datasets into DuckDB catalog |
| `GET` | `/api/datasets/sessions/{session_id}` | Lists all registered tables and schemas in session |
| `POST` | `/api/datasets/load-sample` | Preloads 8 ecommerce CSV tables into tenant catalog |
| `POST` | `/api/chat` | Synchronous analytical query execution |
| `POST` | `/api/chat/stream` | Server-Sent Events (SSE) streaming endpoint |

---

## 4. Libraries Used & Why

### 4.1 Backend Technology Stack

| Library / Tool | Version | Role in Architecture | Technical Rationale |
|---|---|---|---|
| **FastAPI** | `^0.115` | Core API Framework | High-performance asynchronous I/O, native streaming responses (`StreamingResponse` for SSE), auto-generated OpenAPI documentation, and native dependency injection for multi-tenancy scoping. |
| **DuckDB** | `^1.1` | Relational Analytical Engine | Embedded columnar database engine. Executes standard ANSI-SQL with vectorized SIMD parallelism. Reads CSVs and queries multi-million-row joins in sub-second times with zero Pandas overhead. Completely eliminates the need for Python `exec()` or `eval()`. |
| **Groq Python SDK** | `^0.11` | LLM Inference Client | Delivers ultra-low inference latency (>250 tokens/sec), essential for interactive streaming. Supports modern open models such as `openai/gpt-oss-120b` with deterministic JSON mode. |
| **Pydantic** | `^2.10` | Data Validation & Schemas | Strict type contracts for API requests, chart specifications, and error models. Guarantees deterministic serialization and JSON schema enforcement. |
| **python-multipart** | `^0.0.12` | Multipart Ingestion | Enables memory-efficient chunked streaming of file uploads without loading full payloads into RAM. |
| **pytest & HTTPX** | `^8.3` / `^0.28` | Automated Regression Suite | Asynchronous test client capable of testing SSE streams, file uploads, and DuckDB catalog state with tenant isolation. |

### 4.2 Frontend Technology Stack

| Library / Tool | Version | Role in Architecture | Technical Rationale |
|---|---|---|---|
| **Next.js** | `16.4 (App Router)` | Frontend Web Framework | Fast React Server/Client component architecture, built-in Turbopack bundler for rapid compilation, and native optimization. |
| **TypeScript** | `^5.0` | Type Safety | Enforces typed data contracts matching backend Pydantic models for chat messages, chart specs, and validation preview errors. |
| **TailwindCSS** | `^3.4` | Styling & Design System | High-performance styling with zero runtime overhead. Enables custom dark-mode tokens, glassmorphic card overlays, and responsive mobile layouts. |
| **Recharts** | `^2.15` | Data Visualization | Declarative React SVG charting library. Supports responsive containers, grouped multi-series bar charts, time-series lines, and custom tooltips. |
| **Lucide React** | `^0.475` | Iconography | Lightweight, consistent SVG icon set for dashboard cards, table status, and execution metrics. |

### 4.3 Architectural Trade-offs & Rejected Alternatives

1. **DuckDB vs. Pandas / SQLite:**
   - *Rejected Alternative:* Performing analysis by generating Pandas dataframe code (`df.groupby().sum()`) and executing it via `exec()`.
   - *Why Rejected:* Introducing `exec()` creates an unmitigated Remote Code Execution (RCE) vulnerability. Furthermore, Pandas relies on single-threaded Python execution and suffers from high memory bloat on multi-file joins.
   - *Why DuckDB Won:* DuckDB uses vectorized columnar execution in C++, natively joins multiple relational tables using standard ANSI-SQL, and operates safely in read-only mode without code execution vulnerabilities.
2. **Server-Sent Events (SSE) vs. WebSockets:**
   - *Rejected Alternative:* WebSockets (`ws://`).
   - *Why Rejected:* WebSockets require stateful connection negotiation, custom ping/pong heartbeats, and complex proxy configuration.
   - *Why SSE Won:* SSE operates over standard HTTP/1.1 and HTTP/2, works seamlessly through corporate proxies, provides native reconnection capabilities, and matches the unidirectional flow of LLM streaming (client sends query, server streams progression).
3. **Chunked Resumable Uploads vs. Single Multipart Request:**
   - *Rejected Alternative:* Standard single-request file upload (`POST /upload` with 500MB payload).
   - *Why Rejected:* A single transient network failure at 95% completion forces the user to restart from 0%, leading to poor reliability for large enterprise datasets.
   - *Why Chunking Won:* Slicing into 5MB chunks provides fine-grained progress feedback, network drop recovery, and bounded memory utilization.

---

## 5. How Evaluation Could Be Performed

In an enterprise conversational analytics deployment, system performance must be evaluated across five distinct dimensions:

### 5.1 Numerical Grounding & Hallucination Elimination
To ensure business stakeholders never receive fabricated metrics:
1. **Mathematical Grounding Score ($Precision_{grounding}$):**
   - Automatically regex-extract every numerical figure, percentage, and currency value cited in the LLM's natural language response.
   - Cross-reference each extracted value against the raw numeric cells returned by the DuckDB SQL execution.
   - Allow a narrow 3% tolerance for human-friendly rounding shorthand (e.g. matching `$18.13M` to `$18,129,566.24`).
   - Flag any cited number that cannot be mathematically mapped to a DuckDB result as a hallucination.
   - **Target Metric:** $Precision_{grounding} \ge 98\%$.
2. **Table Recall ($Recall@k$):**
   - Measure the proportion of ground-truth tables required to answer the query that were correctly identified and joined by the planner.
   - **Target Metric:** $Recall \ge 95\%$.
3. **Query Feasibility Pre-Screening:**
   - Check user query entities against the active catalog schema before SQL planning to reject unanswerable inquiries (e.g. asking for "weather patterns" on an ecommerce database) with clear explanations rather than speculative queries.

### 5.2 Deterministic Golden Benchmark Suite
Build an automated benchmark pipeline consisting of 50+ curated analytical queries:
1. **Benchmark Curation:** Define queries spanning single-table aggregations, multi-table joins, temporal boundaries, and categorical rankings.
2. **Ground-Truth SQL Execution:** Pair each test question with human-verified golden SQL and expected record counts.
3. **Automated Continuous Evaluation (CI/CD):**
   - In CI/CD runs, execute model-generated SQL against golden SQL on a test database.
   - Assert equality of result tables (row counts, column values, and order).
   - Compute pass rate percentage to prevent regression across model prompt updates.

### 5.3 Performance & Scalability Benchmarks
1. **Vectorized Columnar Latency:**
   - Benchmark DuckDB query response time across scaling record volumes:
     - 10,000 rows: target latency $< 50\text{ ms}$
     - 100,000 rows: target latency $< 150\text{ ms}$
     - 1,000,000 rows: target latency $< 500\text{ ms}$
2. **Native Cursor Record Iteration:**
   - Measure memory overhead when fetching query results. Native Python tuple fetching avoids data duplication and ensures flat memory profiles during high concurrency.
3. **Chunked Upload Throughput:**
   - Benchmark upload assembly speed and memory consumption during 50MB, 200MB, and 1GB file ingestion.

### 5.4 Security, Adversarial & Robustness Testing
1. **Mutation Intent Refusal Rate:**
   - Test suite of 100+ adversarial user prompts attempting to alter data (`DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `UPDATE`, `EDIT`, `REMOVE`, `INSERT`).
   - **Requirement:** 100% refusal rate with zero mutating SQL generated or executed.
2. **CSV Formula Injection Screening:**
   - Inject spreadsheet command payloads into cells (`=cmd|' /C calc'!A0`, `@SUM(...)`, `+1+1`).
   - Verify that all formula characters at the start of string cells are rejected or sanitized.
3. **SQL Injection AST Bounding:**
   - Attempt multi-statement semicolon injections (e.g. `' OR 1=1; DROP TABLE orders; SELECT '`).
   - Verify that AST validation catches statement chaining and throws security guardrail rejections.
4. **Tenant Isolation Verification:**
   - Issue queries with forged tenant IDs or path traversal tokens (`X-Tenant-ID: ../../system`).
   - Verify immediate 400 rejection and physical database segregation.

### 5.5 UI/UX & Analytical Communication Quality
1. **Clean NLP Typography Rate:**
   - Verify that 0% of executive briefings display raw markdown artifacts (`**Text**`, `### 1.`, `\*`).
2. **Tabular Formatting Accuracy:**
   - Verify that tabular data is correctly detected, aligned (numbers right, text left), and paired with clean footnote caveats.
3. **Multi-Series Chart Adaptability:**
   - Verify that comparison queries (e.g. 2023 vs 2024) dynamically render multi-bar grouped charts with matching legends and scaled Y-axes.
