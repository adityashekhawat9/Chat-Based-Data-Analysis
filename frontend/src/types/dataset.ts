export type Severity = "BLOCKING" | "WARNING";

export interface ValidationIssue {
  code: string;
  severity: Severity;
  message: string;
  column?: string | null;
  affected_count?: number | null;
  recommended_action: string;
}

export interface ColumnProfile {
  name: string;
  raw_name: string;
  inferred_type: string;
  null_count: number;
  null_percentage: number;
  unique_count: number;
  is_unique: boolean;
  sample_values: string[];
}

export interface ValidationResponse {
  status: "passed" | "warnings" | "failed";
  session_id: string;
  filename: string;
  file_size_bytes: number;
  content_hash: string;
  is_duplicate: boolean;
  existing_dataset_id?: string | null;
  row_count: number;
  column_count: number;
  can_register: boolean;
  issues: ValidationIssue[];
  column_profiles: ColumnProfile[];
}

export interface RegisteredDataset {
  dataset_id: string;
  session_id: string;
  table_name: string;
  filename: string;
  content_hash: string;
  row_count: number;
  column_count: number;
  registered_at: string;
  columns: string[];
}

export interface SessionDatasetsResponse {
  session_id: string;
  datasets: RegisteredDataset[];
}

export interface BatchRegisterItem {
  session_id: string;
  content_hash: string;
  table_name?: string;
}

export interface BatchRegisterRequest {
  items: BatchRegisterItem[];
}

export interface BatchRegisterResponse {
  registered: RegisteredDataset[];
  errors: Array<{ content_hash?: string; table_name?: string; error: string }>;
}

export type BatchItemStatus =
  | "queued"
  | "uploading"
  | "validating"
  | "validated"
  | "blocked"
  | "registering"
  | "registered"
  | "failed";

export interface BatchQueueItem {
  id: string;
  file: File;
  name: string;
  size: number;
  status: BatchItemStatus;
  progressPercent: number;
  chunkProgress?: {
    current: number;
    total: number;
    uploadedChunks: number[];
    uploadId?: string;
    isPaused?: boolean;
  };
  validationResult?: ValidationResponse;
  registeredDataset?: RegisteredDataset;
  errorMessage?: string;
  customTableName?: string;
}

