import { useEffect, useState } from "react";
import { useWorkspaceStore } from "../store/workspaceStore";
import { useConversationStore } from "../store/conversationStore";

interface SidebarProps {
  onUploadClick: () => void;
  onSettingsClick: () => void;
  onMemoryClick: () => void;
  onDocumentsClick: () => void;
  onQuizClick: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export default function Sidebar({
  onUploadClick,
  onSettingsClick,
  onMemoryClick,
  onDocumentsClick,
  onQuizClick,
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const setActiveWorkspace = useWorkspaceStore((s) => s.setActiveWorkspace);
  const loadWorkspaces = useWorkspaceStore((s) => s.loadWorkspaces);

  const conversations = useConversationStore((s) => s.conversations);
  const activeConversationId = useConversationStore(
    (s) => s.activeConversationId,
  );
  const loadConversations = useConversationStore((s) => s.loadConversations);
  const createConversation = useConversationStore((s) => s.createConversation);
  const renameConversation = useConversationStore((s) => s.renameConversation);
  const deleteConversation = useConversationStore((s) => s.deleteConversation);
  const setActiveConversation = useConversationStore(
    (s) => s.setActiveConversation,
  );

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  // Load conversations whenever the active workspace changes
  useEffect(() => {
    if (activeWorkspaceId !== null) {
      void loadConversations(activeWorkspaceId);
    }
  }, [activeWorkspaceId, loadConversations]);

  const startRename = (id: string, currentName: string) => {
    setRenamingId(id);
    setRenameDraft(currentName);
  };

  const commitRename = () => {
    if (renamingId !== null && renameDraft.trim().length > 0) {
      void renameConversation(renamingId, renameDraft.trim());
    }
    setRenamingId(null);
  };

  return (
    <aside
      className={
        collapsed ? "sidebar sidebar--collapsed" : "sidebar"
      }
      aria-hidden={collapsed}
    >
      <div className="sidebar-inner">
        <div className="sidebar-logo">
          <span className="sidebar-logo-mark">◆</span>
          <span className="sidebar-logo-text">Lumina</span>
          <button
            type="button"
            className="sidebar-collapse-btn"
            title="Collapse sidebar"
            onClick={onToggleCollapse}
          >
            ‹
          </button>
        </div>

      <nav className="sidebar-nav">
        <p className="sidebar-section-label">Workspaces</p>
        {workspaces.length === 0 && (
          <p className="sidebar-empty">
            No workspaces yet. Create one in Settings.
          </p>
        )}
        <ul className="sidebar-workspace-list">
          {workspaces.map((workspace) => {
            const isActive = workspace.id === activeWorkspaceId;
            return (
              <li key={workspace.id}>
                <button
                  type="button"
                  className={
                    isActive
                      ? "sidebar-workspace sidebar-workspace--active"
                      : "sidebar-workspace"
                  }
                  onClick={() => setActiveWorkspace(workspace.id)}
                >
                  <span className="sidebar-workspace-accent" />
                  <span className="sidebar-workspace-name">
                    {workspace.name}
                  </span>
                </button>

                {isActive && (
                  <div className="sidebar-conversations">
                    <button
                      type="button"
                      className="sidebar-new-chat"
                      onClick={() => void createConversation(workspace.id)}
                    >
                      + New Chat
                    </button>
                    <ul className="sidebar-conversation-list">
                      {conversations.map((conversation) => {
                        const isConversationActive =
                          conversation.id === activeConversationId;
                        const isRenaming = conversation.id === renamingId;
                        return (
                          <li key={conversation.id}>
                            {isRenaming ? (
                              <input
                                type="text"
                                className="field sidebar-rename-field"
                                value={renameDraft}
                                autoFocus
                                onChange={(e) =>
                                  setRenameDraft(e.target.value)
                                }
                                onBlur={commitRename}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    commitRename();
                                  }
                                  if (e.key === "Escape") {
                                    setRenamingId(null);
                                  }
                                }}
                              />
                            ) : (
                              <div
                                className={
                                  isConversationActive
                                    ? "sidebar-conversation sidebar-conversation--active"
                                    : "sidebar-conversation"
                                }
                              >
                                <button
                                  type="button"
                                  className="sidebar-conversation-name"
                                  onClick={() =>
                                    setActiveConversation(conversation.id)
                                  }
                                >
                                  {conversation.name}
                                </button>
                                <span className="sidebar-conversation-actions">
                                  <button
                                    type="button"
                                    className="sidebar-icon-btn"
                                    title="Rename conversation"
                                    onClick={() =>
                                      startRename(
                                        conversation.id,
                                        conversation.name,
                                      )
                                    }
                                  >
                                    ✎
                                  </button>
                                  <button
                                    type="button"
                                    className="sidebar-icon-btn"
                                    title="Delete conversation"
                                    onClick={() =>
                                      void deleteConversation(conversation.id)
                                    }
                                  >
                                    ✕
                                  </button>
                                </span>
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="sidebar-footer">
        <button
          type="button"
          className="sidebar-footer-btn"
          onClick={onUploadClick}
        >
          Upload
        </button>
        <button
          type="button"
          className="sidebar-footer-btn"
          onClick={onDocumentsClick}
        >
          Documents
        </button>
        <button
          type="button"
          className="sidebar-footer-btn"
          onClick={onQuizClick}
        >
          Quiz
        </button>
        <button
          type="button"
          className="sidebar-footer-btn"
          onClick={onMemoryClick}
        >
          Memory
        </button>
        <button
          type="button"
          className="sidebar-footer-btn"
          onClick={onSettingsClick}
        >
          Settings
        </button>
      </div>
      </div>
    </aside>
  );
}
