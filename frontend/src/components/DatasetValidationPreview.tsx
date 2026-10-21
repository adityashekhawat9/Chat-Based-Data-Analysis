"use client";

import React, { useState } from "react";
import {
  ValidationResponse,
  RegisteredDataset,
} from "@/types/dataset";
import {
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  Copy,
  RefreshCw,
  X,
  Database,
  FileSpreadsheet,
  Columns,
  Table as TableIcon,
  ShieldAlert,
  ArrowRight,
} from "lucide-react";

interface Props {
  validation: ValidationResponse;
  onAccept: (dataset: RegisteredDataset) => void;
  onRetry: () => void;
  onCancel: () => void;
  apiUrl?: string;
  tenantId?: string;
}

export default function DatasetValidationPreview({
  validation,
  onAccept,
  onRetry,
  onCancel,
  apiUrl = "http://localhost:8000",
  tenantId = "default_tenant",
}: Props) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [customTableName, setCustomTableName] = useState(
    validation.filename.replace(/\.[^/.]+$/, "").replace(/[^\w]/g, "_")
  );

  const blockingIssues = validation.issues.filter(
    (i) => i.severity === "BLOCKING"
  );
  const warningIssues = validation.issues.filter(
    (i) => i.severity === "WARNING"
  );

  const handleRegister = async () => {
    if (!validation.can_register) return;
    setIsRegistering(true);
    setErrorMsg(null);

    try {
      const res = await fetch(`${apiUrl}/api/datasets/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify({
          session_id: validation.session_id,
          content_hash: validation.content_hash,
          table_name: customTableName || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Registration failed" }));
        throw new Error(errData.detail || "Registration failed");
      }

      const registered: RegisteredDataset = await res.json();
      onAccept(registered);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to register dataset.");
    } finally {
      setIsRegistering(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl p-6 text-slate-100 max-w-4xl mx-auto my-6 transition-all">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-5">
        <div className="flex items-center space-x-3">
          <div
            className={`p-2.5 rounded-lg ${
              blockingIssues.length > 0
                ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                : warningIssues.length > 0
                ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            }`}
          >
            {blockingIssues.length > 0 ? (
              <AlertOctagon className="w-6 h-6" />
            ) : warningIssues.length > 0 ? (
              <AlertTriangle className="w-6 h-6" />
            ) : (
              <CheckCircle2 className="w-6 h-6" />
            )}
          </div>
          <div>
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <span>{validation.filename}</span>
              {validation.is_duplicate && (
                <span className="text-xs bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Copy className="w-3 h-3" /> Duplicate Detected
                </span>
              )}
            </h2>
            <p className="text-sm text-slate-400">
              SHA-256:{" "}
              <code className="text-xs bg-slate-800/80 px-1.5 py-0.5 rounded text-slate-300 font-mono">
                {validation.content_hash.substring(0, 16)}...
              </code>{" "}
              &bull; Size: {formatBytes(validation.file_size_bytes)}
            </p>
          </div>
        </div>

        <button
          onClick={onCancel}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          title="Cancel and close"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <div className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3">
          <span className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
            <TableIcon className="w-3.5 h-3.5 text-blue-400" /> Row Count
          </span>
          <span className="text-xl font-bold text-slate-100">
            {validation.row_count.toLocaleString()}
          </span>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3">
          <span className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
            <Columns className="w-3.5 h-3.5 text-purple-400" /> Column Count
          </span>
          <span className="text-xl font-bold text-slate-100">
            {validation.column_count}
          </span>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3">
          <span className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> Blocking Errors
          </span>
          <span
            className={`text-xl font-bold ${
              blockingIssues.length > 0 ? "text-rose-400" : "text-slate-400"
            }`}
          >
            {blockingIssues.length}
          </span>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3">
          <span className="text-xs text-slate-400 flex items-center gap-1.5 mb-1">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Warnings
          </span>
          <span
            className={`text-xl font-bold ${
              warningIssues.length > 0 ? "text-amber-400" : "text-slate-400"
            }`}
          >
            {warningIssues.length}
          </span>
        </div>
      </div>

      {/* Blocking Issues Alert Box */}
      {blockingIssues.length > 0 && (
        <div className="mb-5 p-4 rounded-xl bg-rose-950/40 border border-rose-800/50 text-rose-200">
          <h3 className="font-semibold text-rose-300 flex items-center gap-2 mb-2">
            <AlertOctagon className="w-4 h-4 text-rose-400" />
            Blocking Ingestion Errors (Registration Prohibited)
          </h3>
          <p className="text-xs text-rose-300/80 mb-3">
            The dataset violates structural or security requirements and cannot be
            registered or queried until corrected.
          </p>
          <div className="space-y-2">
            {blockingIssues.map((issue, idx) => (
              <div
                key={idx}
                className="bg-rose-900/30 border border-rose-800/40 rounded-lg p-3 text-sm"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs font-semibold bg-rose-950 px-2 py-0.5 rounded text-rose-300">
                    {issue.code}
                  </span>
                  {issue.column && (
                    <span className="text-xs text-rose-300">
                      Column: <strong>{issue.column}</strong>
                    </span>
                  )}
                </div>
                <p className="text-rose-100">{issue.message}</p>
                <p className="text-xs text-rose-300/90 mt-1 italic">
                  Action: {issue.recommended_action}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings Box */}
      {warningIssues.length > 0 && (
        <div className="mb-5 p-4 rounded-xl bg-amber-950/30 border border-amber-800/40 text-amber-200">
          <h3 className="font-semibold text-amber-300 flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Data Quality Warnings (Non-Blocking)
          </h3>
          <p className="text-xs text-amber-300/80 mb-3">
            The dataset is structurally sound and can be registered. However, the
            following data hygiene notes were detected:
          </p>
          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
            {warningIssues.map((issue, idx) => (
              <div
                key={idx}
                className="bg-amber-900/20 border border-amber-800/30 rounded-lg p-2.5 text-sm"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-xs font-semibold bg-amber-950 px-2 py-0.5 rounded text-amber-300">
                    {issue.code}
                  </span>
                  {issue.column && (
                    <span className="text-xs text-amber-300">
                      Column: <strong>{issue.column}</strong>
                    </span>
                  )}
                </div>
                <p className="text-amber-100 text-xs sm:text-sm">{issue.message}</p>
                <p className="text-xs text-amber-300/80 mt-1 italic">
                  Tip: {issue.recommended_action}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Column Schema Preview Table */}
      {validation.column_profiles.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-slate-400" />
            Inferred Column Schemas ({validation.column_profiles.length} columns)
          </h3>
          <div className="max-h-56 overflow-y-auto border border-slate-800 rounded-lg">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-800/80 text-slate-300 sticky top-0">
                <tr>
                  <th className="py-2 px-3">Column Name</th>
                  <th className="py-2 px-3">Type</th>
                  <th className="py-2 px-3">Nulls</th>
                  <th className="py-2 px-3">Unique</th>
                  <th className="py-2 px-3">Sample Values</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-900/50">
                {validation.column_profiles.map((col, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/30 transition">
                    <td className="py-2 px-3 font-medium text-slate-200">
                      {col.name}
                      {col.raw_name !== col.name && (
                        <span className="block text-[10px] text-slate-500 font-mono">
                          raw: {col.raw_name}
                        </span>
                      )}
                    </td>
                    <td className="py-2 px-3">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-sky-400 font-mono text-[11px]">
                        {col.inferred_type}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={
                          col.null_count > 0 ? "text-amber-400" : "text-slate-400"
                        }
                      >
                        {col.null_count} ({col.null_percentage}%)
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-300">
                      {col.is_unique ? "Yes" : col.unique_count.toLocaleString()}
                    </td>
                    <td className="py-2 px-3 text-slate-400 truncate max-w-xs">
                      {col.sample_values.join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Target Table Name Input */}
      {validation.can_register && (
        <div className="mb-5 bg-slate-800/30 border border-slate-800 p-3 rounded-lg flex flex-col sm:flex-row items-center gap-3">
          <label className="text-xs text-slate-300 font-medium whitespace-nowrap">
            DuckDB Table Name:
          </label>
          <input
            type="text"
            value={customTableName}
            onChange={(e) => setCustomTableName(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-100 rounded px-3 py-1.5 text-sm flex-1 font-mono focus:outline-none focus:border-blue-500"
            placeholder="orders"
          />
        </div>
      )}

      {errorMsg && (
        <div className="mb-4 p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-sm">
          {errorMsg}
        </div>
      )}

      {/* Action Buttons: Accept, Retry, Cancel */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800">
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
        >
          Cancel
        </button>

        <div className="flex items-center gap-3">
          <button
            onClick={onRetry}
            className="px-4 py-2 rounded-lg text-sm font-medium border border-slate-700 text-slate-300 hover:bg-slate-800 transition flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" /> Retry / Re-upload
          </button>

          <button
            onClick={handleRegister}
            disabled={!validation.can_register || isRegistering}
            className={`px-5 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 ${
              validation.can_register
                ? "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/30"
                : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50"
            }`}
          >
            {isRegistering ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" /> Registering...
              </>
            ) : (
              <>
                <Database className="w-4 h-4" />
                {validation.is_duplicate ? "Use Existing Dataset" : "Accept & Register"}
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
