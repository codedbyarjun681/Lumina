export interface MemoryEntry {
  id: string;
  workspace_id: string;
  content: string;
  source: "auto" | "manual";
  created_at: string;
  updated_at: string;
}
