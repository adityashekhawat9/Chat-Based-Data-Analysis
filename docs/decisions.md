# Architecture Decision Records (ADRs)

## ADR-001: Deterministic DuckDB Execution Engine vs Unsafe Python `exec()`
- **Status:** Accepted
- **Context:** Chat-based data analysis tools often generate ad-hoc Python snippets and execute them using `exec()` or `eval()`.
- **Decision:** We strictly adopt DuckDB as the in-memory analytical query engine. The LLM translates user queries to standard ANSI SQL (`SELECT` statements), which are parsed and validated before deterministic execution.
- **Consequences:** Eliminates arbitrary code execution vulnerabilities, prevents non-deterministic mathematical hallucinations, and yields millisecond-level query performance on multi-table joins.

---

## ADR-002: Two-Phase Upload (Validate & Stage &rarr; Register)
- **Status:** Accepted
- **Context:** Uploaded files must be validated for structure, scripts, and quality before entering the query engine, while avoiding race conditions or byte substitutions (TOCTOU).
- **Decision:** Split upload into:
  1. `POST /api/datasets/validate`: Validates bytes, checks idempotency via SHA-256, generates issue reports, and stages valid bytes in a session-keyed cache.
  2. `POST /api/datasets/register`: Accepts registration for a staged, validated hash, commits it to DuckDB, and assigns a UUIDv4 dataset ID.
- **Consequences:** Prevents unvalidated or rejected datasets from ever touching DuckDB or the query engine. Guarantees byte immutability between validation and registration.

---

## ADR-003: SHA-256 Content-Based Idempotency Scoped by Session
- **Status:** Accepted
- **Context:** Users may accidentally drag-and-drop the same file multiple times or retry interrupted network uploads.
- **Decision:** Every uploaded payload has its SHA-256 digest computed immediately. If the digest matches an already registered dataset within the session, the registry returns the existing dataset identity with status `is_duplicate: true` rather than registering redundant tables.
- **Consequences:** Prevents wasted memory and avoids polluting DuckDB with redundant or duplicate tables.

---

## ADR-004: Groq API with Llama 3.3 70B for LLM Semantic Layer
- **Status:** Accepted
- **Context:** The system needs fast, reliable semantic parsing and grounded text synthesis without hardcoding credentials or incurring high latency.
- **Decision:** Use Groq API (`llama-3.3-70b-versatile`) via provider environment variables (`GROQ_API_KEY`). Groq delivers >250 tokens/sec inference, minimizing end-to-end chat latency.
- **Consequences:** High response speed, zero hardcoded credentials, clean fallback support.
