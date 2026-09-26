import { create } from 'zustand';
import { api } from '../services/api';

const storageKey = 'ops-agent-chat-v1';

export type AgentMessageRole = 'user' | 'assistant';
export type AgentMessageStatus = 'sent' | 'loading' | 'error';

export interface AgentMessage {
  id: string;
  role: AgentMessageRole;
  text: string;
  status: AgentMessageStatus;
  createdAt: number;
}

interface SavedChat {
  threadId?: string | null;
  messages?: AgentMessage[];
}

interface AgentChatState {
  threadId: string | null;
  messages: AgentMessage[];
  pending: boolean;
  send: (message: string, frameId?: string | null) => Promise<void>;
  clearError: (id: string) => void;
}

const id = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

function loadChat(): SavedChat {
  if (typeof window === 'undefined') return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(storageKey) ?? '{}') as SavedChat;
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.messages)) return {};
    return {
      threadId: typeof parsed.threadId === 'string' ? parsed.threadId : null,
      messages: parsed.messages
        .filter(message => message && (message.role === 'user' || message.role === 'assistant') && typeof message.text === 'string')
        .map(message => ({ ...message, status: message.status === 'error' ? 'error' : 'sent' })),
    };
  } catch {
    return {};
  }
}

function saveChat(state: Pick<AgentChatState, 'threadId' | 'messages'>) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(storageKey, JSON.stringify({
      threadId: state.threadId,
      messages: state.messages.filter(message => message.status !== 'loading'),
    }));
  } catch {
    // localStorage may be unavailable; chat continues in memory.
  }
}

const saved = loadChat();

export const useAgentChatStore = create<AgentChatState>((set, get) => ({
  threadId: saved.threadId ?? null,
  messages: saved.messages ?? [],
  pending: false,
  clearError: messageId => set(state => {
    const next = { ...state, messages: state.messages.filter(message => message.id !== messageId) };
    saveChat(next);
    return next;
  }),
  send: async (rawMessage, frameId) => {
    const message = rawMessage.trim();
    if (!message || get().pending) return;

    const userMessage: AgentMessage = { id: id(), role: 'user', text: message, status: 'sent', createdAt: Date.now() };
    const assistantId = id();
    const assistantMessage: AgentMessage = { id: assistantId, role: 'assistant', text: '', status: 'loading', createdAt: Date.now() };

    set(state => {
      const next = {
        ...state,
        pending: true,
        messages: [...state.messages, userMessage, assistantMessage],
      };
      saveChat(next);
      return next;
    });

    try {
      const currentThread = get().threadId;
      const reply = await api.chat(message, currentThread, frameId ?? null);
      set(state => {
        const next = {
          ...state,
          threadId: reply.thread_id,
          pending: false,
          messages: state.messages.map(item => item.id === assistantId
            ? { ...item, text: reply.answer, status: 'sent' as const }
            : item),
        };
        saveChat(next);
        return next;
      });
    } catch (cause) {
      const text = cause instanceof Error ? cause.message : 'Ajan yanıtı alınamadı.';
      set(state => {
        const next = {
          ...state,
          pending: false,
          messages: state.messages.map(item => item.id === assistantId
            ? { ...item, text, status: 'error' as const }
            : item),
        };
        saveChat(next);
        return next;
      });
    }
  },
}));
