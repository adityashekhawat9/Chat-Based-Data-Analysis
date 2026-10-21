import { useState, useCallback } from "react";
import { MessageItem, ChartSpec, ExecutionMetrics, GroundingMetrics } from "@/types/chat";

interface StreamOptions {
  apiUrl?: string;
  tenantId: string;
  sessionId: string;
  history: { role: string; content: string }[];
  onMessageUpdate?: (message: MessageItem) => void;
  onComplete?: (message: MessageItem) => void;
  onError?: (err: string) => void;
}

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStep, setCurrentStep] = useState<string | null>(null);

  const streamQuery = useCallback(
    async (
      question: string,
      options: StreamOptions
    ) => {
      const {
        apiUrl = "http://localhost:8000",
        tenantId,
        sessionId,
        history,
        onMessageUpdate,
        onComplete,
        onError,
      } = options;

      setIsStreaming(true);
      setCurrentStep("Connecting to analysis stream...");

      const assistantMsg: MessageItem = {
        id: `msg_asst_${Date.now()}`,
        role: "assistant",
        content: "",
        chart: null,
        sql_query: "",
        data_preview: [],
        metrics: { tables_used: [], row_count: 0, execution_time_ms: 0 },
        grounding: null,
        trace_id: null,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        isStreaming: true,
      };

      try {
        const response = await fetch(`${apiUrl}/api/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Tenant-ID": tenantId,
          },
          body: JSON.stringify({
            session_id: sessionId,
            message: question,
            history,
          }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: Failed to initiate stream.`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("Response body is not readable.");
        }

        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || ""; // Keep partial chunk in buffer

          for (const block of lines) {
            if (!block.trim()) continue;

            const eventMatch = block.match(/^event:\s*([^\n]+)/m);
            const dataMatch = block.match(/^data:\s*([^\n]+)/m);

            if (eventMatch && dataMatch) {
              const eventType = eventMatch[1].trim();
              try {
                const data = JSON.parse(dataMatch[1].trim());

                switch (eventType) {
                  case "pipeline_step":
                    setCurrentStep(data.message || data.step);
                    if (data.trace_id) assistantMsg.trace_id = data.trace_id;
                    break;

                  case "sql":
                    assistantMsg.sql_query = data.sql;
                    if (data.trace_id) assistantMsg.trace_id = data.trace_id;
                    onMessageUpdate?.({ ...assistantMsg });
                    break;

                  case "execution":
                    assistantMsg.metrics = {
                      tables_used: data.tables_used || [],
                      row_count: data.row_count || 0,
                      execution_time_ms: data.runtime_ms || 0,
                    };
                    assistantMsg.data_preview = data.data_preview || [];
                    onMessageUpdate?.({ ...assistantMsg });
                    break;

                  case "chart":
                    assistantMsg.chart = data;
                    onMessageUpdate?.({ ...assistantMsg });
                    break;

                  case "token":
                    assistantMsg.content += data.token;
                    onMessageUpdate?.({ ...assistantMsg });
                    break;

                  case "grounding":
                    assistantMsg.grounding = data;
                    onMessageUpdate?.({ ...assistantMsg });
                    break;

                  case "done":
                    assistantMsg.isStreaming = false;
                    setCurrentStep(null);
                    onMessageUpdate?.({ ...assistantMsg });
                    onComplete?.({ ...assistantMsg });
                    break;

                  case "error":
                    assistantMsg.error = data.message;
                    assistantMsg.content += `\n\n⚠️ ${data.message}`;
                    onError?.(data.message);
                    onMessageUpdate?.({ ...assistantMsg });
                    break;
                }
              } catch (parseErr) {
                console.error("Failed to parse SSE payload", parseErr, block);
              }
            }
          }
        }
      } catch (err: any) {
        assistantMsg.isStreaming = false;
        assistantMsg.error = err.message;
        assistantMsg.content = `Error in streaming communication: ${err.message}`;
        onError?.(err.message);
        onMessageUpdate?.({ ...assistantMsg });
      } finally {
        setIsStreaming(false);
        setCurrentStep(null);
      }
    },
    []
  );

  return {
    isStreaming,
    currentStep,
    streamQuery,
  };
}
