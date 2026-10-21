"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  Sparkles,
  LineChart,
  BarChart,
  PieChart,
  Loader2,
} from "lucide-react";
import { MessageItem } from "@/types/chat";
import { useChatStream } from "@/hooks/useChatStream";
import ExecutiveDashboardCard from "./ExecutiveDashboardCard";

interface Props {
  sessionId: string;
  hasDatasets: boolean;
  onLoadSample: () => void;
  apiUrl?: string;
  tenantId?: string;
}

const SAMPLE_QUESTIONS = [
  {
    icon: LineChart,
    label: "Monthly Revenue Trend",
    query: "What is the monthly sales trend over the past year?",
  },
  {
    icon: BarChart,
    label: "Sales by Category",
    query: "Compare sales across product categories from two different CSVs",
  },
  {
    icon: BarChart,
    label: "Top States by Sales",
    query: "Which states have the highest sales?",
  },
  {
    icon: PieChart,
    label: "Payment Status Distribution",
    query: "Show me the payment transaction status breakdown",
  },
];

export default function ChatInterface({
  sessionId,
  hasDatasets,
  onLoadSample,
  apiUrl = "http://localhost:8000",
  tenantId = "default_tenant",
}: Props) {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const { isStreaming, currentStep, streamQuery } = useChatStream();
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming, currentStep]);

  const handleSendMessage = async (queryText?: string) => {
    const text = queryText || inputValue;
    if (!text.trim() || isStreaming) return;

    const userMsg: MessageItem = {
      id: `msg_user_${Date.now()}`,
      role: "user",
      content: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    const tempAsstId = `msg_asst_${Date.now()}`;
    const initialAssistantMsg: MessageItem = {
      id: tempAsstId,
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

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);
    if (!queryText) setInputValue("");

    const historyPayload = messages.slice(-4).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    await streamQuery(text.trim(), {
      apiUrl,
      tenantId,
      sessionId,
      history: historyPayload,
      onMessageUpdate: (updatedMsg) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === tempAsstId ? { ...updatedMsg, id: tempAsstId } : m))
        );
      },
      onComplete: (finalMsg) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === tempAsstId ? { ...finalMsg, id: tempAsstId, isStreaming: false } : m
          )
        );
      },
      onError: (errMsg) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === tempAsstId
              ? {
                  ...m,
                  error: errMsg,
                  content: m.content || `⚠️ Error: ${errMsg}`,
                  isStreaming: false,
                }
              : m
          )
        );
      },
    });
  };

  const handleCopySQL = (sql: string, id: string) => {
    navigator.clipboard.writeText(sql);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="flex flex-col h-[760px] bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
      {/* Live Stream Pipeline Stage Bar */}
      {isStreaming && currentStep && (
        <div className="bg-gradient-to-r from-blue-900/60 via-indigo-950/60 to-slate-900/60 border-b border-blue-500/30 px-4 py-2.5 flex items-center justify-between text-xs text-blue-200 backdrop-blur transition-all">
          <div className="flex items-center space-x-2.5">
            <Loader2 className="w-3.5 h-3.5 text-sky-400 animate-spin" />
            <span className="font-medium tracking-wide">{currentStep}</span>
          </div>
          <span className="text-[10px] uppercase font-mono tracking-widest text-sky-400/80 bg-sky-950/80 border border-sky-800 px-2 py-0.5 rounded">
            SSE Stream Active
          </span>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto py-12 space-y-4">
            <div className="p-3 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-2xl">
              <Sparkles className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-semibold text-white">
                Conversational Data Analysis
              </h3>
              <p className="text-sm text-slate-400">
                Ask analytical questions across multiple CSV files. Queries are executed
                deterministically in DuckDB and rendered as clean, executive dashboard cards.
              </p>
            </div>

            {!hasDatasets && (
              <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-300 text-xs flex flex-col items-center gap-2 max-w-md">
                <p>No datasets loaded yet. Upload CSVs above or load the default 8 ecommerce tables.</p>
                <button
                  onClick={onLoadSample}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-medium transition"
                >
                  Pre-load 8 E-Commerce Tables (Online Shop 2024)
                </button>
              </div>
            )}

            {/* Quick Prompt Pills */}
            <div className="pt-2 w-full space-y-2">
              <span className="text-xs text-slate-500 font-medium uppercase tracking-wider block">
                Suggested Executive Questions
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left">
                {SAMPLE_QUESTIONS.map((q, idx) => {
                  const Icon = q.icon;
                  return (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(q.query)}
                      className="p-2.5 rounded-xl border border-slate-800 bg-slate-900/80 hover:bg-slate-800 hover:border-slate-700 text-slate-300 text-xs transition flex items-center gap-2 group"
                    >
                      <Icon className="w-4 h-4 text-sky-400 group-hover:scale-110 transition flex-shrink-0" />
                      <span className="truncate">{q.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className="w-full">
              {msg.role === "user" ? (
                /* User Prompt Bubble */
                <div className="flex gap-3 justify-end mb-4">
                  <div className="max-w-xl rounded-2xl p-4 text-sm bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-br-none shadow-lg shadow-blue-600/20">
                    <div className="flex items-center justify-between text-xs opacity-75 mb-1.5">
                      <span className="font-semibold">You</span>
                      <span className="font-mono text-[11px]">{msg.timestamp}</span>
                    </div>
                    <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-slate-300 flex-shrink-0 mt-1">
                    <User className="w-4 h-4" />
                  </div>
                </div>
              ) : (
                /* Executive Dashboard Card for Assistant Response */
                <div className="flex gap-3 justify-start mb-6">
                  <div className="w-8 h-8 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 flex-shrink-0 mt-2">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div className="flex-1 max-w-4xl">
                    <ExecutiveDashboardCard
                      message={msg}
                      onCopySQL={handleCopySQL}
                      copiedId={copiedId}
                    />
                  </div>
                </div>
              )}
            </div>
          ))
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="border-t border-slate-800 bg-slate-900/80 p-3 sm:p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isStreaming}
            placeholder="Ask an analytical question (e.g., 'What is monthly revenue?', 'Compare sales by category')..."
            className="flex-1 bg-slate-950 border border-slate-700/80 text-slate-100 placeholder-slate-500 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500 transition disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isStreaming}
            className={`p-2.5 rounded-xl transition ${
              inputValue.trim() && !isStreaming
                ? "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20"
                : "bg-slate-800 text-slate-500 cursor-not-allowed"
            }`}
            title="Send query"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
