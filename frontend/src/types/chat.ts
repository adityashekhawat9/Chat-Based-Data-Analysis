export interface ChartSpec {
  type: "line" | "bar" | "pie" | "area" | "table";
  title: string;
  x_axis: string;
  y_axis: string;
  data: Record<string, any>[];
}

export interface ExecutionMetrics {
  tables_used: string[];
  row_count: number;
  execution_time_ms: number;
}

export interface GroundingMetrics {
  grounding_precision: number;
  table_recall: number;
  feasibility_status: string;
  supported_claims: string[];
  unsupported_claims: string[];
  notes: string[];
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  sql_query: string;
  chart?: ChartSpec | null;
  data_preview: Record<string, any>[];
  execution_metrics: ExecutionMetrics;
  grounding_metrics?: GroundingMetrics | null;
  trace_id?: string | null;
  error?: string | null;
}

export interface MessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  chart?: ChartSpec | null;
  sql_query?: string;
  data_preview?: Record<string, any>[];
  metrics?: ExecutionMetrics;
  grounding?: GroundingMetrics | null;
  trace_id?: string | null;
  timestamp: string;
  error?: string | null;
  isStreaming?: boolean;
}
