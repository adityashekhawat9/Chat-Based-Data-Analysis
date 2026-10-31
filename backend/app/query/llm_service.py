import os
import json
import re
import time
from typing import Dict, List, Any, Optional, Tuple
import duckdb
from groq import Groq

from backend.app.models.chat import (
    ChatMessage,
    ChartSpec,
    ExecutionMetrics,
    ChatResponse,
)
from backend.app.query.prompt_builder import PromptBuilder
from backend.app.query.sql_guardrails import SQLGuardrails, SQLGuardrailError, MUTATION_REFUSAL_MESSAGE
from backend.app.query.nlp_guardrails import NLPGuardrails, PROMPT_INJECTION_REFUSAL_MESSAGE

GROQ_DEFAULT_MODEL = os.environ.get("GROQ_MODEL", os.environ.get("LLM_MODEL", "openai/gpt-oss-120b"))

class LLMService:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._load_local_env()
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model or os.environ.get("GROQ_MODEL", os.environ.get("LLM_MODEL", GROQ_DEFAULT_MODEL))
        self.client = Groq(api_key=self.api_key) if self.api_key else None

    @staticmethod
    def _load_local_env():
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass

    def query(
        self,
        session_id: str,
        user_message: str,
        conn: duckdb.DuckDBPyConnection,
        history: Optional[List[ChatMessage]] = None,
    ) -> ChatResponse:
        start_time = time.perf_counter()

        # 1. Guard against buffer flooding / ReDoS via message length validation (V5)
        try:
            NLPGuardrails.validate_message_length(user_message)
        except ValueError as ve:
            return ChatResponse(
                session_id=session_id,
                answer=str(ve),
                sql_query="",
                chart=None,
                data_preview=[],
                execution_metrics=ExecutionMetrics(execution_time_ms=0),
                error=str(ve),
            )

        # 2. Check for prompt injection / jailbreak attempts (V3)
        is_injection, injection_refusal = NLPGuardrails.detect_prompt_injection(user_message)
        if is_injection:
            return ChatResponse(
                session_id=session_id,
                answer=injection_refusal or PROMPT_INJECTION_REFUSAL_MESSAGE,
                sql_query="",
                chart=None,
                data_preview=[],
                execution_metrics=ExecutionMetrics(execution_time_ms=round((time.perf_counter() - start_time) * 1000, 2)),
            )

        # 3. Check mutation intent before generating SQL plan (V1 & V2)
        if SQLGuardrails.is_mutation_intent(user_message):
            return ChatResponse(
                session_id=session_id,
                answer=MUTATION_REFUSAL_MESSAGE,
                sql_query="",
                chart=None,
                data_preview=[],
                execution_metrics=ExecutionMetrics(tables_used=[], row_count=0, execution_time_ms=round((time.perf_counter() - start_time) * 1000, 2)),
            )

        catalog_schema = PromptBuilder.get_catalog_schema(conn)

        if "No tables currently registered" in catalog_schema:
            return ChatResponse(
                session_id=session_id,
                answer="No datasets are currently registered in this session. Please upload a CSV file or click 'Load Sample Dataset' to begin your analysis.",
                sql_query="",
                chart=None,
                data_preview=[],
                execution_metrics=ExecutionMetrics(tables_used=[], row_count=0, execution_time_ms=0),
            )

        # 1. Generate SQL Plan (via Groq or Heuristic Fallback)
        sql_plan = self._generate_sql_plan(user_message, catalog_schema, history)
        raw_sql = sql_plan.get("sql_query", "")

        # 2. Sanitize & Validate SQL Guardrails
        try:
            sanitized_sql = SQLGuardrails.validate_and_sanitize(raw_sql)
        except SQLGuardrailError as se:
            err_msg = str(se)
            return ChatResponse(
                session_id=session_id,
                answer=err_msg,
                sql_query=raw_sql,
                chart=None,
                data_preview=[],
                execution_metrics=ExecutionMetrics(execution_time_ms=round((time.perf_counter() - start_time) * 1000, 2)),
                error=err_msg,
            )

        # 3. Deterministic Execution in DuckDB with Self-Correction
        records, error = self._execute_with_retry(conn, sanitized_sql, catalog_schema, user_message)
        if error:
            safe_error = NLPGuardrails.sanitize_database_error(error)
            return ChatResponse(
                session_id=session_id,
                answer=f"Could not execute query on dataset: {safe_error}",
                sql_query=sanitized_sql,
                chart=None,
                data_preview=[],
                execution_metrics=ExecutionMetrics(execution_time_ms=round((time.perf_counter() - start_time) * 1000, 2)),
                error=safe_error,
            )

        query_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        row_count = len(records)

        # Detect tables used in query
        all_tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        tables_used = [t for t in all_tables if t.lower() in sanitized_sql.lower()]

        # 4. Generate Grounded Narrative
        answer = self._generate_grounded_narrative(user_message, sanitized_sql, records)

        # 5. Format Chart Specification
        chart_spec = self._build_chart_spec(sql_plan, records)

        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sql_query=sanitized_sql,
            chart=chart_spec,
            data_preview=records[:50],  # Return up to 50 rows for data table inspection
            execution_metrics=ExecutionMetrics(
                tables_used=tables_used,
                row_count=row_count,
                execution_time_ms=query_duration_ms,
            ),
        )

    def _generate_sql_plan(
        self,
        user_message: str,
        catalog_schema: str,
        history: Optional[List[ChatMessage]] = None,
    ) -> Dict[str, Any]:
        if not self.client:
            return self._heuristic_sql_fallback(user_message, catalog_schema)

        history_str = ""
        if history:
            history_str = "\n".join([f"{m.role}: {m.content}" for m in history[-4:]])

        prompt = PromptBuilder.build_sql_prompt(user_message, catalog_schema, history_str)

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a specialized SQL planner that responds ONLY in raw JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            resp_text = completion.choices[0].message.content or "{}"
            plan = json.loads(resp_text)
            return plan
        except Exception:
            return self._heuristic_sql_fallback(user_message, catalog_schema)

    def _execute_to_records(self, conn: duckdb.DuckDBPyConnection, sql: str) -> List[Dict[str, Any]]:
        # Enforce statement timeout to prevent Cartesian explosion DoS (V5)
        try:
            conn.execute("SET statement_timeout = '15s'")
        except Exception:
            pass
        cursor = conn.execute(sql)
        if not cursor.description:
            return []
        col_names = [d[0] for d in cursor.description]
        # Bounded fetch to safeguard against OOM on massive result sets
        rows = cursor.fetchmany(1001)
        return [dict(zip(col_names, row)) for row in rows]


    def _execute_with_retry(
        self,
        conn: duckdb.DuckDBPyConnection,
        sql: str,
        catalog_schema: str,
        user_message: str,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        try:
            records = self._execute_to_records(conn, sql)
            return records, None
        except Exception as e:
            initial_error = str(e)
            # If no LLM available, return initial error
            if not self.client:
                return [], initial_error

            # 1-turn self-correction loop
            correction_prompt = f"""The following DuckDB SQL query failed to execute:
{sql}

DuckDB Error Message:
{initial_error}

Database Schema:
{catalog_schema}

User Question:
{user_message}

Please output a corrected, valid DuckDB SQL query in JSON format:
{{ "sql_query": "SELECT ..." }}
"""
            try:
                comp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Fix the failed SQL query. Output ONLY JSON."},
                        {"role": "user", "content": correction_prompt},
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                fixed_json = json.loads(comp.choices[0].message.content or "{}")
                fixed_sql = SQLGuardrails.validate_and_sanitize(fixed_json.get("sql_query", ""))
                records = self._execute_to_records(conn, fixed_sql)
                return records, None
            except Exception as e2:
                return [], f"Execution failed: {initial_error} (Correction attempt failed: {str(e2)})"


    def _generate_grounded_narrative(
        self,
        user_message: str,
        sql_query: str,
        query_results: List[Dict[str, Any]],
    ) -> str:
        if not query_results:
            return "No matching records found in the dataset for this query."

        if not self.client:
            # Deterministic heuristic narrative fallback
            return self._heuristic_narrative_fallback(user_message, query_results)

        prompt = PromptBuilder.build_narrative_prompt(user_message, sql_query, query_results)

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful data analyst. Ground all answers strictly in the supplied data."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            return completion.choices[0].message.content or "Analysis completed successfully."
        except Exception:
            return self._heuristic_narrative_fallback(user_message, query_results)

    def _build_chart_spec(
        self,
        sql_plan: Dict[str, Any],
        records: List[Dict[str, Any]],
    ) -> Optional[ChartSpec]:
        chart_type = sql_plan.get("chart_type", "none")
        if not chart_type or chart_type == "none" or len(records) < 2:
            return None

        keys = list(records[0].keys()) if records else []
        if len(keys) < 2:
            return None

        # 1. Resilient column resolution for x_axis
        plan_x = (sql_plan.get("x_axis") or "").strip()
        matched_x = None
        for k in keys:
            if k.lower() == plan_x.lower():
                matched_x = k
                break
        if not matched_x:
            # Pick first non-numeric or categorical column
            for k in keys:
                first_val = records[0].get(k)
                if not isinstance(first_val, (int, float)):
                    matched_x = k
                    break
        x_axis = matched_x or keys[0]

        # 2. Resilient column resolution for y_axis
        plan_y = (sql_plan.get("y_axis") or "").strip()
        matched_y = None
        for k in keys:
            if k.lower() == plan_y.lower() and k != x_axis:
                matched_y = k
                break
        if not matched_y:
            # Pick first numeric column that is not x_axis
            for k in keys:
                if k == x_axis:
                    continue
                first_val = records[0].get(k)
                if isinstance(first_val, (int, float)):
                    matched_y = k
                    break
        y_axis = matched_y or (keys[1] if len(keys) > 1 else keys[0])
        title = sql_plan.get("chart_title") or f"{y_axis.replace('_', ' ').title()} by {x_axis.replace('_', ' ').title()}"

        # 3. Check if x_axis has duplicates in records (e.g. category repeated across years/statuses)
        x_vals = [r.get(x_axis) for r in records]
        has_duplicates = len(x_vals) != len(set(x_vals))

        if has_duplicates and len(keys) == 3:
            pivot_col = [k for k in keys if k not in (x_axis, y_axis)][0]
            metric_col = y_axis

            pivoted_dict = {}
            for r in records[:100]:
                x_val = str(r.get(x_axis, ""))
                p_val = str(r.get(pivot_col, ""))
                m_val = r.get(metric_col, 0)
                try:
                    m_num = round(float(str(m_val).replace("$", "").replace(",", "").strip()), 2)
                except (ValueError, TypeError):
                    m_num = 0.0

                if x_val not in pivoted_dict:
                    pivoted_dict[x_val] = {x_axis: x_val}
                pivoted_dict[x_val][p_val] = m_num

            cleaned_data = list(pivoted_dict.values())
        else:
            # Standard clean numerical values for chart rendering
            cleaned_data = []
            for r in records[:50]:
                item = {}
                for k, v in r.items():
                    if hasattr(v, "isoformat"):
                        item[k] = v.isoformat()
                    elif isinstance(v, (int, float)):
                        item[k] = round(float(v), 2)
                    elif isinstance(v, str):
                        clean_str = re.sub(r"[$,\s]", "", v)
                        try:
                            item[k] = round(float(clean_str), 2)
                        except ValueError:
                            item[k] = v
                    else:
                        item[k] = str(v)
                cleaned_data.append(item)

        valid_types = ("line", "bar", "pie", "area")
        chosen_type = chart_type if chart_type in valid_types else "bar"

        return ChartSpec(
            type=chosen_type,
            title=title,
            x_axis=x_axis,
            y_axis=y_axis,
            data=cleaned_data,
        )

    def _heuristic_sql_fallback(self, msg: str, schema: str) -> Dict[str, Any]:
        """
        Robust heuristic SQL planner for common analytical queries when Groq is unavailable.
        """
        m = msg.lower()

        # Monthly trend / revenue trend
        if "trend" in m or "month" in m or "over time" in m:
            return {
                "sql_query": """
SELECT 
    strftime('%Y-%m', CAST(o.order_date AS DATE)) AS month,
    ROUND(SUM(o.total_price), 2) AS recognized_revenue,
    COUNT(DISTINCT o.order_id) AS order_count
FROM orders o
JOIN payment p ON o.order_id = p.order_id
WHERE p.transaction_status = 'Completed'
GROUP BY month
ORDER BY month
""".strip(),
                "chart_type": "line",
                "chart_title": "Monthly Recognized Revenue Trend",
                "x_axis": "month",
                "y_axis": "recognized_revenue",
            }

        # Category sales
        if "categor" in m:
            return {

                "sql_query": """
SELECT 
    p.category,
    ROUND(SUM(oi.quantity * oi.price_at_purchase), 2) AS total_sales,
    SUM(oi.quantity) AS units_sold
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN orders o ON oi.order_id = o.order_id
JOIN payment py ON o.order_id = py.order_id
WHERE py.transaction_status = 'Completed'
GROUP BY p.category
ORDER BY total_sales DESC
""".strip(),
                "chart_type": "bar",
                "chart_title": "Total Sales by Product Category",
                "x_axis": "category",
                "y_axis": "total_sales",
            }

        # State / Geographic comparison
        if "state" in m or "region" in m or "city" in m:
            return {
                "sql_query": """
SELECT 
    TRIM(SPLIT_PART(c.address, ',', 3)) AS state,
    ROUND(SUM(o.total_price), 2) AS total_sales,
    COUNT(DISTINCT o.order_id) AS order_count
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN payment p ON o.order_id = p.order_id
WHERE p.transaction_status = 'Completed'
GROUP BY state
ORDER BY total_sales DESC
LIMIT 10
""".strip(),
                "chart_type": "bar",
                "chart_title": "Top 10 States by Recognized Revenue",
                "x_axis": "state",
                "y_axis": "total_sales",
            }

        # Payment status breakdown
        if "payment" in m or "status" in m or "transaction" in m:
            return {
                "sql_query": """
SELECT 
    transaction_status,
    COUNT(*) AS transaction_count,
    ROUND(SUM(amount), 2) AS total_amount
FROM payment
GROUP BY transaction_status
ORDER BY transaction_count DESC
""".strip(),
                "chart_type": "pie",
                "chart_title": "Payment Status Distribution",
                "x_axis": "transaction_status",
                "y_axis": "transaction_count",
            }

        # Carrier performance
        if "carrier" in m or "shipment" in m or "delivery" in m:
            return {
                "sql_query": """
SELECT 
    carrier,
    shipment_status,
    COUNT(*) AS shipment_count
FROM shipments
GROUP BY carrier, shipment_status
ORDER BY carrier, shipment_count DESC
""".strip(),
                "chart_type": "bar",
                "chart_title": "Shipment Status by Carrier",
                "x_axis": "carrier",
                "y_axis": "shipment_count",
            }

        # Default: Total revenue summary
        return {
            "sql_query": """
SELECT 
    ROUND(SUM(CASE WHEN p.transaction_status = 'Completed' THEN o.total_price ELSE 0 END), 2) AS recognized_revenue,
    ROUND(SUM(o.total_price), 2) AS gross_order_value,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(DISTINCT CASE WHEN p.transaction_status = 'Completed' THEN o.order_id END) AS completed_orders
FROM orders o
JOIN payment p ON o.order_id = p.order_id
""".strip(),
            "chart_type": "none",
            "chart_title": "Revenue Summary",
            "x_axis": "",
            "y_axis": "",
        }

    def _heuristic_narrative_fallback(self, msg: str, records: List[Dict[str, Any]]) -> str:
        if not records:
            return "No matching records found in the dataset for this query."

        # If single scalar row
        if len(records) == 1:
            row = records[0]
            bullets = [f"- **{k.replace('_', ' ').title()}**: {v:,.2f}" if isinstance(v, (int, float)) else f"- **{k.replace('_', ' ').title()}**: {v}" for k, v in row.items()]
            return "Here is the summary based on the analyzed data:\n\n" + "\n".join(bullets)

        # Multi-row summary
        total_rows = len(records)
        first_row = records[0]
        keys = list(first_row.keys())
        top_item = first_row.get(keys[0], "Top entity")
        top_val = first_row.get(keys[1], 0)
        top_val_str = f"{top_val:,.2f}" if isinstance(top_val, (int, float)) else str(top_val)

        return f"Analysis returned **{total_rows} data points**. The leading entry is **{top_item}** with **{top_val_str}** ({keys[1].replace('_', ' ')}). Please refer to the chart and data table below for the detailed breakdown."
