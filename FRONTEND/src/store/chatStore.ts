import { create } from 'zustand';
import type { Citation, PipelineStep } from '../types/api';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  routeTaken?: string;
  latencyMs?: number;
  tokens?: { prompt: number; completion: number; total: number };
  hallucination_flag?: boolean;
  isStreaming?: boolean;
  createdAt: Date;
}

export interface ChatSession {
  id: string;
  category: string;
  createdAt: Date;
  /** True when this session was created locally and has not yet been persisted to the backend. */
  isLocal?: boolean;
}

export type StreamingStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error';

interface PipelineState {
  activeStep: PipelineStep | null;
  completedSteps: PipelineStep[];
  route: string | null;
}

interface ChatState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  messages: Record<string, Message[]>;        // sessionId → messages
  streamingStatus: StreamingStatus;
  streamingMessageId: string | null;           // id of the in-progress message bubble
  pipeline: PipelineState;

  // Actions
  setActiveSession: (id: string | null) => void;
  addSession: (s: ChatSession) => void;
  migrateSession: (oldSessionId: string, newSessionId: string, category: string) => void;
  addMessage: (sessionId: string, msg: Message) => void;
  appendToken: (sessionId: string, msgId: string, delta: string) => void;
  finaliseMessage: (sessionId: string, msgId: string, meta: Partial<Message>) => void;
  setPipeline: (p: Partial<PipelineState>) => void;
  setStreamingStatus: (s: StreamingStatus) => void;
  setStreamingMessageId: (id: string | null) => void;
  resetPipeline: () => void;
  loadHistorySessions: (sessions: ChatSession[]) => void;
  loadSessionMessages: (sessionId: string, msgs: Message[]) => void;
}

const INITIAL_PIPELINE: PipelineState = {
  activeStep: null,
  completedSteps: [],
  route: null,
};

export const useChatStore = create<ChatState>()((set) => ({
  sessions: [],
  activeSessionId: null,
  messages: {},
  streamingStatus: 'idle',
  streamingMessageId: null,
  pipeline: INITIAL_PIPELINE,

  setActiveSession: (id) => set({ activeSessionId: id }),

  addSession: (s) =>
    set((state) => {
      if (state.sessions.some((x) => x.id === s.id)) return state;
      return {
        sessions: [s, ...state.sessions],
        messages: {
          ...state.messages,
          [s.id]: state.messages[s.id] ?? [],
        },
      };
    }),

  migrateSession: (oldSessionId, newSessionId, category) =>
    set((state) => {
      const msgs = state.messages[oldSessionId] ?? state.messages[newSessionId] ?? [];
      const newMessages = { ...state.messages };
      delete newMessages[oldSessionId];
      newMessages[newSessionId] = msgs;

      const newSession: ChatSession = {
        id: newSessionId,
        category,
        createdAt: new Date(),
        isLocal: false,
      };

      const hasOld = state.sessions.some((s) => s.id === oldSessionId);
      let updatedSessions: ChatSession[];
      if (hasOld) {
        updatedSessions = state.sessions.map((s) => (s.id === oldSessionId ? newSession : s));
      } else {
        updatedSessions = [newSession, ...state.sessions.filter((s) => s.id !== newSessionId)];
      }

      return {
        sessions: updatedSessions,
        messages: newMessages,
        activeSessionId: state.activeSessionId === oldSessionId ? newSessionId : state.activeSessionId,
      };
    }),

  addMessage: (sessionId, msg) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [sessionId]: [...(state.messages[sessionId] ?? []), msg],
      },
    })),

  appendToken: (sessionId, msgId, delta) =>
    set((state) => {
      let targetId = sessionId;
      if (!state.messages[targetId]?.some((m) => m.id === msgId)) {
        const found = Object.keys(state.messages).find((key) =>
          state.messages[key]?.some((m) => m.id === msgId)
        );
        if (found) targetId = found;
      }

      return {
        messages: {
          ...state.messages,
          [targetId]: (state.messages[targetId] ?? []).map((m) =>
            m.id === msgId ? { ...m, content: m.content + delta } : m,
          ),
        },
      };
    }),

  finaliseMessage: (sessionId, msgId, meta) =>
    set((state) => {
      let targetId = sessionId;
      if (!state.messages[targetId]?.some((m) => m.id === msgId)) {
        const found = Object.keys(state.messages).find((key) =>
          state.messages[key]?.some((m) => m.id === msgId)
        );
        if (found) targetId = found;
      }

      return {
        messages: {
          ...state.messages,
          [targetId]: (state.messages[targetId] ?? []).map((m) =>
            m.id === msgId ? { ...m, ...meta, isStreaming: false } : m,
          ),
        },
      };
    }),

  setPipeline: (p) =>
    set((state) => ({
      pipeline: { ...state.pipeline, ...p },
    })),

  setStreamingStatus: (s) => set({ streamingStatus: s }),
  setStreamingMessageId: (id) => set({ streamingMessageId: id }),
  resetPipeline: () => set({ pipeline: INITIAL_PIPELINE }),
  
  loadHistorySessions: (newSessions) =>
    set((state) => {
      const localSessions = state.sessions.filter((s) => s.isLocal);
      return {
        sessions: [...localSessions, ...newSessions],
      };
    }),

  loadSessionMessages: (sessionId, msgs) =>
    set((state) => ({
      messages: { ...state.messages, [sessionId]: msgs },
    })),
}));
