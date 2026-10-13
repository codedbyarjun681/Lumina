import { create } from "zustand";
import type { Workspace } from "../types/Workspace";
import { api } from "../services/api";

interface WorkspaceStore {
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  loadWorkspaces: () => Promise<void>;
  createWorkspace: (name: string) => Promise<Workspace>;
  renameWorkspace: (id: string, name: string) => Promise<void>;
  updateWorkspaceLLM: (
    id: string,
    provider: string,
    model: string,
  ) => Promise<void>;
  deleteWorkspace: (id: string) => Promise<void>;
  setActiveWorkspace: (id: string | null) => void;
}

export const useWorkspaceStore = create<WorkspaceStore>((set, get) => ({
  workspaces: [],
  activeWorkspaceId: null,

  loadWorkspaces: async () => {
    const workspaces = await api.listWorkspaces();
    set((state) => {
      const stillExists = workspaces.some(
        (w) => w.id === state.activeWorkspaceId,
      );
      return {
        workspaces,
        activeWorkspaceId: stillExists ? state.activeWorkspaceId : (workspaces[0]?.id ?? null),
      };
    });
  },

  createWorkspace: async (name) => {
    const workspace = await api.createWorkspace(name);
    set((state) => ({
      workspaces: [...state.workspaces, workspace],
      activeWorkspaceId: workspace.id,
    }));
    return workspace;
  },

  renameWorkspace: async (id, name) => {
    const updated = await api.renameWorkspace(id, name);
    set((state) => ({
      workspaces: state.workspaces.map((w) => (w.id === id ? updated : w)),
    }));
  },

  updateWorkspaceLLM: async (id, provider, model) => {
    const updated = await api.updateWorkspaceLLM(id, provider, model);
    set((state) => ({
      workspaces: state.workspaces.map((w) => (w.id === id ? updated : w)),
    }));
  },

  deleteWorkspace: async (id) => {
    await api.deleteWorkspace(id);
    const remaining = get().workspaces.filter((w) => w.id !== id);
    set((state) => ({
      workspaces: remaining,
      activeWorkspaceId:
        state.activeWorkspaceId === id
          ? (remaining[0]?.id ?? null)
          : state.activeWorkspaceId,
    }));
  },

  setActiveWorkspace: (id) => {
    set({ activeWorkspaceId: id });
  },
}));
