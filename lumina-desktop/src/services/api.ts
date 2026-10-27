import type { Workspace } from "../types/Workspace";
import type { Conversation, ConversationMessage } from "../types/Conversation";
import type { MemoryEntry } from "../types/Memory";
import type {
  QuizQuestion,
  QuizResult,
  QuizSummary,
  QuizDetail,
} from "../types/Quiz";
import type {
  BatchUploadResult,
  DocumentSearchResult,
  WorkspaceDocument,
} from "../types/Document";

export interface AskResult {
  response: string;
  conversation_name?: string;
  sources?: Array<{ original_filename: string; excerpt: string }>;
  user_message_id?: string;
  assistant_message_id?: string;
}

const BASE_URL = "http://localhost:8000";

export interface ProviderModel {
  id: string;
  name: string;
}

export interface ProviderInfo {
  id: string;
  name: string;
  kind: string;
  base_url: string | null;
  needs_api_key: boolean;
  is_builtin: boolean;
}

export interface AppSettings {
  api_keys_set: Record<string, boolean>;
  theme: string | null;
  colorway: string | null;
  default_provider: string | null;
  default_model: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const body: unknown = await res.json();
      if (
        typeof body === "object" &&
        body !== null &&
        "detail" in body &&
        typeof (body as { detail: unknown }).detail === "string"
      ) {
        detail = (body as { detail: string }).detail;
      } else if (
        typeof body === "object" &&
        body !== null &&
        "error" in body &&
        typeof (body as { error: unknown }).error === "string"
      ) {
        detail = (body as { error: string }).error;
      }
    } catch {
      // response had no JSON body; keep the default message
    }
    throw new Error(detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export const api = {
  listWorkspaces(): Promise<Workspace[]> {
    return request<Workspace[]>("/workspaces");
  },

  createWorkspace(name: string): Promise<Workspace> {
    return request<Workspace>("/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  },

  renameWorkspace(id: string, name: string): Promise<Workspace> {
    return request<Workspace>(`/workspaces/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  },

  updateWorkspaceLLM(
    id: string,
    llmProvider: string,
    llmModel: string,
  ): Promise<Workspace> {
    return request<Workspace>(`/workspaces/${id}/llm-settings`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ llm_provider: llmProvider, llm_model: llmModel }),
    });
  },

  deleteWorkspace(id: string): Promise<void> {
    return request<void>(`/workspaces/${id}`, { method: "DELETE" });
  },

  async exportWorkspace(id: string, name: string): Promise<void> {
    const res = await fetch(`${BASE_URL}/workspaces/${id}/export`);
    if (!res.ok) {
      throw new Error(`Export failed with status ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `lumina-${name || "workspace"}.zip`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },

  reorderWorkspaces(ids: string[]): Promise<void> {
    return request<void>("/workspaces/reorder", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
  },

  importWorkspace(file: File): Promise<Workspace> {
    const form = new FormData();
    form.append("file", file);
    return request<Workspace>("/workspaces/import", {
      method: "POST",
      body: form,
    });
  },

  async uploadFile(workspaceId: string, file: File): Promise<void> {
    const form = new FormData();
    form.append("workspace_id", workspaceId);
    form.append("file", file);
    await request<{ message: string }>("/upload", {
      method: "POST",
      body: form,
    });
  },

  async ask(
    question: string,
    workspaceId: string,
    conversationId: string,
  ): Promise<AskResult> {
    return request<AskResult>("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        workspace_id: workspaceId,
        conversation_id: conversationId,
      }),
    });
  },

  // ——— Agentic streaming ask ———

  async askStream(
    question: string,
    workspaceId: string,
    conversationId: string,
    handlers: {
      onStep?: (label: string) => void;
      onAgent?: (agent: string, agentLabel: string) => void;
      onToken?: (text: string) => void;
      onRestart?: () => void;
      onFinal?: (
        result: AskResult & {
          agent?: string;
          agent_label?: string;
          quiz?: { quiz_id: string; questions: QuizQuestion[] };
        },
      ) => void;
      onError?: (status: number, detail: string) => void;
    },
  ): Promise<void> {
    const res = await fetch(
      `${BASE_URL}/workspaces/${workspaceId}/agent/ask`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          conversation_id: conversationId,
        }),
      },
    );

    if (!res.ok || !res.body) {
      let detail = `Request failed with status ${res.status}`;
      try {
        const body: unknown = await res.json();
        if (
          typeof body === "object" &&
          body !== null &&
          "detail" in body &&
          typeof (body as { detail: unknown }).detail === "string"
        ) {
          detail = (body as { detail: string }).detail;
        }
      } catch {
        // non-JSON error body
      }
      handlers.onError?.(res.status, detail);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      let separator = buffer.indexOf("\n\n");
      while (separator !== -1) {
        const chunk = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);
        separator = buffer.indexOf("\n\n");
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data:")) {
            continue;
          }
          const event: {
            event: string;
            label?: string;
            token?: string;
            agent?: string;
            agent_label?: string;
            status?: number;
            detail?: string;
            response?: string;
  sources?: Array<{
    original_filename: string;
    excerpt: string;
    page?: number | null;
  }>;
            conversation_name?: string;
            user_message_id?: string;
            assistant_message_id?: string;
            quiz?: { quiz_id: string; questions: QuizQuestion[] };
          } = JSON.parse(line.slice(5).trim());

          if (event.event === "step" && event.label) {
            handlers.onStep?.(event.label);
          } else if (event.event === "token" && typeof event.token === "string") {
            handlers.onToken?.(event.token);
          } else if (event.event === "restart") {
            handlers.onRestart?.();
          } else if (event.event === "agent") {
            handlers.onAgent?.(event.agent ?? "", event.agent_label ?? "");
          } else if (event.event === "final") {
            handlers.onFinal?.({
              response: event.response ?? "",
              sources: event.sources,
              conversation_name: event.conversation_name,
              user_message_id: event.user_message_id,
              assistant_message_id: event.assistant_message_id,
              agent: event.agent,
              agent_label: event.agent_label,
              quiz: event.quiz,
            });
          } else if (event.event === "error") {
            handlers.onError?.(event.status ?? 500, event.detail ?? "Unknown error");
          }
        }
      }
    }
  },

  async uploadBatch(
    workspaceId: string,
    files: File[],
  ): Promise<BatchUploadResult> {
    const form = new FormData();
    form.append("workspace_id", workspaceId);
    for (const file of files) {
      form.append("files", file);
    }
    return request<BatchUploadResult>("/upload/batch", {
      method: "POST",
      body: form,
    });
  },

  fetchDocuments(workspaceId: string): Promise<WorkspaceDocument[]> {
    return request<WorkspaceDocument[]>(`/workspaces/${workspaceId}/documents`);
  },

  documentFileUrl(workspaceId: string, documentId: string): string {
    return `${BASE_URL}/workspaces/${workspaceId}/documents/${documentId}/file`;
  },

  deleteDocument(workspaceId: string, documentId: string): Promise<void> {
    return request<void>(
      `/workspaces/${workspaceId}/documents/${documentId}`,
      { method: "DELETE" },
    );
  },

  searchDocuments(
    workspaceId: string,
    query: string,
  ): Promise<DocumentSearchResult[]> {
    return request<DocumentSearchResult[]>(
      `/workspaces/${workspaceId}/documents/search?q=${encodeURIComponent(query)}`,
    );
  },

  // ——— Conversations ———

  fetchConversations(workspaceId: string): Promise<Conversation[]> {
    return request<Conversation[]>(`/workspaces/${workspaceId}/conversations`);
  },

  createConversation(
    workspaceId: string,
    name?: string,
  ): Promise<Conversation> {
    return request<Conversation>(`/workspaces/${workspaceId}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name ?? "New Conversation" }),
    });
  },

  renameConversation(id: string, name: string): Promise<Conversation> {
    return request<Conversation>(`/conversations/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  },

  deleteConversation(id: string): Promise<void> {
    return request<void>(`/conversations/${id}`, { method: "DELETE" });
  },

  fetchMessages(conversationId: string): Promise<ConversationMessage[]> {
    return request<ConversationMessage[]>(
      `/conversations/${conversationId}/messages`,
    );
  },

  appendMessage(
    conversationId: string,
    role: string,
    content: string,
  ): Promise<ConversationMessage> {
    return request<ConversationMessage>(
      `/conversations/${conversationId}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, content }),
      },
    );
  },

  // ——— Memory ———

  fetchMemory(workspaceId: string): Promise<MemoryEntry[]> {
    return request<MemoryEntry[]>(`/workspaces/${workspaceId}/memory`);
  },

  createMemoryEntry(
    workspaceId: string,
    content: string,
    conversationId?: string,
  ): Promise<MemoryEntry> {
    return request<MemoryEntry>(`/workspaces/${workspaceId}/memory`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      }),
    });
  },

  editMemoryEntry(id: string, content: string): Promise<MemoryEntry> {
    return request<MemoryEntry>(`/memory/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
  },

  deleteMemoryEntry(id: string): Promise<void> {
    return request<void>(`/memory/${id}`, { method: "DELETE" });
  },

  getSettings(): Promise<AppSettings> {
    return request<AppSettings>("/settings");
  },

  setApiKey(provider: string, apiKey: string): Promise<void> {
    return request<void>("/settings/api-key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
  },

  async getProviders(): Promise<ProviderInfo[]> {
    return request<ProviderInfo[]>("/providers");
  },

  async getModels(provider: string): Promise<ProviderModel[]> {
    const data = await request<{ models: ProviderModel[] }>(
      `/models/${provider}`,
    );
    return data.models;
  },

  addProvider(
    name: string,
    baseUrl: string,
    needsApiKey: boolean,
  ): Promise<ProviderInfo> {
    return request<ProviderInfo>("/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        base_url: baseUrl,
        needs_api_key: needsApiKey,
      }),
    });
  },

  deleteProvider(id: string): Promise<void> {
    return request<void>(`/providers/${id}`, { method: "DELETE" });
  },

  updateConversationLLM(
    conversationId: string,
    llmModel: string,
    llmProvider?: string,
  ): Promise<Conversation> {
    return request<Conversation>(`/conversations/${conversationId}/llm`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        llm_model: llmModel,
        ...(llmProvider ? { llm_provider: llmProvider } : {}),
      }),
    });
  },

  updatePreferences(prefs: {
    theme?: string;
    colorway?: string;
    default_provider?: string;
    default_model?: string;
  }): Promise<void> {
    return request<void>("/settings/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    });
  },

  async exportConversation(
    conversationId: string,
    name: string,
    format: "md" | "pdf",
  ): Promise<void> {
    const res = await fetch(
      `${BASE_URL}/conversations/${conversationId}/export?format=${format}`,
    );
    if (!res.ok) {
      let detail = `Export failed with status ${res.status}`;
      try {
        const body: unknown = await res.json();
        if (
          typeof body === "object" &&
          body !== null &&
          "detail" in body &&
          typeof (body as { detail: unknown }).detail === "string"
        ) {
          detail = (body as { detail: string }).detail;
        }
      } catch {
        // non-JSON body
      }
      throw new Error(detail);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    const safe =
      (name || "conversation").replace(/[^\w\- ]+/g, "_").slice(0, 60) ||
      "conversation";
    anchor.download = `${safe}.${format}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },

  deleteMessagesFrom(conversationId: string, messageId: string): Promise<{ deleted: number }> {
    return request<{ deleted: number }>(
      `/conversations/${conversationId}/messages/${messageId}`,
      { method: "DELETE" },
    );
  },

  generateQuiz(
    workspaceId: string,
    numQuestions: number,
    difficulty: string,
  ): Promise<QuizResult> {
    return request<QuizResult>(`/workspaces/${workspaceId}/quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        num_questions: numQuestions,
        difficulty,
      }),
    });
  },

  fetchQuizzes(workspaceId: string): Promise<QuizSummary[]> {
    return request<QuizSummary[]>(`/workspaces/${workspaceId}/quizzes`);
  },

  getQuiz(quizId: string): Promise<QuizDetail> {
    return request<QuizDetail>(`/quizzes/${quizId}`);
  },

  deleteQuiz(quizId: string): Promise<void> {
    return request<void>(`/quizzes/${quizId}`, { method: "DELETE" });
  },

  recordQuizAttempt(
    quizId: string,
    score: number,
    total: number,
  ): Promise<QuizDetail> {
    return request<QuizDetail>(`/quizzes/${quizId}/attempts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ score, total }),
    });
  },
};
