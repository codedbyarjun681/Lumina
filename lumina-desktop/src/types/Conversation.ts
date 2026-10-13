export interface Conversation {
  id: string;
  workspace_id: string;
  name: string;
  llm_model: string | null;
  llm_provider: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}
