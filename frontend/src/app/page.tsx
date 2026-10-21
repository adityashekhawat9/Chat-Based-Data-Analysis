"use client";

import React, { useState, useEffect } from "react";
import {
  Database,
  FileCheck2,
  Layers,
  Sparkles,
  ShieldCheck,
  Server,
  RefreshCw,
  FolderOpen,
  MessageSquare,
  UploadCloud,
  CheckCircle2,
  FileSpreadsheet,
  Building2,
  ChevronDown,
} from "lucide-react";
import CsvUploader from "@/components/CsvUploader";
import ChatInterface from "@/components/ChatInterface";
import { RegisteredDataset } from "@/types/dataset";

const PRESET_TENANTS = [
  { id: "default_tenant", label: "Default Tenant" },
  { id: "tenant_alpha", label: "Tenant Alpha (Org 1)" },
  { id: "tenant_beta", label: "Tenant Beta (Org 2)" },
];

export default function Home() {
  const [sessionId, setSessionId] = useState<string>("");
  const [tenantId, setTenantId] = useState<string>("default_tenant");
  const [datasets, setDatasets] = useState<RegisteredDataset[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(false);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "upload">("chat");
  const [isCustomTenant, setIsCustomTenant] = useState(false);
  const [customTenantInput, setCustomTenantInput] = useState("");

  useEffect(() => {
    // Generate or restore session ID
    let currentSession = localStorage.getItem("data_analysis_session_id");
    if (!currentSession) {
      currentSession = `sess_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
      localStorage.setItem("data_analysis_session_id", currentSession);
    }
    setSessionId(currentSession);

    // Restore tenant ID
    const savedTenant = localStorage.getItem("data_analysis_tenant_id") || "default_tenant";
    setTenantId(savedTenant);
    if (!PRESET_TENANTS.some((t) => t.id === savedTenant)) {
      setIsCustomTenant(true);
      setCustomTenantInput(savedTenant);
    }

    fetchRegisteredDatasets(currentSession, savedTenant);
  }, []);

  const fetchRegisteredDatasets = async (sessId: string, currentTenant: string) => {
    setIsLoadingDatasets(true);
    try {
      const res = await fetch(`http://localhost:8000/api/datasets/sessions/${sessId}`, {
        headers: {
          "X-Tenant-ID": currentTenant,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setDatasets(data.datasets || []);
      }
    } catch (e) {
      console.error("Failed to load session datasets", e);
    } finally {
      setIsLoadingDatasets(false);
    }
  };

  const handleTenantChange = (newTenant: string) => {
    setTenantId(newTenant);
    localStorage.setItem("data_analysis_tenant_id", newTenant);
    if (sessionId) {
      fetchRegisteredDatasets(sessionId, newTenant);
    }
  };

  const handleDatasetRegistered = (newDataset: RegisteredDataset) => {
    setDatasets((prev) => {
      const exists = prev.some((d) => d.content_hash === newDataset.content_hash);
      if (exists) return prev;
      return [newDataset, ...prev];
    });
  };

  const handleLoadSample = async () => {
    if (!sessionId || isLoadingSample) return;
    setIsLoadingSample(true);
    try {
      const res = await fetch("http://localhost:8000/api/datasets/load-sample", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (res.ok) {
        const data = await res.json();
        setDatasets(data.datasets || []);
      }
    } catch (e) {
      console.error("Failed to load sample dataset", e);
    } finally {
      setIsLoadingSample(false);
    }
  };

  const handleNewSession = () => {
    const newSession = `sess_${Math.random().toString(36).substring(2, 10)}_${Date.now()}`;
    localStorage.setItem("data_analysis_session_id", newSession);
    setSessionId(newSession);
    setDatasets([]);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-500/30">
      {/* Top Navigation */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-gradient-to-tr from-blue-600 to-indigo-500 rounded-xl shadow-lg shadow-blue-500/20">
              <Database className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
                Data Analysis Chat
                <span className="text-[10px] font-semibold uppercase tracking-wider bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full">
                  PoC
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Deterministic DuckDB Queries &bull; SSE Streaming &bull; Multi-Tenant
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {/* Multi-Tenant Switcher */}
            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 rounded-lg p-1 text-xs">
              <Building2 className="w-3.5 h-3.5 text-indigo-400 ml-1.5 flex-shrink-0" />
              <select
                value={isCustomTenant ? "custom" : tenantId}
                onChange={(e) => {
                  if (e.target.value === "custom") {
                    setIsCustomTenant(true);
                  } else {
                    setIsCustomTenant(false);
                    handleTenantChange(e.target.value);
                  }
                }}
                className="bg-transparent text-slate-200 text-xs font-medium focus:outline-none pr-2 cursor-pointer"
              >
                {PRESET_TENANTS.map((t) => (
                  <option key={t.id} value={t.id} className="bg-slate-900 text-slate-200">
                    {t.label}
                  </option>
                ))}
                <option value="custom" className="bg-slate-900 text-slate-200">
                  + Custom Tenant
                </option>
              </select>

              {isCustomTenant && (
                <div className="flex items-center gap-1">
                  <input
                    type="text"
                    value={customTenantInput}
                    onChange={(e) => setCustomTenantInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && customTenantInput.trim()) {
                        handleTenantChange(customTenantInput.trim());
                      }
                    }}
                    placeholder="tenant_id"
                    className="bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-xs text-sky-300 w-24 font-mono focus:outline-none"
                  />
                  <button
                    onClick={() => {
                      if (customTenantInput.trim()) {
                        handleTenantChange(customTenantInput.trim());
                      }
                    }}
                    className="text-[10px] bg-blue-600 hover:bg-blue-500 text-white px-2 py-0.5 rounded"
                  >
                    Set
                  </button>
                </div>
              )}
            </div>

            {datasets.length === 0 && (
              <button
                onClick={handleLoadSample}
                disabled={isLoadingSample}
                className="text-xs bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-300 hover:text-white px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 font-medium shadow-sm"
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                {isLoadingSample ? "Loading 8 Tables..." : "Preload Sample Dataset"}
              </button>
            )}

            <div className="hidden lg:flex items-center space-x-2 text-xs bg-slate-800/80 border border-slate-700/60 px-3 py-1.5 rounded-lg text-slate-300">
              <span className="text-slate-500">Session:</span>
              <code className="font-mono text-sky-400 font-medium">
                {sessionId ? sessionId.substring(0, 14) : "initializing..."}...
              </code>
            </div>

            <button
              onClick={handleNewSession}
              className="text-xs border border-slate-700 hover:border-slate-600 bg-slate-800/60 hover:bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg transition flex items-center gap-1.5"
              title="Create a fresh session"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              New Session
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveTab("chat")}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition flex items-center gap-2 ${
                activeTab === "chat"
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <MessageSquare className="w-4 h-4" />
              Data Analysis Chat
            </button>

            <button
              onClick={() => setActiveTab("upload")}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition flex items-center gap-2 ${
                activeTab === "upload"
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <UploadCloud className="w-4 h-4" />
              Upload &amp; Validation ({datasets.length})
            </button>
          </div>

          <div className="text-xs text-slate-400 hidden sm:flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>DuckDB Catalog: <strong>{datasets.length} tables</strong></span>
            </div>
            <span className="text-slate-600">&bull;</span>
            <div className="text-slate-400">
              Tenant DB: <code className="font-mono text-sky-400">{tenantId}</code>
            </div>
          </div>
        </div>

        {/* Tab 1: Chat Interface */}
        {activeTab === "chat" && (
          <div className="space-y-4">
            <ChatInterface
              sessionId={sessionId}
              tenantId={tenantId}
              hasDatasets={datasets.length > 0}
              onLoadSample={handleLoadSample}
            />
          </div>
        )}

        {/* Tab 2: Upload & Validation */}
        {activeTab === "upload" && (
          <div className="space-y-8">
            {/* Upload Area */}
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                    <FileCheck2 className="w-5 h-5 text-blue-400" />
                    Validate &amp; Ingest CSV Files
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Isolated physical database for tenant: <code className="text-sky-400 font-mono">{tenantId}</code>
                  </p>
                </div>
                {datasets.length === 0 && (
                  <button
                    onClick={handleLoadSample}
                    disabled={isLoadingSample}
                    className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg transition"
                  >
                    {isLoadingSample ? "Loading..." : "Load Default 8 Tables"}
                  </button>
                )}
              </div>

              <CsvUploader
                sessionId={sessionId}
                tenantId={tenantId}
                onDatasetRegistered={handleDatasetRegistered}
              />
            </section>

            {/* Registered Datasets Table */}
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-indigo-400" />
                  <h3 className="text-lg font-semibold text-slate-100">
                    Active Catalog Tables for {tenantId} ({datasets.length})
                  </h3>
                </div>
                <button
                  onClick={() => sessionId && fetchRegisteredDatasets(sessionId, tenantId)}
                  className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 transition"
                >
                  <RefreshCw
                    className={`w-3.5 h-3.5 ${isLoadingDatasets ? "animate-spin" : ""}`}
                  />
                  Refresh Catalog
                </button>
              </div>

              {datasets.length === 0 ? (
                <div className="border border-slate-800 rounded-xl p-8 text-center bg-slate-900/40 text-slate-400 space-y-2">
                  <FolderOpen className="w-8 h-8 text-slate-600 mx-auto" />
                  <p className="text-sm font-medium text-slate-300">
                    No datasets registered in this tenant catalog yet.
                  </p>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    Upload CSV files above or click &apos;Preload Sample Dataset&apos; to mount
                    the 8 ecommerce tables into the tenant&apos;s DuckDB analytical engine.
                  </p>
                </div>
              ) : (
                <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-900/60 shadow-xl">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead className="bg-slate-800/80 text-slate-300 border-b border-slate-800 text-xs uppercase tracking-wider">
                      <tr>
                        <th className="py-3 px-4">DuckDB Table</th>
                        <th className="py-3 px-4">Dataset ID &amp; Hash</th>
                        <th className="py-3 px-4">Source File</th>
                        <th className="py-3 px-4 text-right">Rows</th>
                        <th className="py-3 px-4 text-right">Cols</th>
                        <th className="py-3 px-4">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 text-slate-200 text-xs sm:text-sm">
                      {datasets.map((ds) => (
                        <tr
                          key={ds.dataset_id}
                          className="hover:bg-slate-800/40 transition"
                        >
                          <td className="py-3 px-4 font-mono font-semibold text-sky-400 flex items-center gap-2">
                            <Database className="w-4 h-4 text-sky-500" />
                            {ds.table_name}
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-mono text-xs text-slate-300 block">
                              {ds.dataset_id}
                            </span>
                            <span className="font-mono text-[10px] text-slate-500 block truncate max-w-[200px]">
                              sha256: {ds.content_hash}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-slate-300">{ds.filename}</td>
                          <td className="py-3 px-4 text-right font-mono text-slate-100">
                            {ds.row_count.toLocaleString()}
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-slate-100">
                            {ds.column_count}
                          </td>
                          <td className="py-3 px-4">
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                              Ready for Query
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}

        {/* System Safeguards Footer */}
        <section className="bg-slate-900/30 border border-slate-800/60 rounded-xl p-5 text-xs text-slate-400 grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="space-y-1">
            <h4 className="font-semibold text-slate-300 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Zero Arbitrary Code Execution
            </h4>
            <p>
              Queries are strictly executed as syntax-validated, read-only SQL queries
              in DuckDB. Arbitrary Python code execution is strictly prohibited.
            </p>
          </div>
          <div className="space-y-1">
            <h4 className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Server className="w-4 h-4 text-blue-400" />
              Deterministic Relational Engine
            </h4>
            <p>
              All arithmetic, revenue sums, and date aggregations are computed
              deterministically. The LLM only interprets intent and plans queries.
            </p>
          </div>
          <div className="space-y-1">
            <h4 className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Building2 className="w-4 h-4 text-indigo-400" />
              Physical Multi-Tenancy
            </h4>
            <p>
              Each tenant is physically isolated into separate DuckDB database catalogs
              with sanitized directory paths preventing cross-tenant data exposure.
            </p>
          </div>
          <div className="space-y-1">
            <h4 className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Database className="w-4 h-4 text-purple-400" />
              Grounding &amp; Tracing
            </h4>
            <p>
              Every response evaluates numeric precision ($Precision_&#123;grounding&#125;$), table recall,
              and generates persistent JSONL audit spans with unique trace IDs.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
