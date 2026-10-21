from typing import Dict, List, Any
import duckdb

class PromptBuilder:
    @staticmethod
    def get_catalog_schema(conn: duckdb.DuckDBPyConnection) -> str:
        """
        Dynamically introspects all tables in the session's DuckDB catalog.
        """
        tables = conn.execute("SHOW TABLES").fetchall()
        if not tables:
            return "No tables currently registered in the database catalog."

        schema_lines = []
        for (table_name,) in tables:
            row_count = conn.execute(f"SELECT COUNT(*) FROM \"{table_name}\"").fetchone()[0]
            col_info = conn.execute(f"DESCRIBE \"{table_name}\"").fetchall()
            cols_desc = []
            for col in col_info:
                col_name, col_type, null, pk, dflt, extra = col[:6]
                cols_desc.append(f"  - {col_name} ({col_type})")
            
            # Fetch sample row using native cursor
            cursor = conn.execute(f"SELECT * FROM \"{table_name}\" LIMIT 1")
            col_names = [d[0] for d in cursor.description]
            sample_rows = cursor.fetchall()
            sample_str = str(dict(zip(col_names, sample_rows[0]))) if sample_rows else "None"

            schema_lines.append(
                f"Table: {table_name} ({row_count:,} rows)\n"
                + "\n".join(cols_desc)
                + f"\nSample row: {sample_str}\n"
            )


        return "\n".join(schema_lines)

    @classmethod
    def build_sql_prompt(
        cls,
        user_question: str,
        catalog_schema: str,
        conversation_history: str = "",
    ) -> str:
        prompt = f"""You are an expert Data Engineer and Business Analyst specializing in DuckDB SQL.
Your task is to generate a single, highly accurate, deterministic SQL query (SELECT only) to answer the user's question, and recommend an appropriate chart visualization if applicable.

=== ACTIVE DUCKDB DATABASE SCHEMA ===
{catalog_schema}

=== ESSENTIAL BUSINESS & ANALYTICAL RULES ===
1. TEMPORAL BOUNDS: The dataset's maximum date is 2024-11-04 (covering 2023-11-05 to 2024-11-04). NEVER use CURRENT_DATE or NOW()! When the user says "last year" or "past 12 months", anchor to 2024-11-04.
2. RECOGNIZED REVENUE: Use orders.total_price joined with payment ON orders.order_id = payment.order_id WHERE payment.transaction_status = 'Completed'.
3. JOIN FAN-OUT WARNING: orders to order_items is a 1-to-many relationship (some orders have multiple items). NEVER run SUM(orders.total_price) after joining orders to order_items, because multi-item orders will be counted multiple times!
4. HISTORICAL PRICES: In order_items, always use price_at_purchase for historical revenue/spending, NOT products.price.
5. ADDRESS PARSING: Customer addresses are formatted as "Street, City, State" (e.g. '123 Main St, Springfield, IL'). To group by state, use: TRIM(SPLIT_PART(address, ',', 3)). To group by city, use: TRIM(SPLIT_PART(address, ',', 2)).
6. DUCKDB SQL SYNTAX:
   - For monthly grouping, use: strftime('%Y-%m', CAST(order_date AS DATE)) AS month
   - Always ROUND monetary sums to 2 decimal places: ROUND(SUM(...), 2)
   - Order results sensibly (chronologically for dates, descending for volume/revenue).
7. CHART RECOMMENDATIONS:
   - "line" for time trends / monthly sales
   - "bar" for categorical comparisons (by category, carrier, state, or top 5-10 rankings)
   - "pie" for status distributions or category share (max 6 slices)
   - "none" for single scalar KPIs or detailed record lists
8. STRICT READ-ONLY SECURITY:
   - You MUST ONLY generate read-only queries (SELECT or WITH statements).
   - NEVER generate DELETE, DROP, UPDATE, INSERT, ALTER, or TRUNCATE statements under any circumstances.

=== CONVERSATION HISTORY ===
{conversation_history or "None"}

=== USER QUESTION ===
{user_question}

=== OUTPUT FORMAT INSTRUCTIONS ===
You must respond with ONLY valid JSON with this exact schema (no markdown, no other text):
{{
  "sql_query": "SELECT ...",
  "intent": "Brief description of analytical intent",
  "chart_type": "line" | "bar" | "pie" | "none",
  "chart_title": "Descriptive chart title",
  "x_axis": "column_name_for_x_axis",
  "y_axis": "column_name_for_y_axis"
}}
"""
        return prompt

    @classmethod
    def build_narrative_prompt(
        cls,
        user_question: str,
        sql_query: str,
        query_results: List[Dict[str, Any]],
    ) -> str:
        results_preview = str(query_results[:50])
        total_rows = len(query_results)

        prompt = f"""You are a Senior Data Analyst summarizing query results for business stakeholders.
Synthesize a grounded, concise, professional response to the user's question.

=== USER QUESTION ===
{user_question}

=== EXECUTED DUCKDB SQL ===
{sql_query}

=== DETERMINISTIC QUERY RESULTS ({total_rows} rows) ===
{results_preview}

=== GROUNDING & EXECUTIVE BRIEF RULES ===
1. Every single numerical figure, percentage, or currency amount you mention MUST come directly from the query results above.
2. NEVER hallucinate or recalculate figures.
3. Structure your response as an Executive Brief:
   - **Executive Summary**: 1-2 sentence core answer to the user's question.
   - **Key Metrics**: Clear, labeled metrics with exact values (e.g. **Metric Name**: $XX,XXX.XX or XX,XXX).
   - **Strategic Insights**: 1-3 analytical observations (peak performance, category dominance, percentage contribution, or distribution).
4. If the result set is empty, state clearly that no records matched the criteria.
5. STRICT READ-ONLY SECURITY:
   - This application is strictly a read-only analytical engine.
   - NEVER suggest, write, or provide mutating SQL statements (DELETE, DROP, UPDATE, INSERT, ALTER, TRUNCATE).
   - If the user asks about deleting or modifying records, explain politely that this system operates in read-only mode, and focus solely on analytical views.
"""
        return prompt
