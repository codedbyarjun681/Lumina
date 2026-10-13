import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { Message, MessageSource } from "../types/Message";

function SourcesSection({ sources }: { sources: MessageSource[] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="sources-section">
      <button
        type="button"
        className="sources-toggle"
        onClick={() => setExpanded((e) => !e)}
      >
        📄 {sources.length} {sources.length === 1 ? "source" : "sources"}
      </button>
      {expanded && (
        <div className="sources-list">
          {sources.map((s, i) => (
            <div key={i} className="source-card">
              <p className="source-filename">{s.original_filename}</p>
              <p className="source-excerpt">{s.excerpt}…</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface ChatAreaProps {
  messages: Message[];
  loading: boolean;
  onEditMessage: (messageId: string, newContent: string) => void;
}

export default function ChatArea({
  messages,
  loading,
  onEditMessage,
}: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleCopy = async (index: number, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 1200);
    } catch {
      // clipboard unavailable (e.g. insecure context) — nothing to do
    }
  };

  const startEdit = (index: number, content: string) => {
    setEditingIndex(index);
    setEditDraft(content);
  };

  const commitEdit = () => {
    if (editingIndex === null) {
      return;
    }
    const trimmed = editDraft.trim();
    const message = messages[editingIndex];
    if (trimmed.length > 0 && trimmed !== message.content && message.id) {
      onEditMessage(message.id, trimmed);
    }
    setEditingIndex(null);
  };

  return (
    <div className="chat-area">
      {messages.length === 0 && !loading ? (
        <div className="chat-empty">
          <div className="chat-empty-rule" />
          <p className="chat-empty-title">An open notebook</p>
          <p className="chat-empty-subtitle">
            Upload documents, then ask anything — Lumina answers only from this
            workspace's pages.
          </p>
          <div className="chat-empty-rule" />
        </div>
      ) : (
        <div className="chat-messages">
          {messages.map((message, index) => {
            const isUser = message.role === "user";
            const isEditing = editingIndex === index;

            if (isUser && isEditing) {
              return (
                <div key={index} className="chat-row chat-row--user">
                  <div className="chat-edit-box">
                    <textarea
                      className="chat-edit-textarea"
                      value={editDraft}
                      autoFocus
                      onChange={(e) => setEditDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") {
                          setEditingIndex(null);
                        }
                        if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                          commitEdit();
                        }
                      }}
                      rows={Math.max(2, Math.ceil(editDraft.length / 60))}
                    />
                    <div className="chat-edit-actions">
                      <button
                        type="button"
                        className="btn btn--primary btn--small"
                        onClick={commitEdit}
                        disabled={editDraft.trim().length === 0}
                      >
                        Save & resend
                      </button>
                      <button
                        type="button"
                        className="btn btn--secondary btn--small"
                        onClick={() => setEditingIndex(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              );
            }

            return (
              <div
                key={index}
                className={
                  isUser ? "chat-row chat-row--user" : "chat-row chat-row--assistant"
                }
              >
                {isUser && (
                  <div className="chat-actions">
                    <button
                      type="button"
                      className="chat-action-btn"
                      title="Edit prompt"
                      onClick={() => startEdit(index, message.content)}
                      disabled={!message.id}
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      className="chat-action-btn"
                      title="Copy"
                      onClick={() => void handleCopy(index, message.content)}
                    >
                      {copiedIndex === index ? "✓" : "⧉"}
                    </button>
                  </div>
                )}
                <div
                  className={
                    isUser
                      ? "chat-bubble chat-bubble--user"
                      : "chat-bubble chat-bubble--assistant markdown-body"
                  }
                >
                  {isUser ? (
                    message.content
                  ) : (
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  )}
                  {message.sources && message.sources.length > 0 && (
                    <SourcesSection sources={message.sources} />
                  )}
                </div>
                {!isUser && (
                  <div className="chat-actions">
                    <button
                      type="button"
                      className="chat-action-btn"
                      title="Copy answer"
                      onClick={() => void handleCopy(index, message.content)}
                    >
                      {copiedIndex === index ? "✓" : "⧉"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          {loading && (
            <div className="chat-row chat-row--assistant">
              <div className="chat-bubble chat-bubble--assistant chat-bubble--loading">
                <span className="loading-dot" />
                <span className="loading-dot" />
                <span className="loading-dot" />
              </div>
            </div>
          )}
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
