export interface WorkspaceDocument {
  id: string;
  original_filename: string;
  file_size_bytes: number;
  uploaded_at: string;
}

export interface DocumentSearchResult {
  id: string;
  original_filename: string;
  uploaded_at: string;
  match_type: "filename" | "content" | "both";
  excerpt: string | null;
}

export interface BatchUploadResult {
  results: Array<{ filename: string; success: boolean; message: string }>;
}
