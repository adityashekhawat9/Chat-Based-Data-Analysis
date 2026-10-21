"use client";

import React, { useState, useRef } from "react";
import {
  UploadCloud,
  FileSpreadsheet,
  AlertCircle,
  Loader2,
  CheckCircle2,
  RefreshCw,
  HardDrive,
  Layers,
  ArrowRight,
} from "lucide-react";
import { ValidationResponse, RegisteredDataset } from "@/types/dataset";
import DatasetValidationPreview from "./DatasetValidationPreview";

interface Props {
  sessionId: string;
  onDatasetRegistered: (dataset: RegisteredDataset) => void;
  apiUrl?: string;
  tenantId?: string;
}

const CHUNK_SIZE = 5 * 1024 * 1024; // 5 MB per slice

interface ChunkUploadState {
  uploadId: string;
  fileName: string;
  fileSize: number;
  totalChunks: number;
  uploadedChunks: number[];
  currentChunk: number;
  progressPercent: number;
  isPaused: boolean;
}

export default function CsvUploader({
  sessionId,
  onDatasetRegistered,
  apiUrl = "http://localhost:8000",
  tenantId = "default_tenant",
}: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationResult, setValidationResult] =
    useState<ValidationResponse | null>(null);

  // Chunked upload state
  const [chunkState, setChunkState] = useState<ChunkUploadState | null>(null);
  const activeFileRef = useRef<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFile(e.target.files[0]);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const processFile = async (file: File) => {
    setErrorMessage(null);
    setValidationResult(null);
    setChunkState(null);
    activeFileRef.current = file;

    // If file is 5MB or smaller, perform standard single-pass validation
    if (file.size <= CHUNK_SIZE) {
      await processDirectUpload(file);
    } else {
      // Large file: initiate resumable multipart chunked upload
      await processChunkedUpload(file);
    }
  };

  const processDirectUpload = async (file: File) => {
    setIsValidating(true);
    const formData = new FormData();
    formData.append("file", file);
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
      setValidationResult(data);
    } catch (err: any) {
      setErrorMessage(
        err.message || "Failed to connect to backend validation service."
      );
    } finally {
      setIsValidating(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const processChunkedUpload = async (file: File, resumeUploadId?: string) => {
    setIsValidating(true);
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

      setChunkState({
        uploadId: uploadId!,
        fileName: file.name,
        fileSize: file.size,
        totalChunks,
        uploadedChunks: alreadyUploaded,
        currentChunk: alreadyUploaded.length,
        progressPercent: Math.round((alreadyUploaded.length / totalChunks) * 100),
        isPaused: false,
      });

      // Step 2: Upload missing chunks sequentially
      for (let i = 0; i < totalChunks; i++) {
        if (alreadyUploaded.includes(i)) {
          continue;
        }

        setChunkState((prev) =>
          prev
            ? {
                ...prev,
                currentChunk: i + 1,
                progressPercent: Math.round(((i) / totalChunks) * 100),
              }
            : null
        );

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
            `Failed uploading chunk ${i + 1} of ${totalChunks}: ${errData.detail || chunkRes.statusText}`
          );
        }

        alreadyUploaded.push(i);
        setChunkState((prev) =>
          prev
            ? {
                ...prev,
                uploadedChunks: [...alreadyUploaded],
                progressPercent: Math.round((alreadyUploaded.length / totalChunks) * 100),
              }
            : null
        );
      }

      // Step 3: Complete & Assemble on server
      const completeRes = await fetch(`${apiUrl}/api/datasets/upload/complete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify({ upload_id: uploadId }),
      });

      const validationData: ValidationResponse = await completeRes.json();
      setValidationResult(validationData);
      setChunkState(null);
    } catch (err: any) {
      setErrorMessage(err.message || "Interruption occurred during chunked upload.");
      setChunkState((prev) => (prev ? { ...prev, isPaused: true } : null));
    } finally {
      setIsValidating(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleResume = () => {
    if (activeFileRef.current && chunkState?.uploadId) {
      setErrorMessage(null);
      processChunkedUpload(activeFileRef.current, chunkState.uploadId);
    }
  };

  return (
    <div className="w-full">
      {!validationResult && !chunkState && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleFileDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 ${
            isDragging
              ? "border-blue-500 bg-blue-500/10"
              : "border-slate-700 hover:border-slate-500 bg-slate-900/60 hover:bg-slate-900"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.txt"
            onChange={handleFileSelect}
            className="hidden"
          />

          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="p-3.5 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-full">
              {isValidating ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                <UploadCloud className="w-8 h-8" />
              )}
            </div>

            <div className="space-y-1">
              <p className="text-base font-medium text-slate-200">
                {isValidating
                  ? "Validating schema, encoding, and data hygiene..."
                  : "Drag and drop CSV files here, or click to browse"}
              </p>
              <p className="text-xs text-slate-400">
                Supports UTF-8, Latin-1 &bull; Resumable 5MB multipart chunks &bull; Up to 1 GB
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Chunked Upload Progress Banner */}
      {chunkState && !validationResult && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2.5 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded-xl">
                <HardDrive className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white flex items-center gap-2">
                  <span>{chunkState.fileName}</span>
                  <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
                    {formatBytes(chunkState.fileSize)}
                  </span>
                </h4>
                <p className="text-xs text-slate-400">
                  Resumable Multipart Upload &bull; Chunk {chunkState.uploadedChunks.length} of {chunkState.totalChunks}
                </p>
              </div>
            </div>

            <span className="text-lg font-bold font-mono text-sky-400">
              {chunkState.progressPercent}%
            </span>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
            <div
              className="bg-gradient-to-r from-blue-600 to-sky-400 h-full rounded-full transition-all duration-300 shadow-sm shadow-sky-400/50"
              style={{ width: `${chunkState.progressPercent}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>
              {isValidating
                ? "Streaming chunk parts to server cache..."
                : chunkState.isPaused
                ? "Upload paused due to network interruption."
                : "Assembling slices & verifying SHA-256..."}
            </span>
            <span>
              {formatBytes((chunkState.uploadedChunks.length * CHUNK_SIZE))} / {formatBytes(chunkState.fileSize)}
            </span>
          </div>

          {chunkState.isPaused && (
            <div className="pt-2 flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setChunkState(null);
                  setErrorMessage(null);
                }}
                className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                Cancel Upload
              </button>
              <button
                onClick={handleResume}
                className="text-xs px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition flex items-center gap-1.5 shadow-md shadow-blue-600/30"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Resume From Chunk {chunkState.uploadedChunks.length + 1}
              </button>
            </div>
          )}
        </div>
      )}

      {errorMessage && (
        <div className="mt-4 p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm">{errorMessage}</p>
          </div>
          {chunkState?.isPaused && (
            <button
              onClick={handleResume}
              className="text-xs px-3 py-1.5 bg-rose-900 hover:bg-rose-800 text-rose-200 rounded-lg transition font-medium whitespace-nowrap"
            >
              Retry
            </button>
          )}
        </div>
      )}

      {validationResult && (
        <DatasetValidationPreview
          validation={validationResult}
          apiUrl={apiUrl}
          tenantId={tenantId}
          onAccept={(dataset) => {
            setValidationResult(null);
            onDatasetRegistered(dataset);
          }}
          onRetry={() => {
            setValidationResult(null);
            fileInputRef.current?.click();
          }}
          onCancel={() => setValidationResult(null)}
        />
      )}
    </div>
  );
}
