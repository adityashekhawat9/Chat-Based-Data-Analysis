"use client";

import React, { useState, useMemo } from "react";
import {
  DollarSign,
  TrendingUp,
  Package,
  CheckCircle2,
  BarChart3,
  Layers,
  Sparkles,
  Terminal,
  Clock,
  Table as TableIcon,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  ShieldCheck,
  ArrowRight,
  Lightbulb,
  Building2,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { MessageItem } from "@/types/chat";
import DynamicChart from "./DynamicChart";

interface Props {
  message: MessageItem;
  onCopySQL?: (sql: string, id: string) => void;
  copiedId?: string | null;
}

interface KpiItem {
  id: string;
  label: string;
  value: string;
  subtext?: string;
  isCurrency?: boolean;
}

export interface ParsedTable {
  headers: string[];
  rows: string[][];
  footnote?: string;
}

interface ParsedNarrative {
  introParagraphs: string[];
  kpis: KpiItem[];
  insights: { title: string; body: string }[];
  table?: ParsedTable;
  outroParagraphs: string[];
}

/**
 * Modern NLP Clean Formatted Text Renderer:
 * - Converts **text** into clean, bold HTML nodes (no raw asterisks in UI)
 * - Converts `code` into styled monospace pill
 * - Converts *italic* into styled emphasis
 * - Strips leading markdown header hashes (###) and markdown escape backslashes (\*)
 * - Removes stray double asterisks
 */
export function renderCleanFormattedText(rawText: string): React.ReactNode {
  if (!rawText) return null;

  // 1. Strip redundant prefix boilerplate & leading header hashes & escape backslashes
  const cleaned = rawText
    .replace(/^#{1,6}\s*/, "") // remove leading ###
    .replace(/^Here is the (?:executive )?summary (?:based on the analyzed data|of the query results)?:\s*/i, "")
    .replace(/\\([*_#`\\])/g, "$1"); // remove markdown escape slashes

  // 2. Tokenize by markdown bold (**...**), inline code (`...`), and italics (*...*)
  const parts = cleaned.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g);

  return (
    <>
      {parts.map((part, idx) => {
        if (!part) return null;

        // Bold match: **text**
        if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
          const inner = part.slice(2, -2).trim();
          return (
            <strong key={idx} className="font-semibold text-slate-100">
              {inner}
            </strong>
          );
        }

        // Inline code match: `code`
        if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
          const inner = part.slice(1, -1).trim();
          return (
            <code
              key={idx}
              className="px-1.5 py-0.5 mx-0.5 rounded bg-slate-800/90 border border-slate-700/60 font-mono text-[12px] text-sky-300"
            >
              {inner}
            </code>
          );
        }

        // Italic match: *text* (excluding standalone footnote asterisks)
        if (part.startsWith("*") && part.endsWith("*") && part.length >= 3 && !part.includes(" ")) {
          const inner = part.slice(1, -1).trim();
          return (
            <em key={idx} className="text-slate-300 italic">
              {inner}
            </em>
          );
        }

        // Clean any leftover double asterisks
        const safeText = part.replace(/\*\*/g, "");
        return <React.Fragment key={idx}>{safeText}</React.Fragment>;
      })}
    </>
  );
}

export default function ExecutiveDashboardCard({
  message,
  onCopySQL,
  copiedId,
}: Props) {
  const [isTraceExpanded, setIsTraceExpanded] = useState(false);
  const [isGroundingExpanded, setIsGroundingExpanded] = useState(false);

  // Parse narrative content into structured executive components
  const parsed = useMemo<ParsedNarrative>(() => {
    const content = message.content || "";
    const lines = content.split("\n");

    const introParagraphs: string[] = [];
    const extractedKpis: KpiItem[] = [];
    const insights: { title: string; body: string }[] = [];
    let extractedTable: ParsedTable | undefined = undefined;
    const outroParagraphs: string[] = [];

    // First, check if single scalar row in data_preview has KPI columns
    if (message.data_preview && message.data_preview.length === 1) {
      const row = message.data_preview[0];
      for (const [key, val] of Object.entries(row)) {
        if (typeof val === "number" || (typeof val === "string" && !isNaN(Number(val)))) {
          const numVal = Number(val);
          const isCurr =
            key.toLowerCase().includes("revenue") ||
            key.toLowerCase().includes("price") ||
            key.toLowerCase().includes("amount") ||
            key.toLowerCase().includes("sales") ||
            key.toLowerCase().includes("value");

          const formatted = isCurr
            ? `$${numVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            : numVal.toLocaleString();

          extractedKpis.push({
            id: `kpi_preview_${key}`,
            label: key.replace(/_/g, " ").toUpperCase(),
            value: formatted,
            isCurrency: isCurr,
          });
        }
      }
    }

    let currentSection: "intro" | "kpis" | "insights" | "outro" = "intro";

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      // Section Delimiter detection
      const lower = line.toLowerCase();
      if (lower.includes("executive summary")) {
        currentSection = "intro";
        continue;
      }
      if (lower.includes("key metrics") || lower.includes("primary metrics")) {
        currentSection = "kpis";
        continue;
      }
      if (lower.includes("strategic insights") || lower.includes("key insights") || lower.includes("takeaways")) {
        currentSection = "insights";
        continue;
      }

      // Detection & Parsing of Markdown Tables: | Col1 | Col2 |
      if (line.startsWith("|") && line.endsWith("|")) {
        const tableLines: string[] = [line];
        let nextIdx = i + 1;
        while (
          nextIdx < lines.length &&
          lines[nextIdx].trim().startsWith("|") &&
          lines[nextIdx].trim().endsWith("|")
        ) {
          tableLines.push(lines[nextIdx].trim());
          nextIdx++;
        }

        if (tableLines.length >= 2) {
          // Parse header row
          const rawHeaderCols = tableLines[0].split("|");
          const headers = rawHeaderCols
            .map((c) => c.trim().replace(/\\([*_#`\\])/g, "$1").replace(/\*\*/g, ""))
            .filter((c, idx) => idx > 0 && idx < rawHeaderCols.length - 1);

          // Check if row 1 is delimiter: |---|---|
          const isSeparator = /^\|[\s-:]+(\|[\s-:]+)+\|$/.test(tableLines[1]);
          const startRowIdx = isSeparator ? 2 : 1;

          const rows: string[][] = [];
          for (let r = startRowIdx; r < tableLines.length; r++) {
            const rawRowCols = tableLines[r].split("|");
            const rowCells = rawRowCols
              .map((c) => c.trim().replace(/\\([*_#`\\])/g, "$1").replace(/\*\*/g, ""))
              .filter((c, idx) => idx > 0 && idx < rawRowCols.length - 1);
            if (rowCells.length > 0) {
              rows.push(rowCells);
            }
          }

          // Check for immediate footnote following the table (e.g. \*Footnote or *Footnote or Note:)
          let footnote: string | undefined = undefined;
          if (nextIdx < lines.length) {
            const candidate = lines[nextIdx].trim();
            if (
              candidate.startsWith("\\*") ||
              candidate.startsWith("*") ||
              candidate.toLowerCase().startsWith("note:") ||
              candidate.toLowerCase().startsWith("footnote:")
            ) {
              footnote = candidate.replace(/^\\\*/, "*").trim();
              nextIdx++;
            }
          }

          extractedTable = {
            headers,
            rows,
            footnote,
          };

          i = nextIdx - 1;
          continue;
        }
      }

      // Pattern 1: Numbered or Bulleted: (1. or - or *) **Label**: Value
      const kpiMatch1 = line.match(/^(\d+\.|\*|-)?\s*\*\*([^*]+)\*\*:\s*(.*)$/);
      if (kpiMatch1) {
        const label = kpiMatch1[2].trim();
        const rawVal = kpiMatch1[3].trim();

        // Check if value is numeric or currency
        const cleanedNum = rawVal.replace(/[$,\s]/g, "").replace(/\(.*?\)/g, "").trim();
        const isNumeric = !isNaN(Number(cleanedNum)) && cleanedNum.length > 0;

        if (isNumeric && extractedKpis.length < 6 && currentSection !== "insights") {
          const exists = extractedKpis.some(
            (k) => k.label.toLowerCase() === label.toLowerCase()
          );
          if (!exists) {
            const isCurr =
              label.toLowerCase().includes("revenue") ||
              label.toLowerCase().includes("price") ||
              label.toLowerCase().includes("sales") ||
              label.toLowerCase().includes("value") ||
              rawVal.includes("$");

            const num = Number(cleanedNum);
            const formatted = isCurr
              ? (rawVal.startsWith("$") ? rawVal : `$${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
              : num.toLocaleString();

            extractedKpis.push({
              id: `kpi_line_${i}`,
              label: label.toUpperCase(),
              value: formatted,
              isCurrency: isCurr,
            });
            continue;
          }
        }

        // Otherwise, it is an executive strategic insight!
        insights.push({
          title: label,
          body: rawVal,
        });
        continue;
      }

      // Pattern 2: (1. or - or *) **$Value** – Description
      const kpiMatch2 = line.match(/^(\d+\.|\*|-)?\s*\*\*([$0-9.,]+)\*\*\s*[–—-]\s*(.*)$/);
      if (kpiMatch2) {
        const valStr = kpiMatch2[2].trim();
        const desc = kpiMatch2[3].trim();
        const exists = extractedKpis.some((k) => k.value.includes(valStr));
        if (!exists && extractedKpis.length < 4) {
          extractedKpis.push({
            id: `kpi_val_${i}`,
            label: "AGGREGATE VALUE",
            value: valStr,
            subtext: desc,
            isCurrency: valStr.includes("$"),
          });
        } else {
          insights.push({
            title: "Verified Calculation",
            body: `${valStr}: ${desc}`,
          });
        }
        continue;
      }

      // Pattern 3: Numbered insight without bold colon: 1. **Peak Performance** followed by text
      const insightMatch3 = line.match(/^(\d+\.|\*|-)\s*(.*)$/);
      if (insightMatch3) {
        const rawContent = insightMatch3[2].trim();
        const cleanContent = rawContent.replace(/^\*\*(.*?)\*\*\s*[:–—]?\s*/, "$1: ");
        const parts = cleanContent.split(":");
        if (parts.length > 1) {
          insights.push({
            title: parts[0].trim(),
            body: parts.slice(1).join(":").trim(),
          });
        } else {
          insights.push({
            title: `Takeaway ${insights.length + 1}`,
            body: rawContent,
          });
        }
        continue;
      }

      // Outro check
      if (
        lower.includes("no additional records") ||
        lower.includes("refer to the chart") ||
        lower.includes("please see below")
      ) {
        outroParagraphs.push(line);
      } else {
        introParagraphs.push(line);
      }
    }

    return {
      introParagraphs,
      kpis: extractedKpis,
      insights,
      table: extractedTable,
      outroParagraphs,
    };
  }, [message.content, message.data_preview]);

  const getKpiIcon = (label: string) => {
    const l = label.toLowerCase();
    if (l.includes("revenue") || l.includes("sales") || l.includes("value") || l.includes("amount")) {
      return <DollarSign className="w-4 h-4 text-emerald-400" />;
    }
    if (l.includes("order") && !l.includes("completed")) {
      return <Package className="w-4 h-4 text-blue-400" />;
    }
    if (l.includes("completed") || l.includes("status") || l.includes("success")) {
      return <CheckCircle2 className="w-4 h-4 text-teal-400" />;
    }
    if (l.includes("trend") || l.includes("growth") || l.includes("rate")) {
      return <TrendingUp className="w-4 h-4 text-sky-400" />;
    }
    return <BarChart3 className="w-4 h-4 text-indigo-400" />;
  };

  return (
    <div className="relative bg-slate-900/90 border border-slate-800/90 rounded-2xl shadow-2xl overflow-hidden backdrop-blur-md transition-all duration-200">
      {/* Top Ambient Glow Bar */}
      <div className="h-[2.5px] w-full bg-gradient-to-r from-blue-500 via-indigo-500 to-sky-400 shadow-sm" />

      {/* Card Header Bar */}
      <div className="px-5 py-3.5 border-b border-slate-800/80 bg-slate-950/40 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-100 tracking-wide uppercase">
                Executive Analysis Brief
              </span>
              {message.trace_id && (
                <span className="text-[10px] font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                  {message.trace_id.substring(0, 10)}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full">
            <ShieldCheck className="w-3 h-3" /> Grounded in DuckDB
          </span>
          <span className="text-slate-500 text-[11px]">{message.timestamp}</span>
        </div>
      </div>

      <div className="p-5 sm:p-6 space-y-5">
        {/* Section 1: Executive Summary Box */}
        {parsed.introParagraphs.length > 0 && (
          <div className="bg-gradient-to-br from-blue-950/30 via-slate-900/40 to-indigo-950/20 border border-blue-900/30 rounded-xl p-4 text-slate-200 text-sm leading-relaxed shadow-inner">
            <div className="text-[11px] uppercase font-mono tracking-wider text-sky-400 font-semibold mb-1 flex items-center gap-1.5">
              <Lightbulb className="w-3.5 h-3.5 text-amber-400" /> Executive Overview
            </div>
            {parsed.introParagraphs.map((para, idx) => (
              <p key={idx} className="mt-1 first:mt-0 font-normal text-slate-200">
                {renderCleanFormattedText(para)}
              </p>
            ))}
          </div>
        )}

        {/* Streaming Placeholder if empty content */}
        {!message.content && message.isStreaming && (
          <div className="p-4 bg-slate-950/40 border border-slate-800 rounded-xl flex items-center gap-2.5 text-xs text-sky-300 italic">
            <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping" />
            Synthesizing executive briefing with LLM...
          </div>
        )}

        {/* Section 2: Executive KPI Metric Cards Grid */}
        {parsed.kpis.length > 0 && (
          <div>
            <div className="text-[11px] font-mono uppercase text-slate-400 font-medium tracking-wider mb-2.5 flex items-center gap-1.5">
              <BarChart3 className="w-3.5 h-3.5 text-blue-400" /> Primary Key Performance Indicators
            </div>

            <div className={`grid gap-3 ${
              parsed.kpis.length === 1
                ? "grid-cols-1 max-w-sm"
                : parsed.kpis.length === 2
                ? "grid-cols-1 sm:grid-cols-2"
                : parsed.kpis.length === 3
                ? "grid-cols-1 sm:grid-cols-3"
                : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
            }`}>
              {parsed.kpis.map((kpi) => (
                <div
                  key={kpi.id}
                  className="relative group bg-slate-950/70 border border-slate-800/80 hover:border-slate-700/80 rounded-xl p-4 transition-all duration-200 shadow-md hover:shadow-lg hover:shadow-blue-500/5 flex flex-col justify-between"
                >
                  {/* Subtle top indicator line */}
                  <div className="absolute top-0 left-4 right-4 h-[1.5px] bg-gradient-to-r from-blue-500/40 via-sky-400/40 to-transparent rounded-full" />

                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-mono uppercase text-slate-400 font-medium tracking-wider truncate pr-2">
                      {kpi.label}
                    </span>
                    <div className="p-1.5 rounded-lg bg-slate-900 border border-slate-800">
                      {getKpiIcon(kpi.label)}
                    </div>
                  </div>

                  <div className="mt-1">
                    <div className="text-2xl font-bold font-mono tracking-tight text-white group-hover:text-sky-200 transition">
                      {kpi.value}
                    </div>
                    {kpi.subtext && (
                      <p className="mt-1 text-[11px] text-slate-400 line-clamp-2">
                        {renderCleanFormattedText(kpi.subtext)}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section 3: Strategic Insights & Key Takeaways */}
        {parsed.insights.length > 0 && (
          <div className="space-y-2">
            <div className="text-[11px] font-mono uppercase text-slate-400 font-medium tracking-wider mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> Analytical Takeaways &amp; Breakdown
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {parsed.insights.map((insight, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950/50 border border-slate-800/80 rounded-xl p-3.5 flex items-start gap-3 text-xs"
                >
                  <div className="p-1 rounded-md bg-sky-500/10 border border-sky-500/20 text-sky-400 flex-shrink-0 mt-0.5">
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                  <div className="space-y-0.5">
                    <span className="font-semibold text-slate-200 block">
                      {renderCleanFormattedText(insight.title)}
                    </span>
                    <p className="text-slate-300 leading-relaxed font-normal">
                      {renderCleanFormattedText(insight.body)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section 4: Structured Tabular Breakdown */}
        {parsed.table && (
          <div className="rounded-xl border border-slate-800/90 bg-slate-950/70 overflow-hidden shadow-lg">
            <div className="px-4 py-2.5 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <TableIcon className="w-4 h-4 text-sky-400" />
                <span className="text-xs font-mono uppercase tracking-wider text-slate-200 font-semibold">
                  Tabular Breakdown
                </span>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                {parsed.table.rows.length} {parsed.table.rows.length === 1 ? "row" : "rows"}
              </span>
            </div>

            <div className="overflow-x-auto max-h-80 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 bg-slate-900/95 backdrop-blur border-b border-slate-800 text-slate-300 font-mono text-[11px] uppercase tracking-wider z-10">
                  <tr>
                    {parsed.table.headers.map((header, hIdx) => {
                      const isNumeric =
                        header.toLowerCase().includes("sales") ||
                        header.toLowerCase().includes("total") ||
                        header.toLowerCase().includes("price") ||
                        header.toLowerCase().includes("amount") ||
                        header.toLowerCase().includes("quantity") ||
                        header.toLowerCase().includes("count");
                      return (
                        <th
                          key={hIdx}
                          className={`px-4 py-3 font-semibold ${isNumeric ? "text-right" : "text-left"}`}
                        >
                          {header.replace(/_/g, " ")}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {parsed.table.rows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      className="hover:bg-slate-900/60 transition-colors group"
                    >
                      {row.map((cell, cIdx) => {
                        const isMoney = cell.startsWith("$") || cell.includes("$");
                        const isNum = !isNaN(Number(cell.replace(/[$,\s%*]/g, ""))) && cell.length > 0;
                        const isRightAligned = isMoney || isNum;
                        return (
                          <td
                            key={cIdx}
                            className={`px-4 py-2.5 ${
                              isRightAligned ? "text-right" : "text-left"
                            } ${
                              isMoney
                                ? "text-emerald-400 font-semibold group-hover:text-emerald-300"
                                : "text-slate-300 group-hover:text-slate-100"
                            }`}
                          >
                            {renderCleanFormattedText(cell)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {parsed.table.footnote && (
              <div className="px-4 py-2.5 bg-slate-900/50 border-t border-slate-800 text-[11px] text-slate-400 italic flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" />
                <span>{renderCleanFormattedText(parsed.table.footnote)}</span>
              </div>
            )}
          </div>
        )}

        {/* Section 5: Concluding Observations */}
        {parsed.outroParagraphs.length > 0 && (
          <div className="text-xs text-slate-400 italic bg-slate-950/30 border border-slate-800/50 rounded-lg p-3 space-y-1">
            {parsed.outroParagraphs.map((para, idx) => (
              <p key={idx}>{renderCleanFormattedText(para)}</p>
            ))}
          </div>
        )}

        {/* Section 5: Integrated Dynamic Chart */}
        {message.chart && (
          <div className="pt-2">
            <DynamicChart spec={message.chart} />
          </div>
        )}

        {/* Section 6: Grounding Verification Badge */}
        {message.grounding && (
          <div className="pt-3 border-t border-slate-800/70">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                    message.grounding.grounding_precision >= 0.9
                      ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400"
                      : "bg-amber-500/10 border border-amber-500/30 text-amber-300"
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  {Math.round(message.grounding.grounding_precision * 100)}% Grounded in Data
                </span>

                <span className="text-[11px] text-slate-400 bg-slate-950 border border-slate-800 px-2 py-0.5 rounded">
                  Table Recall: {(message.grounding.table_recall * 100).toFixed(0)}%
                </span>

                {message.grounding.feasibility_status === "FEASIBLE" && (
                  <span className="text-[11px] text-sky-400 bg-sky-950/40 border border-sky-800/60 px-2 py-0.5 rounded">
                    Feasible Query
                  </span>
                )}
              </div>

              {message.grounding.supported_claims.length > 0 && (
                <button
                  onClick={() => setIsGroundingExpanded(!isGroundingExpanded)}
                  className="text-[11px] text-slate-400 hover:text-slate-200 transition"
                >
                  {isGroundingExpanded
                    ? "Hide Claims Audit"
                    : `Audit ${message.grounding.supported_claims.length} Claims`}
                </button>
              )}
            </div>

            {/* Expandable Grounding Audit Details */}
            {isGroundingExpanded && (
              <div className="mt-2.5 bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-xs space-y-2">
                <div>
                  <span className="text-[10px] uppercase font-mono text-emerald-400 font-semibold block mb-1">
                    Verified Numeric Claims ({message.grounding.supported_claims.length})
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {message.grounding.supported_claims.map((claim, idx) => (
                      <span
                        key={idx}
                        className="bg-emerald-950/50 border border-emerald-800/60 text-emerald-300 font-mono text-[11px] px-2 py-0.5 rounded"
                      >
                        {claim}
                      </span>
                    ))}
                  </div>
                </div>

                {message.grounding.notes.length > 0 && (
                  <div className="pt-1 text-[11px] text-slate-400 italic">
                    Notes: {message.grounding.notes.join("; ")}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Section 7: Audit & SQL Inspection Drawer */}
        {message.sql_query && (
          <div className="pt-2 border-t border-slate-800/70">
            <button
              onClick={() => setIsTraceExpanded(!isTraceExpanded)}
              className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1.5 transition font-medium"
            >
              <Terminal className="w-3.5 h-3.5" />
              {isTraceExpanded
                ? "Hide SQL & Execution Trace"
                : "Inspect SQL & Deterministic Execution Trace"}
              {isTraceExpanded ? (
                <ChevronUp className="w-3.5 h-3.5" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5" />
              )}
            </button>

            {isTraceExpanded && (
              <div className="mt-3 space-y-3 bg-slate-950/90 border border-slate-800 p-4 rounded-xl text-xs">
                {/* Execution Metrics Bar */}
                {message.metrics && (
                  <div className="flex flex-wrap items-center gap-4 text-slate-400 border-b border-slate-800 pb-2">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-blue-400" />
                      Runtime: <strong>{message.metrics.execution_time_ms} ms</strong>
                    </span>
                    <span className="flex items-center gap-1">
                      <TableIcon className="w-3.5 h-3.5 text-purple-400" />
                      Rows: <strong>{message.metrics.row_count}</strong>
                    </span>
                    {message.metrics.tables_used.length > 0 && (
                      <span className="flex items-center gap-1">
                        <Layers className="w-3.5 h-3.5 text-emerald-400" />
                        Tables: <strong>{message.metrics.tables_used.join(", ")}</strong>
                      </span>
                    )}
                  </div>
                )}

                {/* SQL Code Block */}
                <div className="relative group">
                  <div className="flex items-center justify-between text-slate-400 mb-1">
                    <span className="font-mono text-[11px] text-slate-500 uppercase">
                      DuckDB SQL
                    </span>
                    {onCopySQL && (
                      <button
                        onClick={() => onCopySQL(message.sql_query!, message.id)}
                        className="text-slate-400 hover:text-slate-200 transition flex items-center gap-1 text-[11px]"
                      >
                        {copiedId === message.id ? (
                          <>
                            <Check className="w-3 h-3 text-emerald-400" /> Copied
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3" /> Copy SQL
                          </>
                        )}
                      </button>
                    )}
                  </div>
                  <pre className="bg-slate-900 border border-slate-800/80 rounded-lg p-3 overflow-x-auto text-[11px] font-mono text-sky-300">
                    {message.sql_query}
                  </pre>
                </div>

                {/* Raw Data Preview Table */}
                {message.data_preview && message.data_preview.length > 0 && (
                  <div>
                    <span className="font-mono text-[11px] text-slate-500 uppercase block mb-1">
                      Data Preview ({message.data_preview.length} rows)
                    </span>
                    <div className="max-h-48 overflow-y-auto border border-slate-800 rounded-lg">
                      <table className="w-full text-left text-[11px] border-collapse">
                        <thead className="bg-slate-900 text-slate-400 sticky top-0">
                          <tr>
                            {Object.keys(message.data_preview[0]).map((k) => (
                              <th key={k} className="py-1.5 px-2.5 border-b border-slate-800">
                                {k}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                          {message.data_preview.slice(0, 15).map((row, rIdx) => (
                            <tr key={rIdx} className="hover:bg-slate-800/20">
                              {Object.values(row).map((val: any, cIdx) => (
                                <td key={cIdx} className="py-1.5 px-2.5 text-slate-300">
                                  {typeof val === "number"
                                    ? val.toLocaleString(undefined, { maximumFractionDigits: 2 })
                                    : String(val)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
