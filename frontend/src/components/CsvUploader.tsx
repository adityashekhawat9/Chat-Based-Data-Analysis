"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  UploadCloud,
  FileSpreadsheet,
  AlertCircle,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  RefreshCw,
  HardDrive,
  Layers,
  ArrowRight,
  Trash2,
  Eye,
  X,
  Database,
  Plus,
  Clock,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import {
  ValidationResponse,
  RegisteredDataset,
  BatchQueueItem,
  BatchItemStatus,
  BatchRegisterResponse,
} from "@/types/dataset";
import DatasetValidationPreview from "./DatasetValidationPreview";

interface Props {
  sessionId: string;
  onDatasetRegistered: (dataset: RegisteredDataset) => void;
  apiUrl?: string;
  tenantId?: string;
}

const CHUNK_SIZE = 5 * 1024 * 1024; // 5 MB per slice

export default function CsvUploader({
  sessionId,
  onDatasetRegistered,
  apiUrl = "http://localhost:8000",
  tenantId = "default_tenant",
}: Props) {
  const [queue, setQueue] = useState<BatchQueueItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [inspectingItem, setInspectingItem] = useState<BatchQueueItem | null>(null);
  const [isRegisteringAll, setIsRegisteringAll] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const isProcessingRef = useRef<boolean>(false);
  const queueRef = useRef<BatchQueueItem[]>([]);

  // Keep queueRef in sync with queue state
  useEffect(() => {
    queueRef.current = queue;
  }, [queue]);

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const updateQueueItem = useCallback(
    (id: string, patch: Partial<BatchQueueItem>) => {
      setQueue((prev) =>
        prev.map((item) => (item.id === id ? { ...item, ...patch } : item))
      );
    },
    []
  );

  // ---------------------------------------------------------------------------
  // Queue Processing Engine (Sequential ingestion to avoid DuckDB lock contention)
  // ---------------------------------------------------------------------------
  const processNextInQueue = useCallback(async () => {
    if (isProcessingRef.current) return;

    // Find the next item that needs validation
    const nextItem = queueRef.current.find((item) => item.status === "queued");
    if (!nextItem) {
      isProcessingRef.current = false;
      return;
    }

    isProcessingRef.current = true;

    try {
      if (nextItem.size <= CHUNK_SIZE) {
        await processDirectValidation(nextItem);
      } else {
        await processChunkedValidation(nextItem);
      }
    } catch (err: any) {
      updateQueueItem(nextItem.id, {
        status: "failed",
        errorMessage: err.message || "Failed to process dataset.",
      });
    } finally {
      isProcessingRef.current = false;
      // Trigger next item in queue
      setTimeout(() => {
        processNextInQueue();
      }, 100);
    }
  }, [apiUrl, sessionId, tenantId, updateQueueItem]);

  // Start queue processing whenever queued items are present
  const startQueueProcessing = useCallback(() => {
    if (!isProcessingRef.current) {
      processNextInQueue();
    }
  }, [processNextInQueue]);

  // ---------------------------------------------------------------------------
  // Direct Validation for files <= 5MB
  // ---------------------------------------------------------------------------
  const processDirectValidation = async (item: BatchQueueItem) => {
    updateQueueItem(item.id, {
      status: "validating",
      progressPercent: 50,
      errorMessage: undefined,
    });

    const formData = new FormData();
    formData.append("file", item.file);
    formData.append("session_id", sessionId);

    try {
      const res = await fetch(`${apiUrl}/api/datasets/validate`, {
        method: "POST",
        headers: {
          "X-Tenant-ID": tenantId,
        },
        body: formData,
      });

      const data: ValidationResponse = await res.json();
      const hasBlocking = !data.can_register;

      updateQueueItem(item.id, {
        status: hasBlocking ? "blocked" : "validated",
        progressPercent: 100,
        validationResult: data,
        errorMessage: hasBlocking
          ? data.issues.find((i) => i.severity === "BLOCKING")?.message ||
            "Validation blocked due to critical issues."
          : undefined,
      });
    } catch (err: any) {
      updateQueueItem(item.id, {
        status: "failed",
        progressPercent: 0,
        errorMessage:
          err.message || "Failed to connect to backend validation service.",
      });
    }
  };

  // ---------------------------------------------------------------------------
  // Resumable Chunked Multipart Validation for files > 5MB
  // ---------------------------------------------------------------------------
  const processChunkedValidation = async (
    item: BatchQueueItem,
    resumeUploadId?: string
  ) => {
    updateQueueItem(item.id, {
      status: "uploading",
      progressPercent: 5,
      errorMessage: undefined,
    });

    const file = item.file;
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    try {
      let uploadId = resumeUploadId;
      let alreadyUploaded: number[] = [];

      if (!uploadId) {
        // Step 1: Initialize chunk session
        const initRes = await fetch(`${apiUrl}/api/datasets/upload/init`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Tenant-ID": tenantId,
          },
          body: JSON.stringify({
            session_id: sessionId,
            filename: file.name,
            file_size_bytes: file.size,
            total_chunks: totalChunks,
            chunk_size_bytes: CHUNK_SIZE,
          }),
        });

        if (!initRes.ok) {
          const errData = await initRes.json().catch(() => ({}));
          throw new Error(errData.detail || "Failed to initialize chunked upload.");
        }

        const initData = await initRes.json();
        uploadId = initData.upload_id;
        alreadyUploaded = initData.uploaded_chunks || [];
      } else {
        // Check current status on resume
        const statusRes = await fetch(
          `${apiUrl}/api/datasets/upload/status?upload_id=${uploadId}`,
          {
            headers: { "X-Tenant-ID": tenantId },
          }
        );
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          alreadyUploaded = statusData.uploaded_chunks || [];
        }
      }

      updateQueueItem(item.id, {
        chunkProgress: {
          current: alreadyUploaded.length,
          total: totalChunks,
          uploadedChunks: alreadyUploaded,
          uploadId: uploadId!,
          isPaused: false,
        },
        progressPercent: Math.round((alreadyUploaded.length / totalChunks) * 100),
      });

      // Step 2: Upload missing chunks sequentially
      for (let i = 0; i < totalChunks; i++) {
        if (alreadyUploaded.includes(i)) continue;

        const start = i * CHUNK_SIZE;
        const end = Math.min(file.size, start + CHUNK_SIZE);
        const chunkBlob = file.slice(start, end);

        const chunkFormData = new FormData();
        chunkFormData.append("upload_id", uploadId!);
        chunkFormData.append("chunk_index", i.toString());
        chunkFormData.append("chunk_file", chunkBlob, `part_${i}.part`);

        const chunkRes = await fetch(`${apiUrl}/api/datasets/upload/chunk`, {
          method: "POST",
          headers: {
            "X-Tenant-ID": tenantId,
          },
          body: chunkFormData,
        });

        if (!chunkRes.ok) {
          const errData = await chunkRes.json().catch(() => ({}));
          throw new Error(
            `Failed uploading chunk ${i + 1} of ${totalChunks}: ${
              errData.detail || chunkRes.statusText
            }`
          );
        }

        alreadyUploaded.push(i);
        const pct = Math.round((alreadyUploaded.length / totalChunks) * 100);

        updateQueueItem(item.id, {
          chunkProgress: {
            current: alreadyUploaded.length,
            total: totalChunks,
            uploadedChunks: [...alreadyUploaded],
            uploadId: uploadId!,
            isPaused: false,
          },
          progressPercent: pct,
        });
      }

      // Step 3: Complete & Assemble on server
      updateQueueItem(item.id, {
        status: "validating",
        progressPercent: 95,
      });

      const completeRes = await fetch(`${apiUrl}/api/datasets/upload/complete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify({ upload_id: uploadId }),
      });

      const validationData: ValidationResponse = await completeRes.json();
      const hasBlocking = !validationData.can_register;

      updateQueueItem(item.id, {
        status: hasBlocking ? "blocked" : "validated",
        progressPercent: 100,
        validationResult: validationData,
        errorMessage: hasBlocking
          ? validationData.issues.find((i) => i.severity === "BLOCKING")?.message ||
            "Validation blocked due to critical issues."
          : undefined,
      });
    } catch (err: any) {
      updateQueueItem(item.id, {
        status: "failed",
        errorMessage: err.message || "Interruption during chunked upload.",
        chunkProgress: item.chunkProgress
          ? { ...item.chunkProgress, isPaused: true }
          : undefined,
      });
    }
  };

  // ---------------------------------------------------------------------------
  // Multi-File Selection & Drag/Drop Handling
  // ---------------------------------------------------------------------------
  const handleIncomingFiles = (incomingFiles: FileList | File[]) => {
    setGeneralError(null);
    const validFiles: File[] = [];
    let invalidCount = 0;

    Array.from(incomingFiles).forEach((file) => {
      const lower = file.name.toLowerCase();
      if (lower.endsWith(".csv") || lower.endsWith(".txt")) {
        validFiles.push(file);
      } else {
        invalidCount++;
      }
    });

    if (invalidCount > 0) {
      setGeneralError(
        `${invalidCount} unsupported file(s) ignored. Only .csv and .txt datasets are supported.`
      );
    }

    if (validFiles.length === 0) return;

    const newItems: BatchQueueItem[] = validFiles.map((file) => ({
      id: `${file.name}_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      file,
      name: file.name,
      size: file.size,
      status: "queued",
      progressPercent: 0,
      customTableName: file.name
        .replace(/\.[^/.]+$/, "")
        .replace(/[^\w]/g, "_")
        .toLowerCase(),
    }));

    setQueue((prev) => [...prev, ...newItems]);

    // Schedule queue execution
    setTimeout(() => {
      startQueueProcessing();
    }, 50);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleIncomingFiles(e.dataTransfer.files);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleIncomingFiles(e.target.files);
    }
  };

  // ---------------------------------------------------------------------------
  // Batch & Individual Registration Actions
  // ---------------------------------------------------------------------------
  const handleRegisterSingle = async (item: BatchQueueItem) => {
    if (!item.validationResult || !item.validationResult.can_register) return;

    updateQueueItem(item.id, { status: "registering" });

    try {
      const res = await fetch(`${apiUrl}/api/datasets/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify({
          session_id: item.validationResult.session_id,
          content_hash: item.validationResult.content_hash,
          table_name: item.customTableName || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Registration failed" }));
        throw new Error(errData.detail || "Registration failed");
      }

      const registered: RegisteredDataset = await res.json();
      updateQueueItem(item.id, {
        status: "registered",
        registeredDataset: registered,
      });
      onDatasetRegistered(registered);
    } catch (err: any) {
      updateQueueItem(item.id, {
        status: "failed",
        errorMessage: err.message || "Failed to register dataset.",
      });
    }
  };

  const handleRegisterAllValidated = async () => {
    const readyItems = queue.filter(
      (item) => item.status === "validated" && item.validationResult?.can_register
    );

    if (readyItems.length === 0) return;

    setIsRegisteringAll(true);
    setGeneralError(null);

    // Prepare batch payload
    const batchPayload = readyItems.map((item) => ({
      session_id: item.validationResult!.session_id,
      content_hash: item.validationResult!.content_hash,
      table_name: item.customTableName || undefined,
    }));

    try {
      const res = await fetch(`${apiUrl}/api/datasets/register-batch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify({ items: batchPayload }),
      });

      if (!res.ok) {
        // Fallback to sequential registration if endpoint fails
        throw new Error("Batch registration endpoint failed, attempting sequential.");
      }

      const batchResult: BatchRegisterResponse = await res.json();

      // Update state for successful registrations
      batchResult.registered.forEach((reg) => {
        const matching = readyItems.find((it) => it.validationResult?.content_hash === reg.content_hash);
        if (matching) {
          updateQueueItem(matching.id, {
            status: "registered",
            registeredDataset: reg,
          });
          onDatasetRegistered(reg);
        }
      });

      // Update state for any registration errors
      batchResult.errors.forEach((err) => {
        const matching = readyItems.find((it) => it.validationResult?.content_hash === err.content_hash);
        if (matching) {
          updateQueueItem(matching.id, {
            status: "failed",
            errorMessage: err.error,
          });
        }
      });
    } catch (err: any) {
      // Graceful fallback: register one-by-one sequentially
      for (const item of readyItems) {
        await handleRegisterSingle(item);
      }
    } finally {
      setIsRegisteringAll(false);
    }
  };

  const handleRetryItem = (item: BatchQueueItem) => {
    if (item.chunkProgress?.uploadId && item.size > CHUNK_SIZE) {
      updateQueueItem(item.id, { status: "uploading", errorMessage: undefined });
      processChunkedValidation(item, item.chunkProgress.uploadId);
    } else {
      updateQueueItem(item.id, {
        status: "queued",
        errorMessage: undefined,
        progressPercent: 0,
      });
      setTimeout(() => startQueueProcessing(), 50);
    }
  };

  const handleRetryAllFailed = () => {
    setQueue((prev) =>
      prev.map((item) =>
        item.status === "failed"
          ? { ...item, status: "queued", errorMessage: undefined, progressPercent: 0 }
          : item
      )
    );
    setTimeout(() => startQueueProcessing(), 50);
  };

  const handleRemoveItem = (id: string) => {
    setQueue((prev) => prev.filter((item) => item.id !== id));
  };

  const handleClearCompleted = () => {
    setQueue((prev) => prev.filter((item) => item.status !== "registered"));
  };

  const handleClearAll = () => {
    if (isProcessingRef.current) return;
    setQueue([]);
    setGeneralError(null);
  };

  // ---------------------------------------------------------------------------
  // Summary Aggregates
  // ---------------------------------------------------------------------------
  const totalFiles = queue.length;
  const totalBytes = queue.reduce((sum, item) => sum + item.size, 0);
  const validatedCount = queue.filter(
    (i) => i.status === "validated" && i.validationResult?.can_register
  ).length;
  const registeredCount = queue.filter((i) => i.status === "registered").length;
  const blockedCount = queue.filter((i) => i.status === "blocked").length;
  const failedCount = queue.filter((i) => i.status === "failed").length;
  const inProgressCount = queue.filter(
    (i) =>
      i.status === "uploading" ||
      i.status === "validating" ||
      i.status === "registering" ||
      i.status === "queued"
  ).length;

  return (
    <div className="w-full space-y-6">
      {/* Hidden Multi-file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".csv,.txt"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Primary Dropzone (Rendered when queue is empty) */}
      {queue.length === 0 && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleFileDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-3xl p-10 text-center cursor-pointer transition-all duration-300 relative overflow-hidden group ${
            isDragging
              ? "border-blue-500 bg-blue-500/10 shadow-2xl shadow-blue-500/10 scale-[1.005]"
              : "border-slate-700/80 hover:border-blue-500/50 bg-gradient-to-b from-slate-900/80 to-slate-950/80 hover:bg-slate-900/90 shadow-xl"
          }`}
        >
          <div className="flex flex-col items-center justify-center space-y-4">
            <div className="p-4 bg-gradient-to-tr from-blue-600/20 to-sky-400/20 border border-blue-500/30 text-blue-400 rounded-2xl group-hover:scale-105 transition-transform duration-300 shadow-inner">
              <UploadCloud className="w-10 h-10" />
            </div>

            <div className="space-y-1.5 max-w-md">
              <h4 className="text-base font-semibold text-slate-100 flex items-center justify-center gap-2">
                <span>Select Multiple CSV Files or Drop Here</span>
                <span className="text-[10px] bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded-full font-mono uppercase">
                  Batch Queue
                </span>
              </h4>
              <p className="text-xs text-slate-400">
                Supports multi-file selection &bull; Resumable 5MB multipart chunks &bull; Up to 1 GB per file
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2 pt-2 text-[11px] text-slate-400">
              <span className="bg-slate-800/80 border border-slate-700/70 px-2.5 py-1 rounded-lg">
                &bull; Auto Schema Profiling
              </span>
              <span className="bg-slate-800/80 border border-slate-700/70 px-2.5 py-1 rounded-lg">
                &bull; Script Injection Guard
              </span>
              <span className="bg-slate-800/80 border border-slate-700/70 px-2.5 py-1 rounded-lg">
                &bull; Zero-Collision DuckDB
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Batch Ingestion Queue Dashboard */}
      {queue.length > 0 && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 shadow-2xl backdrop-blur space-y-6">
          {/* Header & Controls Toolbar */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
            <div className="space-y-1">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-xl">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    CSV Batch Ingestion Queue
                    <span className="text-xs font-mono bg-slate-800 text-sky-400 px-2 py-0.5 rounded-full border border-slate-700">
                      {totalFiles} file{totalFiles !== 1 ? "s" : ""} &bull; {formatBytes(totalBytes)}
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    Pre-flight validation, schema profiling, and DuckDB catalog staging
                  </p>
                </div>
              </div>

              {/* Status pills summary */}
              <div className="flex flex-wrap items-center gap-2 pt-2 text-xs">
                {inProgressCount > 0 && (
                  <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
                    <Loader2 className="w-3 h-3 animate-spin" /> {inProgressCount} in progress
                  </span>
                )}
                {validatedCount > 0 && (
                  <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                    <CheckCircle2 className="w-3 h-3" /> {validatedCount} ready to register
                  </span>
                )}
                {registeredCount > 0 && (
                  <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
                    <Database className="w-3 h-3" /> {registeredCount} registered
                  </span>
                )}
                {blockedCount > 0 && (
                  <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 font-medium">
                    <ShieldAlert className="w-3 h-3" /> {blockedCount} blocked
                  </span>
                )}
                {failedCount > 0 && (
                  <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                    <AlertTriangle className="w-3 h-3" /> {failedCount} errors
                  </span>
                )}
              </div>
            </div>

            {/* Action Buttons Toolbar */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-xs px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 transition flex items-center gap-1.5 font-medium shadow-sm"
              >
                <Plus className="w-3.5 h-3.5 text-blue-400" /> Add Files
              </button>

              {validatedCount > 0 && (
                <button
                  onClick={handleRegisterAllValidated}
                  disabled={isRegisteringAll}
                  className="text-xs px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-medium transition flex items-center gap-2 shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                >
                  {isRegisteringAll ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Database className="w-3.5 h-3.5" />
                  )}
                  Register All Validated ({validatedCount})
                </button>
              )}

              {failedCount > 0 && (
                <button
                  onClick={handleRetryAllFailed}
                  className="text-xs px-3 py-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 transition flex items-center gap-1.5 font-medium"
                >
                  <RefreshCw className="w-3.5 h-3.5" /> Retry Failed ({failedCount})
                </button>
              )}

              {registeredCount > 0 && (
                <button
                  onClick={handleClearCompleted}
                  className="text-xs px-3 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                  title="Remove successfully registered items from queue"
                >
                  Clear Completed
                </button>
              )}

              <button
                onClick={handleClearAll}
                disabled={isProcessingRef.current}
                className="text-xs px-2.5 py-2 rounded-xl text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition disabled:opacity-30"
                title="Clear all items from queue"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Drop Banner for Queuing Additional Files */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleFileDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border border-dashed rounded-2xl py-3 px-4 text-center cursor-pointer transition duration-200 flex items-center justify-center gap-2 text-xs ${
              isDragging
                ? "border-blue-500 bg-blue-500/10 text-blue-300"
                : "border-slate-800 hover:border-slate-700 bg-slate-950/40 text-slate-400 hover:text-slate-300"
            }`}
          >
            <UploadCloud className="w-4 h-4 text-blue-400" />
            <span>Drop additional CSV files here, or click to browse</span>
          </div>

          {/* General Error Banner */}
          {generalError && (
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/70 text-amber-300 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{generalError}</span>
              </div>
              <button
                onClick={() => setGeneralError(null)}
                className="text-amber-400 hover:text-amber-200"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Queue Items List */}
          <div className="space-y-3">
            {queue.map((item) => (
              <QueueItemCard
                key={item.id}
                item={item}
                onInspect={() => setInspectingItem(item)}
                onRegisterSingle={() => handleRegisterSingle(item)}
                onRetry={() => handleRetryItem(item)}
                onRemove={() => handleRemoveItem(item.id)}
                formatBytes={formatBytes}
              />
            ))}
          </div>
        </div>
      )}

      {/* Validation Inspection Modal */}
      {inspectingItem && inspectingItem.validationResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto">
          <div className="w-full max-w-4xl relative my-auto">
            <DatasetValidationPreview
              validation={inspectingItem.validationResult}
              apiUrl={apiUrl}
              tenantId={tenantId}
              onAccept={(dataset) => {
                updateQueueItem(inspectingItem.id, {
                  status: "registered",
                  registeredDataset: dataset,
                });
                onDatasetRegistered(dataset);
                setInspectingItem(null);
              }}
              onRetry={() => {
                const target = inspectingItem;
                setInspectingItem(null);
                handleRetryItem(target);
              }}
              onCancel={() => setInspectingItem(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Queue Item Card Component
// ---------------------------------------------------------------------------
function QueueItemCard({
  item,
  onInspect,
  onRegisterSingle,
  onRetry,
  onRemove,
  formatBytes,
}: {
  item: BatchQueueItem;
  onInspect: () => void;
  onRegisterSingle: () => void;
  onRetry: () => void;
  onRemove: () => void;
  formatBytes: (b: number) => string;
}) {
  const isChunked = item.size > CHUNK_SIZE;

  // Render status badge
  const renderBadge = () => {
    switch (item.status) {
      case "queued":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
            <Clock className="w-3 h-3" /> Queued
          </span>
        );
      case "uploading":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-blue-500/20 text-sky-400 border border-blue-500/30">
            <Loader2 className="w-3 h-3 animate-spin" /> Uploading {item.progressPercent}%
          </span>
        );
      case "validating":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <Loader2 className="w-3 h-3 animate-spin" /> Profiling Schema...
          </span>
        );
      case "validated":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3" /> Validated
          </span>
        );
      case "blocked":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30">
            <ShieldAlert className="w-3 h-3" /> Blocked
          </span>
        );
      case "registering":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
            <Loader2 className="w-3 h-3 animate-spin" /> Registering DuckDB...
          </span>
        );
      case "registered":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            <Database className="w-3 h-3" /> Registered
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30">
            <AlertCircle className="w-3 h-3" /> Failed
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 rounded-2xl p-4 transition-all duration-200 space-y-3">
      {/* Top row: Filename, size, status, actions */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center space-x-3 min-w-0">
          <div
            className={`p-2 rounded-xl flex-shrink-0 ${
              item.status === "registered"
                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                : item.status === "blocked" || item.status === "failed"
                ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                : item.status === "validated"
                ? "bg-teal-500/10 text-teal-400 border border-teal-500/20"
                : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
            }`}
          >
            <FileSpreadsheet className="w-5 h-5" />
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-sm font-semibold text-slate-100 truncate" title={item.name}>
                {item.name}
              </h4>
              <span className="text-[10px] font-mono bg-slate-900 text-slate-400 px-1.5 py-0.5 rounded border border-slate-800">
                {formatBytes(item.size)}
              </span>
              {isChunked && (
                <span className="text-[10px] bg-sky-950 text-sky-400 border border-sky-800 px-1.5 py-0.5 rounded">
                  Multipart 5MB
                </span>
              )}
            </div>

            {/* Subtitle / Details */}
            <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2 flex-wrap">
              {item.validationResult && (
                <>
                  <span>
                    {item.validationResult.row_count.toLocaleString()} rows &bull;{" "}
                    {item.validationResult.column_count} columns
                  </span>
                  {item.validationResult.issues.length > 0 && (
                    <span
                      className={`text-[11px] ${
                        item.validationResult.can_register ? "text-amber-400" : "text-rose-400 font-medium"
                      }`}
                    >
                      &bull; {item.validationResult.issues.length} issue(s)
                    </span>
                  )}
                </>
              )}

              {item.registeredDataset && (
                <span className="text-emerald-400 font-mono text-[11px] flex items-center gap-1">
                  Table: <code>{item.registeredDataset.table_name}</code>
                </span>
              )}

              {item.errorMessage && (
                <span className="text-rose-400 text-[11px] truncate max-w-sm" title={item.errorMessage}>
                  {item.errorMessage}
                </span>
              )}

              {item.chunkProgress && item.status === "uploading" && (
                <span className="text-slate-400 text-[11px]">
                  Chunk {item.chunkProgress.current} of {item.chunkProgress.total}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right side: Badge & Action buttons */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          {renderBadge()}

          {/* Inspect / Preview button */}
          {item.validationResult && (
            <button
              onClick={onInspect}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
              title="Inspect Schema & Issues"
            >
              <Eye className="w-4 h-4 text-sky-400" />
            </button>
          )}

          {/* Register single button */}
          {item.status === "validated" && item.validationResult?.can_register && (
            <button
              onClick={onRegisterSingle}
              className="text-xs px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition flex items-center gap-1 shadow-sm"
              title="Register into DuckDB"
            >
              <Database className="w-3.5 h-3.5" /> Register
            </button>
          )}

          {/* Retry button */}
          {(item.status === "failed" || item.chunkProgress?.isPaused) && (
            <button
              onClick={onRetry}
              className="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 transition"
              title="Retry Validation"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          )}

          {/* Remove button */}
          {item.status !== "uploading" && item.status !== "validating" && item.status !== "registering" && (
            <button
              onClick={onRemove}
              className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition"
              title="Remove from queue"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar (Visible during uploading or validating) */}
      {(item.status === "uploading" ||
        item.status === "validating" ||
        item.status === "registering") && (
        <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              item.status === "registering"
                ? "bg-gradient-to-r from-indigo-500 to-purple-400 animate-pulse"
                : "bg-gradient-to-r from-blue-600 to-sky-400"
            }`}
            style={{ width: `${Math.max(item.progressPercent, 5)}%` }}
          />
        </div>
      )}
    </div>
  );
}
