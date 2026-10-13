import { create } from "zustand";
import type { Conversation } from "../types/Conversation";
import { api } from "../services/api";

interface ConversationState {
  conversations: Conversation[];
  activeConversationId: string | null;
  loadConversations: (workspaceId: string) => Promise<void>;
  createConversation: (workspaceId: string) => Promise<void>;
  renameConversation: (id: string, name: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  setActiveConversation: (id: string) => void;
  applyConversationName: (id: string, name: string) => void;
  updateConversationModel: (
    id: string,
    provider: string,
    model: string,
  ) => Promise<void>;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  activeConversationId: null,

  loadConversations: async (workspaceId) => {
    let conversations = await api.fetchConversations(workspaceId);

    // Every workspace always has at least one conversation to land in
    if (conversations.length === 0) {
      const created = await api.createConversation(
        workspaceId,
        "New Conversation",
      );
      conversations = [created];
    }

    set((state) => {
      const stillExists = conversations.some(
        (c) => c.id === state.activeConversationId,
      );
      return {
        conversations,
        activeConversationId: stillExists
          ? state.activeConversationId
          : conversations[0].id,
      };
    });
  },

  createConversation: async (workspaceId) => {
    const conversation = await api.createConversation(workspaceId);
    set((state) => ({
      conversations: [conversation, ...state.conversations],
      activeConversationId: conversation.id,
    }));
  },

  renameConversation: async (id, name) => {
    const updated = await api.renameConversation(id, name);
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? updated : c,
      ),
    }));
  },

  deleteConversation: async (id) => {
    await api.deleteConversation(id);
    const remaining = get().conversations.filter((c) => c.id !== id);
    set((state) => ({
      conversations: remaining,
      activeConversationId:
        state.activeConversationId === id
          ? (remaining[0]?.id ?? null)
          : state.activeConversationId,
    }));
  },

  setActiveConversation: (id) => {
    set({ activeConversationId: id });
  },

  applyConversationName: (id, name) => {
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? { ...c, name } : c,
      ),
    }));
  },

  updateConversationModel: async (id, provider, model) => {
    const updated = await api.updateConversationLLM(id, model, provider);
    set((state) => ({
      conversations: state.conversations.map((c) =>
        c.id === id ? updated : c,
      ),
    }));
  },
}));
