import { useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar";
import SidePanel from "./components/SidePanel";
import QuizPanel from "./components/QuizPanel";
import ChatSession, { type ChatSessionHandle } from "./components/ChatSession";
import { useWorkspaceStore } from "./store/workspaceStore";
import { useConversationStore } from "./store/conversationStore";
import { api, type ProviderInfo, type ProviderModel } from "./services/api";
import type { Workspace } from "./types/Workspace";
import type { MemoryEntry } from "./types/Memory";
import type {
  DocumentSearchResult,
  WorkspaceDocument,
} from "./types/Document";
import {
  applyTheme,
  colorwaysFor,
  resolveTheme,
  type ThemeMode,
} from "./theme";
import "./App.css";

function formatUploadDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface WorkspaceRowProps {
  workspace: Workspace;
}

function WorkspaceRow({ workspace }: WorkspaceRowProps) {
  const renameWorkspace = useWorkspaceStore((s) => s.renameWorkspace);
  const deleteWorkspace = useWorkspaceStore((s) => s.deleteWorkspace);
  const [nameDraft, setNameDraft] = useState(workspace.name);
  const [saving, setSaving] = useState(false);
  const nameChanged = nameDraft.trim() !== workspace.name;

  const handleRename = async () => {
    if (!nameChanged || saving) {
      return;
    }
    setSaving(true);
    try {
      await renameWorkspace(workspace.id, nameDraft.trim());
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="workspace-row">
      <div className="workspace-row-line">
        <input
          type="text"
          className="field"
          value={nameDraft}
          onChange={(e) => setNameDraft(e.target.value)}
          aria-label="Workspace name"
        />
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => void handleRename()}
          disabled={!nameChanged || saving}
        >
          Rename
        </button>
        <button
          type="button"
          className="btn btn--danger"
          onClick={() => void deleteWorkspace(workspace.id)}
          disabled={saving}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

interface ApiKeyFieldProps {
  provider: ProviderInfo;
  isSet: boolean;
  onSaved: () => void;
}

function ApiKeyField({ provider, isSet, onSaved }: ApiKeyFieldProps) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    const key = value.trim();
    if (key.length === 0 || saving) {
      return;
    }
    setSaving(true);
    try {
      await api.setApiKey(provider.id, key);
      setValue("");
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel-section">
      <p className="panel-label">{provider.name} API key</p>
      <p className="panel-muted">
        {isSet ? "A key is currently configured." : "No key configured yet."}
      </p>
      <div className="workspace-row-line">
        <input
          type="password"
          className="field"
          placeholder="Paste your API key…"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => void handleSave()}
          disabled={value.trim().length === 0 || saving}
        >
          Save
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const createWorkspace = useWorkspaceStore((s) => s.createWorkspace);
  const conversations = useConversationStore((s) => s.conversations);
  const activeConversationId = useConversationStore(
    (s) => s.activeConversationId,
  );

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId);
  const activeConversation = conversations.find(
    (c) => c.id === activeConversationId,
  );

  const [settingsPanelOpen, setSettingsPanelOpen] = useState(false);
  const [memoryPanelOpen, setMemoryPanelOpen] = useState(false);
  const [memoryEntries, setMemoryEntries] = useState<MemoryEntry[]>([]);
  const [newMemoryText, setNewMemoryText] = useState("");
  const [editingMemoryId, setEditingMemoryId] = useState<string | null>(null);
  const [editingMemoryDraft, setEditingMemoryDraft] = useState("");

  const [documentsPanelOpen, setDocumentsPanelOpen] = useState(false);
  const [quizPanelOpen, setQuizPanelOpen] = useState(false);
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([]);
  const [searchResults, setSearchResults] = useState<DocumentSearchResult[]>(
    [],
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [confirmDeleteDocId, setConfirmDeleteDocId] = useState<string | null>(
    null,
  );

  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [apiKeysSet, setApiKeysSet] = useState<Record<string, boolean>>({});
  const [localModels, setLocalModels] = useState<Record<string, number>>({});

  const [newProviderName, setNewProviderName] = useState("");
  const [newProviderBaseUrl, setNewProviderBaseUrl] = useState("");
  const [addingProvider, setAddingProvider] = useState(false);

  // Appearance
  const [theme, setTheme] = useState<ThemeMode>("light");
  const [colorway, setColorway] = useState<string>("warm");
  const [colorwayPickerOpen, setColorwayPickerOpen] = useState(false);

  // Global model defaults
  const [defaultProvider, setDefaultProvider] = useState<string | null>(null);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
  const [defaultProviderDraft, setDefaultProviderDraft] = useState("");
  const [defaultModelDraft, setDefaultModelDraft] = useState("");

  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [creating, setCreating] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatSessionRef = useRef<ChatSessionHandle>(null);

  // ——— Sidebar collapse ———

  const [sidebarOpen, setSidebarOpen] = useState(
    () =>
      typeof window !== "undefined" &&
      window.localStorage.getItem("lumina:sidebar") !== "collapsed",
  );

  useEffect(() => {
    window.localStorage.setItem(
      "lumina:sidebar",
      sidebarOpen ? "open" : "collapsed",
    );
  }, [sidebarOpen]);

  const toggleSidebar = () => setSidebarOpen((open) => !open);

  // Effective chain for the chat bar: conversation override → global defaults
  const effectiveProviderId =
    activeConversation?.llm_provider ?? defaultProvider ?? null;
  const effectiveModel =
    activeConversation?.llm_model ??
    defaultModel ??
    activeWorkspace?.llm_model ??
    "";

  // ——— Theme setup ———

  useEffect(() => {
    void (async () => {
      try {
        const settings = await api.getSettings();
        const t = (settings.theme as ThemeMode | null) ?? "light";
        const c = settings.colorway ?? null;
        setTheme(t);
        setColorway(c ?? "warm");
        applyTheme(t, c);
        setDefaultProvider(settings.default_provider ?? null);
        setDefaultModel(settings.default_model ?? null);
        setDefaultProviderDraft(settings.default_provider ?? "");
        setDefaultModelDraft(settings.default_model ?? "");
      } catch {
        applyTheme("light", null);
      }
    })();
  }, []);

  // React to OS theme changes while in "system" mode
  useEffect(() => {
    if (theme !== "system") {
      return;
    }
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system", colorway);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme, colorway]);

  const handleSelectTheme = (mode: ThemeMode) => {
    setTheme(mode);
    setColorwayPickerOpen(true);
    void api.updatePreferences({ theme: mode });
    applyTheme(mode, colorway);
  };

  const handleSelectColorway = (id: string) => {
    setColorway(id);
    setColorwayPickerOpen(false);
    void api.updatePreferences({ colorway: id });
    applyTheme(theme, id);
  };

  // ——— Settings panel data ———

  const handleOpenSettingsPanel = () => {
    setSettingsPanelOpen(true);
    void (async () => {
      try {
        const [settings, providerList] = await Promise.all([
          api.getSettings(),
          api.getProviders(),
        ]);
        setApiKeysSet(settings.api_keys_set);
        setProviders(providerList);
        setDefaultProvider(settings.default_provider ?? null);
        setDefaultModel(settings.default_model ?? null);
        setDefaultProviderDraft(settings.default_provider ?? "");
        setDefaultModelDraft(settings.default_model ?? "");

        // Local model detection banner
        const local: Record<string, number> = {};
        await Promise.all(
          providerList
            .filter((p) => p.kind === "ollama")
            .map(async (p) => {
              const models = await api.getModels(p.id);
              if (models.length > 0) {
                local[p.id] = models.length;
              }
            }),
        );
        for (const p of providerList.filter(
          (p) => p.base_url?.includes("localhost") && p.kind === "openai",
        )) {
          const models = await api.getModels(p.id);
          if (models.length > 0) {
            local[p.id] = models.length;
          }
        }
        setLocalModels(local);
      } catch {
        setProviders([]);
      }
    })();
  };

  const handleAddProvider = async () => {
    const name = newProviderName.trim();
    const baseUrl = newProviderBaseUrl.trim();
    if (name.length === 0 || baseUrl.length === 0 || addingProvider) {
      return;
    }
    setAddingProvider(true);
    try {
      await api.addProvider(name, baseUrl, true);
      setNewProviderName("");
      setNewProviderBaseUrl("");
      setProviders(await api.getProviders());
    } finally {
      setAddingProvider(false);
    }
  };

  const handleDeleteProvider = async (id: string) => {
    await api.deleteProvider(id);
    setProviders(await api.getProviders());
  };

  const handleSaveDefaults = async () => {
    if (defaultProviderDraft.trim().length === 0) {
      return;
    }
    await api.updatePreferences({
      default_provider: defaultProviderDraft,
      ...(defaultModelDraft.trim().length > 0
        ? { default_model: defaultModelDraft }
        : {}),
    });
    setDefaultProvider(defaultProviderDraft);
    setDefaultModel(defaultModelDraft || null);
  };

  const handleSetLocalAsDefault = async (providerId: string) => {
    const models = await api.getModels(providerId).catch(() => []);
    await api.updatePreferences({
      default_provider: providerId,
      ...(models[0] ? { default_model: models[0].id } : {}),
    });
    setDefaultProvider(providerId);
    setDefaultModel(models[0]?.id ?? null);
    setDefaultProviderDraft(providerId);
    setDefaultModelDraft(models[0]?.id ?? "");
  };

  const handleCreateWorkspace = async () => {
    const name = newWorkspaceName.trim();
    if (name.length === 0 || creating) {
      return;
    }
    setCreating(true);
    try {
      await createWorkspace(name);
      setNewWorkspaceName("");
    } finally {
      setCreating(false);
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  // ——— Memory panel ———

  const reloadMemory = async (workspaceId: string) => {
    try {
      setMemoryEntries(await api.fetchMemory(workspaceId));
    } catch {
      setMemoryEntries([]);
    }
  };

  const handleOpenMemoryPanel = () => {
    setMemoryPanelOpen(true);
    if (activeWorkspaceId !== null) {
      void reloadMemory(activeWorkspaceId);
    }
  };

  const handleAddMemory = async () => {
    const content = newMemoryText.trim();
    if (activeWorkspaceId === null || content.length === 0) {
      return;
    }
    await api.createMemoryEntry(activeWorkspaceId, content);
    setNewMemoryText("");
    await reloadMemory(activeWorkspaceId);
  };

  const handleSaveMemoryEdit = async (id: string) => {
    const content = editingMemoryDraft.trim();
    if (activeWorkspaceId === null || content.length === 0) {
      setEditingMemoryId(null);
      return;
    }
    await api.editMemoryEntry(id, content);
    setEditingMemoryId(null);
    await reloadMemory(activeWorkspaceId);
  };

  const handleDeleteMemory = async (id: string) => {
    if (activeWorkspaceId === null) {
      return;
    }
    await api.deleteMemoryEntry(id);
    await reloadMemory(activeWorkspaceId);
  };

  // ——— Documents panel ———

  const reloadDocuments = async (workspaceId: string) => {
    try {
      setDocuments(await api.fetchDocuments(workspaceId));
    } catch {
      setDocuments([]);
    }
  };

  const handleOpenDocumentsPanel = () => {
    setDocumentsPanelOpen(true);
    setSearchQuery("");
    setSearchResults([]);
    if (activeWorkspaceId !== null) {
      void reloadDocuments(activeWorkspaceId);
    }
  };

  const handleOpenQuizPanel = () => {
    setQuizPanelOpen(true);
    if (activeWorkspaceId !== null) {
      void reloadDocuments(activeWorkspaceId);
    }
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (value.trim().length === 0) {
      setSearchResults([]);
    }
  };

  useEffect(() => {
    if (activeWorkspaceId === null) {
      return;
    }
    const query = searchQuery.trim();
    if (query.length === 0) {
      return;
    }
    const timer = setTimeout(() => {
      void (async () => {
        try {
          setSearchResults(await api.searchDocuments(activeWorkspaceId, query));
        } catch {
          setSearchResults([]);
        }
      })();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, activeWorkspaceId]);

  const handleDeleteDocument = async (documentId: string) => {
    if (activeWorkspaceId === null) {
      return;
    }
    await api.deleteDocument(activeWorkspaceId, documentId);
    setConfirmDeleteDocId(null);
    await reloadDocuments(activeWorkspaceId);
    if (searchQuery.trim().length > 0) {
      setSearchResults(
        await api.searchDocuments(activeWorkspaceId, searchQuery.trim()),
      );
    }
  };

  const resolvedFamily = resolveTheme(theme);
  const colorwayOptions = colorwaysFor(theme);

  return (
    <div className="app-shell">
      <Sidebar
        onUploadClick={handleUploadClick}
        onSettingsClick={handleOpenSettingsPanel}
        onMemoryClick={handleOpenMemoryPanel}
        onDocumentsClick={handleOpenDocumentsPanel}
        onQuizClick={handleOpenQuizPanel}
        collapsed={!sidebarOpen}
        onToggleCollapse={toggleSidebar}
      />

      <main className="main-area">
        {!sidebarOpen && (
          <button
            type="button"
            className="sidebar-reopen"
            title="Open sidebar"
            onClick={toggleSidebar}
          >
            ☰
          </button>
        )}
        <ChatSession
          key={activeConversationId ?? "none"}
          ref={chatSessionRef}
          workspaceId={activeWorkspaceId}
          conversationId={activeConversationId}
          providerId={effectiveProviderId}
          model={effectiveModel}
        />
      </main>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.pptx"
        multiple
        className="visually-hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length > 0) {
            chatSessionRef.current?.handleFileSelected(files);
          }
          e.target.value = "";
        }}
      />

      <SidePanel
        title="Settings"
        isOpen={settingsPanelOpen}
        onClose={() => setSettingsPanelOpen(false)}
      >
        <div className="panel-section">
          <p className="panel-label">UI Theme</p>
          <div className="theme-modes">
            {(["light", "dark", "system"] as ThemeMode[]).map((mode) => (
              <button
                key={mode}
                type="button"
                className={
                  theme === mode
                    ? "theme-mode-btn theme-mode-btn--active"
                    : "theme-mode-btn"
                }
                onClick={() => handleSelectTheme(mode)}
              >
                {mode === "system" ? "System default" : mode[0].toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
          {colorwayPickerOpen && (
            <div className="colorway-popover">
              {colorwayOptions.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={
                    colorway === opt.id
                      ? "colorway-swatch colorway-swatch--active"
                      : "colorway-swatch"
                  }
                  onClick={() => handleSelectColorway(opt.id)}
                >
                  <span
                    className="colorway-swatch-preview"
                    style={{
                      background: `linear-gradient(135deg, ${opt.swatchBg} 55%, ${opt.swatchAccent} 55%)`,
                    }}
                  />
                  {opt.name}
                  {colorway === opt.id && <span>✓</span>}
                </button>
              ))}
              <span className="panel-muted" style={{ gridColumn: "1 / -1" }}>
                {theme === "system"
                  ? `System is currently ${resolvedFamily}.`
                  : `${resolvedFamily === "dark" ? "Dark" : "Light"} colorways`}
              </span>
            </div>
          )}
        </div>

        {Object.entries(localModels).map(([providerId, count]) => (
          <div key={providerId} className="local-banner">
            <span>
              Detected {count} local model{count === 1 ? "" : "s"} via{" "}
              {providers.find((p) => p.id === providerId)?.name ?? providerId}.
            </span>
            <button
              type="button"
              className="btn btn--primary btn--small"
              onClick={() => void handleSetLocalAsDefault(providerId)}
            >
              Use as default
            </button>
          </div>
        ))}

        <div className="panel-section">
          <p className="panel-label">Model defaults</p>
          <p className="panel-muted">
            Used when a conversation has no model of its own.
          </p>
          <div className="workspace-row-line">
            <select
              className="field field--select"
              value={defaultProviderDraft}
              onChange={(e) => {
                setDefaultProviderDraft(e.target.value);
                setDefaultModelDraft("");
              }}
              aria-label="Default provider"
            >
              <option value="">Select provider…</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <DefaultModelPicker
              providerId={defaultProviderDraft || null}
              value={defaultModelDraft}
              onChange={setDefaultModelDraft}
            />
          </div>
          <div className="workspace-row-line" style={{ marginTop: 8 }}>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void handleSaveDefaults()}
              disabled={defaultProviderDraft.trim().length === 0}
            >
              Save defaults
            </button>
            {defaultProvider && (
              <span className="panel-muted" style={{ alignSelf: "center" }}>
                Current: {defaultModel ?? "(none)"}
              </span>
            )}
          </div>
        </div>

        <div className="panel-section">
          <p className="panel-label">Workspaces</p>
          <div className="workspace-row-line">
            <input
              type="text"
              className="field"
              placeholder="New workspace name…"
              value={newWorkspaceName}
              onChange={(e) => setNewWorkspaceName(e.target.value)}
            />
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void handleCreateWorkspace()}
              disabled={newWorkspaceName.trim().length === 0 || creating}
            >
              Create
            </button>
          </div>
          <div style={{ marginTop: 12 }}>
            {workspaces.length === 0 && (
              <p className="panel-muted">No workspaces yet.</p>
            )}
            {workspaces.map((workspace) => (
              <WorkspaceRow key={workspace.id} workspace={workspace} />
            ))}
          </div>
        </div>

        <div className="panel-section">
          <p className="panel-label">Providers</p>
          {providers.map((provider) => (
            <div key={provider.id} className="provider-row">
              <div className="provider-row-info">
                <span className="provider-row-name">{provider.name}</span>
                {provider.is_builtin ? (
                  <span className="memory-badge memory-badge--auto">
                    built-in
                  </span>
                ) : (
                  <span className="memory-badge memory-badge--manual">
                    custom
                  </span>
                )}
              </div>
              {!provider.is_builtin && (
                <button
                  type="button"
                  className="sidebar-icon-btn"
                  title="Delete provider"
                  onClick={() => void handleDeleteProvider(provider.id)}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="panel-section">
          <p className="panel-label">Add custom provider</p>
          <p className="panel-muted">
            Any OpenAI-compatible endpoint (e.g. Groq, Together, a local
            vLLM/LiteLLM server).
          </p>
          <div className="workspace-row-line">
            <input
              type="text"
              className="field"
              placeholder="Name (e.g. Groq)"
              value={newProviderName}
              onChange={(e) => setNewProviderName(e.target.value)}
            />
          </div>
          <div className="workspace-row-line" style={{ marginTop: 8 }}>
            <input
              type="text"
              className="field"
              placeholder="Base URL (https://api.groq.com/openai/v1)"
              value={newProviderBaseUrl}
              onChange={(e) => setNewProviderBaseUrl(e.target.value)}
            />
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void handleAddProvider()}
              disabled={
                newProviderName.trim().length === 0 ||
                newProviderBaseUrl.trim().length === 0 ||
                addingProvider
              }
            >
              Add
            </button>
          </div>
        </div>

        <div className="panel-section">
          <p className="panel-label">API keys</p>
          {providers
            .filter((p) => p.needs_api_key)
            .map((provider) => (
              <ApiKeyField
                key={provider.id}
                provider={provider}
                isSet={apiKeysSet[provider.id] ?? false}
                onSaved={() =>
                  setApiKeysSet((prev) => ({ ...prev, [provider.id]: true }))
                }
              />
            ))}
        </div>
      </SidePanel>

      <SidePanel
        title="Quiz"
        isOpen={quizPanelOpen}
        onClose={() => setQuizPanelOpen(false)}
      >
        <QuizPanel
          workspaceId={activeWorkspaceId}
          documentCount={documents.length}
        />
      </SidePanel>

      <SidePanel
        title="Workspace Documents"
        isOpen={documentsPanelOpen}
        onClose={() => setDocumentsPanelOpen(false)}
      >
        {activeWorkspaceId === null ? (
          <p className="panel-muted">Select a workspace to view its documents.</p>
        ) : (
          <>
            <div className="panel-section">
              <input
                type="text"
                className="field"
                placeholder="Search by filename or content…"
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
              />
            </div>

            <div className="panel-section">
              {searchQuery.trim().length === 0 ? (
                documents.length === 0 ? (
                  <p className="panel-muted">No documents uploaded yet.</p>
                ) : (
                  documents.map((doc) => (
                    <div key={doc.id} className="document-entry">
                      <div className="document-entry-info">
                        <span className="document-entry-name">
                          {doc.original_filename}
                        </span>
                        <span className="document-entry-date">
                          {formatUploadDate(doc.uploaded_at)}
                        </span>
                      </div>
                      {confirmDeleteDocId === doc.id ? (
                        <span className="document-entry-confirm">
                          Delete?
                          <button
                            type="button"
                            className="btn btn--danger btn--small"
                            onClick={() => void handleDeleteDocument(doc.id)}
                          >
                            Yes
                          </button>
                          <button
                            type="button"
                            className="btn btn--secondary btn--small"
                            onClick={() => setConfirmDeleteDocId(null)}
                          >
                            No
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="sidebar-icon-btn"
                          title="Delete document"
                          onClick={() => setConfirmDeleteDocId(doc.id)}
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))
                )
              ) : searchResults.length === 0 ? (
                <p className="panel-muted">No documents match your search.</p>
              ) : (
                searchResults.map((result) => (
                  <div key={result.id} className="document-entry">
                    <div className="document-entry-info">
                      <span className="document-entry-name">
                        {result.original_filename}
                      </span>
                      <span className="document-entry-date">
                        {formatUploadDate(result.uploaded_at)}
                        <span
                          className={`match-badge match-badge--${result.match_type}`}
                        >
                          {result.match_type}
                        </span>
                      </span>
                      {result.excerpt && (
                        <span className="document-entry-excerpt">
                          {result.excerpt}…
                        </span>
                      )}
                    </div>
                    {confirmDeleteDocId === result.id ? (
                      <span className="document-entry-confirm">
                        Delete?
                        <button
                          type="button"
                          className="btn btn--danger btn--small"
                          onClick={() => void handleDeleteDocument(result.id)}
                        >
                          Yes
                        </button>
                        <button
                          type="button"
                          className="btn btn--secondary btn--small"
                          onClick={() => setConfirmDeleteDocId(null)}
                        >
                          No
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="sidebar-icon-btn"
                        title="Delete document"
                        onClick={() => setConfirmDeleteDocId(result.id)}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </SidePanel>

      <SidePanel
        title="Workspace Memory"
        isOpen={memoryPanelOpen}
        onClose={() => setMemoryPanelOpen(false)}
      >
        <div className="panel-section">
          <p className="panel-label">Add a memory</p>
          <div className="workspace-row-line">
            <input
              type="text"
              className="field"
              placeholder="e.g. Prefers concise explanations"
              value={newMemoryText}
              onChange={(e) => setNewMemoryText(e.target.value)}
            />
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => void handleAddMemory()}
              disabled={newMemoryText.trim().length === 0}
            >
              Add Memory
            </button>
          </div>
        </div>

        <div className="panel-section">
          <p className="panel-label">What Lumina remembers</p>
          {memoryEntries.length === 0 && (
            <p className="panel-muted">
              Nothing yet. Lumina learns from your chats, or you can add
              memories manually above.
            </p>
          )}
          {memoryEntries.map((entry) => (
            <div key={entry.id} className="memory-entry">
              {editingMemoryId === entry.id ? (
                <input
                  type="text"
                  className="field"
                  value={editingMemoryDraft}
                  autoFocus
                  onChange={(e) => setEditingMemoryDraft(e.target.value)}
                  onBlur={() => void handleSaveMemoryEdit(entry.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      void handleSaveMemoryEdit(entry.id);
                    }
                    if (e.key === "Escape") {
                      setEditingMemoryId(null);
                    }
                  }}
                />
              ) : (
                <button
                  type="button"
                  className="memory-entry-content"
                  title="Click to edit"
                  onClick={() => {
                    setEditingMemoryId(entry.id);
                    setEditingMemoryDraft(entry.content);
                  }}
                >
                  {entry.content}
                </button>
              )}
              <div className="memory-entry-meta">
                <span
                  className={
                    entry.source === "auto"
                      ? "memory-badge memory-badge--auto"
                      : "memory-badge memory-badge--manual"
                  }
                >
                  {entry.source}
                </span>
                <button
                  type="button"
                  className="sidebar-icon-btn"
                  title="Delete memory"
                  onClick={() => void handleDeleteMemory(entry.id)}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      </SidePanel>
    </div>
  );
}

// Small helper component: models for the chosen default provider, fetched lazily
function DefaultModelPicker({
  providerId,
  value,
  onChange,
}: {
  providerId: string | null;
  value: string;
  onChange: (v: string) => void;
}) {
  const [models, setModels] = useState<ProviderModel[]>([]);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    if (!providerId || loadedFor === providerId) {
      return;
    }
    void (async () => {
      try {
        setModels(await api.getModels(providerId));
      } catch {
        setModels([]);
      } finally {
        setLoadedFor(providerId);
      }
    })();
  }, [providerId, loadedFor]);

  return (
    <select
      className="field field--select"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Default model"
      disabled={!providerId}
    >
      <option value="">{providerId ? "Select model…" : "Pick a provider first"}</option>
      {models.map((m) => (
        <option key={m.id} value={m.id}>
          {m.name}
        </option>
      ))}
    </select>
  );
}
