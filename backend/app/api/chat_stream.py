import json
import asyncio
import time
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.app.models.chat import ChatRequest, ChatMessage
from backend.app.auth.tenant import get_current_tenant
from backend.app.api.datasets import registry
from backend.app.api.chat import llm_service
from backend.app.tracing.tracer import TracingService
from backend.app.tracing.grounding_evaluator import GroundingValidator
from backend.app.query.prompt_builder import PromptBuilder
from backend.app.query.sql_guardrails import SQLGuardrails, SQLGuardrailError, MUTATION_REFUSAL_MESSAGE
from backend.app.query.nlp_guardrails import NLPGuardrails, PROMPT_INJECTION_REFUSAL_MESSAGE

router = APIRouter(prefix="/api", tags=["chat_stream"])
tracer = TracingService()

@router.post("/chat/stream")
async def chat_stream_endpoint(
    req: ChatRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Server-Sent Events (SSE) streaming endpoint for conversational data analysis.
    Streams execution stages, generated SQL, execution metrics, live chart specs,
    tokens of the grounded narrative, and grounding evaluation metrics.
    """
    if not req.message or not req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    # 1. Guard against buffer flooding / ReDoS (V5)
    try:
        NLPGuardrails.validate_message_length(req.message)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )

    # 2. Check for prompt injection / jailbreak attempts upfront (V3)
    is_injection, injection_refusal = NLPGuardrails.detect_prompt_injection(req.message)
    if is_injection:
        trace = tracer.create_trace(tenant_id=tenant_id, session_id=req.session_id, operation="prompt_injection_refusal")
        async def injection_stream() -> AsyncGenerator[str, None]:
            trace.start_span("security_screening")
            yield _format_sse("pipeline_step", {
                "step": "security_screening",
                "message": "Screening analytical request for safety & operational scope...",
                "trace_id": trace.trace_id,
            })
            await asyncio.sleep(0.02)
            trace.end_span("security_screening", status="success")

            refusal_text = injection_refusal or PROMPT_INJECTION_REFUSAL_MESSAGE
            words = refusal_text.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                yield _format_sse("token", {"token": token, "trace_id": trace.trace_id})
                await asyncio.sleep(0.01)

            yield _format_sse("grounding", {
                "grounding_precision": 1.0,
                "hallucination_detected": False,
                "table_recall": 1.0,
                "trace_id": trace.trace_id,
            })
            yield _format_sse("done", {"trace_id": trace.trace_id})

        return StreamingResponse(injection_stream(), media_type="text/event-stream")

    # 3. Check for unauthorized mutation/deletion intent upfront (V1 & V2)
    if SQLGuardrails.is_mutation_intent(req.message):
        trace = tracer.create_trace(tenant_id=tenant_id, session_id=req.session_id, operation="permission_refusal")
        async def refusal_stream() -> AsyncGenerator[str, None]:
            trace.start_span("permissions_check")
            yield _format_sse("pipeline_step", {
                "step": "permissions_check",
                "message": "Checking query permissions & operational scope...",
                "trace_id": trace.trace_id,
            })
            await asyncio.sleep(0.02)
            trace.end_span("permissions_check", status="success")

            words = MUTATION_REFUSAL_MESSAGE.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                yield _format_sse("token", {"token": token, "trace_id": trace.trace_id})
                await asyncio.sleep(0.01)

            yield _format_sse("grounding", {
                "grounding_precision": 1.0,
                "hallucination_detected": False,
                "table_recall": 1.0,
                "trace_id": trace.trace_id,
            })
            yield _format_sse("done", {"trace_id": trace.trace_id})

        return StreamingResponse(refusal_stream(), media_type="text/event-stream")

    # Resolve tenant's isolated DuckDB connection
    conn = registry.get_tenant_duckdb(tenant_id)
    trace = tracer.create_trace(tenant_id=tenant_id, session_id=req.session_id, operation="chat_stream")

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # 1. Pipeline step: Catalog schema introspection
            trace.start_span("schema_introspection")
            yield _format_sse("pipeline_step", {
                "step": "schema_introspection",
                "message": "Introspecting tenant DuckDB catalog...",
                "trace_id": trace.trace_id,
            })
            await asyncio.sleep(0.01)

            catalog_schema = PromptBuilder.get_catalog_schema(conn)
            trace.end_span("schema_introspection", status="success")

            if "No tables currently registered" in catalog_schema:
                yield _format_sse("error", {
                    "message": "No tables registered in this tenant catalog. Upload a CSV or load the sample dataset to begin.",
                    "trace_id": trace.trace_id,
                })
                yield _format_sse("done", {"trace_id": trace.trace_id})
                return

            # 2. Pipeline step: SQL Generation
            trace.start_span("sql_generation")
            yield _format_sse("pipeline_step", {
                "step": "sql_generation",
                "message": "Planning deterministic SQL query with LLM...",
                "trace_id": trace.trace_id,
            })
            await asyncio.sleep(0.01)

            sql_plan = llm_service._generate_sql_plan(req.message, catalog_schema, req.history)
            raw_sql = sql_plan.get("sql_query", "")
            trace.end_span("sql_generation", status="success", metadata={"raw_sql": raw_sql})

            # 3. Guardrails validation
            trace.start_span("sql_guardrails")
            try:
                sanitized_sql = SQLGuardrails.validate_and_sanitize(raw_sql)
                trace.end_span("sql_guardrails", status="success")
            except SQLGuardrailError as sge:
                trace.end_span("sql_guardrails", status="failed", metadata={"error": str(sge)})
                trace.add_error(str(sge))
                refusal_text = str(sge)
                for word in refusal_text.split(" "):
                    yield _format_sse("token", {"token": word + " ", "trace_id": trace.trace_id})
                    await asyncio.sleep(0.01)
                yield _format_sse("done", {"trace_id": trace.trace_id})
                return

            yield _format_sse("sql", {
                "sql": sanitized_sql,
                "intent": sql_plan.get("intent", "Data Analysis"),
                "trace_id": trace.trace_id,
            })

            # 4. Pipeline step: Execution in DuckDB
            trace.start_span("duckdb_execution")
            yield _format_sse("pipeline_step", {
                "step": "duckdb_execution",
                "message": "Executing query deterministically in DuckDB...",
                "trace_id": trace.trace_id,
            })
            await asyncio.sleep(0.01)

            start_exec = time.perf_counter()
            records, error = llm_service._execute_with_retry(
                conn, sanitized_sql, catalog_schema, req.message
            )
            exec_duration_ms = round((time.perf_counter() - start_exec) * 1000, 2)

            if error:
                trace.end_span("duckdb_execution", status="failed", metadata={"error": error})
                trace.add_error(error)
                yield _format_sse("error", {"message": f"DuckDB Execution Error: {error}"})
                yield _format_sse("done", {"trace_id": trace.trace_id})
                return

            trace.end_span("duckdb_execution", status="success", metadata={
                "runtime_ms": exec_duration_ms,
                "row_count": len(records),
            })

            # Detect tables used
            all_tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            tables_used = [t for t in all_tables if t.lower() in sanitized_sql.lower()]

            yield _format_sse("execution", {
                "runtime_ms": exec_duration_ms,
                "row_count": len(records),
                "tables_used": tables_used,
                "data_preview": records[:30],
                "trace_id": trace.trace_id,
            })

            # 5. Emit Chart Spec (if applicable)
            chart_spec = llm_service._build_chart_spec(sql_plan, records)
            if chart_spec:
                yield _format_sse("chart", chart_spec.model_dump())

            # 6. Pipeline step: Stream Narrative Tokens
            trace.start_span("narrative_synthesis")
            yield _format_sse("pipeline_step", {
                "step": "narrative_synthesis",
                "message": "Synthesizing grounded natural language narrative...",
                "trace_id": trace.trace_id,
            })

            full_narrative = ""
            # Stream from Groq if available
            if llm_service.client:
                prompt = PromptBuilder.build_narrative_prompt(req.message, sanitized_sql, records)
                try:
                    stream = llm_service.client.chat.completions.create(
                        model=llm_service.model,
                        messages=[
                            {"role": "system", "content": "You are a helpful data analyst. Ground all answers strictly in the supplied data."},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                        max_tokens=600,
                        stream=True,
                    )
                    for chunk in stream:
                        token = chunk.choices[0].delta.content or ""
                        if token:
                            full_narrative += token
                            yield _format_sse("token", {"token": token})
                            await asyncio.sleep(0.005)
                except Exception as e:
                    trace.add_warning(f"Streaming LLM failed ({str(e)}), falling back to heuristic narrative.")
                    fallback_text = llm_service._heuristic_narrative_fallback(req.message, records)
                    full_narrative = fallback_text
                    for word in fallback_text.split(" "):
                        yield _format_sse("token", {"token": word + " "})
                        await asyncio.sleep(0.01)
            else:
                fallback_text = llm_service._heuristic_narrative_fallback(req.message, records)
                full_narrative = fallback_text
                for word in fallback_text.split(" "):
                    yield _format_sse("token", {"token": word + " "})
                    await asyncio.sleep(0.01)

            trace.end_span("narrative_synthesis", status="success")

            # 7. Evaluate Grounding (Precision@k, Table Recall@k)
            trace.start_span("grounding_evaluation")
            grounding_result = GroundingValidator.evaluate(
                user_message=req.message,
                narrative=full_narrative,
                sql_query=sanitized_sql,
                query_records=records,
                conn=conn,
            )
            grounding_dict = grounding_result.to_dict()
            trace.end_span("grounding_evaluation", status="success", metadata=grounding_dict)
            trace.set_metric("grounding_precision", grounding_dict["grounding_precision"])
            trace.set_metric("table_recall", grounding_dict["table_recall"])

            yield _format_sse("grounding", grounding_dict)

            # 8. Complete & Done event
            trace_dict = trace.to_dict()
            tracer.persist_trace(trace)
            yield _format_sse("done", {
                "trace_id": trace.trace_id,
                "total_duration_ms": trace_dict["total_duration_ms"],
                "status": "success",
            })

        except Exception as e:
            trace.add_error(str(e))
            tracer.persist_trace(trace)
            yield _format_sse("error", {"message": f"Pipeline failure: {str(e)}", "trace_id": trace.trace_id})
            yield _format_sse("done", {"trace_id": trace.trace_id})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

def _format_sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
