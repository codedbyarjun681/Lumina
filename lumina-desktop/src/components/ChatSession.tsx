import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useState,
  type DragEvent,
} from "react";
import type { Message } from "../types/Message";
import { api } from "../services/api";
import { useConversationStore } from "../store/conversationStore";
import ChatArea from "./ChatArea";
import InputBar from "./InputBar";
import ModelPicker from "./ModelPicker";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".pptx"];

export interface ChatSessionHandle {
  handleFileSelected: (files: File | File[]) => void;
}

interface ChatSessionProps {
  workspaceId: string | null;
  conversationId: string | null;
  providerId: string | null;
  model: string;
}

const ChatSession = forwardRef<ChatSessionHandle, ChatSessionProps>(
  ({ workspaceId, conversationId, providerId, model }, ref) => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [agentSteps, setAgentSteps] = useState<string[]>([]);

    // Load persisted history on mount (component remounts per conversation
    // because App renders it with key={conversationId})
    useEffect(() => {
      if (conversationId === null) {
        return;
      }
      let cancelled = false;
      void (async () => {
        try {
          const history = await api.fetchMessages(conversationId);
          if (cancelled) {
            return;
          }
          setMessages(
            history.map((m) => ({
              id: m.id,
              role: m.role,
              content: m.content,
            })),
          );
        } catch {
          // History failed to load — start with an empty chat instead
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [conversationId]);

    const pushMessage = (message: Message) => {
      setMessages((prev) => [...prev, message]);
    };

    const requireWorkspace = (): string | null => {
      if (workspaceId === null) {
        pushMessage({
          role: "assistant",
          content:
            "Select or create a workspace first — I'll keep your message here.",
        });
        return null;
      }
      return workspaceId;
    };

    const requireConversation = (): string | null => {
      if (conversationId === null) {
        pushMessage({
          role: "assistant",
          content: "Start a new conversation first, then ask away.",
        });
        return null;
      }
      return conversationId;
    };

    // Shared ask flow: the caller has already pushed the user message to the
    // UI (optimistic). Streams agent progress; backend persists both messages.
    const sendQuestion = async (question: string) => {
      const activeWorkspace = requireWorkspace();
      const activeConversation = requireConversation();
      if (activeWorkspace === null || activeConversation === null) {
        return;
      }

      setLoading(true);
      setAgentSteps([]);
      try {
        await api.askStream(question, activeWorkspace, activeConversation, {
          onStep: (label) => setAgentSteps((prev) => [...prev, label]),
          onAgent: () => undefined,
          onFinal: (result) => {
            setAgentSteps([]);
            if (result.user_message_id) {
              setMessages((prev) => {
                const next = [...prev];
                for (let i = next.length - 1; i >= 0; i--) {
                  if (next[i].role === "user" && next[i].id === undefined) {
                    next[i] = { ...next[i], id: result.user_message_id };
                    break;
                  }
                }
                return next;
              });
            }
            pushMessage({
              id: result.assistant_message_id,
              role: "assistant",
              content: result.response,
              agent: result.agent_label,
              sources:
                result.sources && result.sources.length > 0
                  ? result.sources
                  : undefined,
            });
            if (result.conversation_name) {
              useConversationStore
                .getState()
                .applyConversationName(
                  activeConversation,
                  result.conversation_name,
                );
            }
          },
          onError: (status, detail) => {
            setAgentSteps([]);
            pushMessage({
              role: "assistant",
              content:
                status === 503 || status === 409 || status === 429
                  ? `The model is busy or unreachable — ${detail}`
                  : `Something went wrong: ${detail}`,
            });
          },
        });
      } catch (error) {
        setAgentSteps([]);
        pushMessage({
          role: "assistant",
          content:
            error instanceof Error
              ? `Something went wrong: ${error.message}`
              : "Something went wrong while answering.",
        });
      } finally {
        setLoading(false);
      }
    };

    const handleSend = async () => {
      const question = input.trim();
      if (question.length === 0 || loading) {
        return;
      }
      setInput("");
      pushMessage({ role: "user", content: question });
      await sendQuestion(question);
    };

    // ChatGPT-style prompt editing: truncate the conversation from the edited
    // message (server + UI), then re-ask with the new content.
    const handleEditMessage = (messageId: string, newContent: string) => {
      if (conversationId === null || loading) {
        return;
      }
      const activeConversation = conversationId;
      setMessages((prev) => {
        const index = prev.findIndex((m) => m.id === messageId);
        return index === -1 ? prev : prev.slice(0, index);
      });
      pushMessage({ role: "user", content: newContent });
      setLoading(true);
      void (async () => {
        try {
          await api.deleteMessagesFrom(activeConversation, messageId);
        } catch {
          // If truncation fails, stop — the UI may drift from the server,
          // but never re-ask on top of an un-truncated conversation.
          setLoading(false);
          pushMessage({
            role: "assistant",
            content:
              "Could not update the conversation on the server — please reload.",
          });
          return;
        }
        setLoading(false);
        await sendQuestion(newContent);
      })();
    };

    const uploadOne = async (activeId: string, file: File) => {
      await api.uploadFile(activeId, file);
      pushMessage({
        role: "assistant",
        content: `"${file.name}" was added to this workspace's knowledge. Ask me anything about it.`,
      });
    };

    const uploadMany = async (activeId: string, files: File[]) => {
      const result = await api.uploadBatch(activeId, files);
      const succeeded = result.results.filter((r) => r.success).length;
      const summary = result.results
        .map((r) =>
          r.success
            ? `${r.filename} ✓`
            : `${r.filename} ✗ (${r.message.toLowerCase()})`,
        )
        .join(", ");
      pushMessage({
        role: "assistant",
        content: `${succeeded} of ${result.results.length} files uploaded: ${summary}`,
      });
    };

    const handleFileSelected = (files: File | File[]) => {
      const list = Array.isArray(files) ? files : [files];
      if (list.length === 0) {
        return;
      }
      const activeId = requireWorkspace();
      if (activeId === null) {
        return;
      }
      setLoading(true);
      void (async () => {
        try {
          if (list.length === 1) {
            await uploadOne(activeId, list[0]);
          } else {
            await uploadMany(activeId, list);
          }
        } catch (error) {
          pushMessage({
            role: "assistant",
            content:
              error instanceof Error
                ? `Upload failed: ${error.message}`
                : "Upload failed.",
          });
        } finally {
          setLoading(false);
        }
      })();
    };

    useImperativeHandle(ref, () => ({ handleFileSelected }));

    // ——— Drag & drop ———

    const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      if (workspaceId !== null) {
        setIsDragging(true);
      }
    };

    const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
      if (e.currentTarget.contains(e.relatedTarget as Node | null)) {
        return;
      }
      setIsDragging(false);
    };

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      if (workspaceId === null) {
        return;
      }
      const files = Array.from(e.dataTransfer.files).filter((f) =>
        ALLOWED_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext)),
      );
      if (files.length > 0) {
        handleFileSelected(files);
      }
    };

    const handleSelectModel = (newProvider: string, newModel: string) => {
      if (conversationId !== null) {
        void useConversationStore
          .getState()
          .updateConversationModel(conversationId, newProvider, newModel);
      }
    };

    return (
      <div
        className="chat-session-dropzone"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <section className="chat-session">
          <ChatArea
            messages={messages}
            loading={loading}
            agentSteps={agentSteps}
            onEditMessage={handleEditMessage}
          />
          <div className="chat-compose">
            <ModelPicker
              providerId={providerId}
              currentModel={model}
              onSelect={handleSelectModel}
            />
            <InputBar
              input={input}
              setInput={setInput}
              handleSend={handleSend}
            />
          </div>
        </section>
        {isDragging && (
          <div className="drag-overlay">
            <span>Drop files to upload</span>
          </div>
        )}
      </div>
    );
  },
);

ChatSession.displayName = "ChatSession";

export default ChatSession;
