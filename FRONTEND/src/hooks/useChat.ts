/**
 * useChat — Chat orchestration hook.
 *
 * Composes useSSE + chatApi to provide a single, clean interface
 * for the chat UI:
 *  • Manages SSE lifecycle (connected while authenticated).
 *  • On SSEPipelineStepEvent → updates pipeline HUD state.
 *  • On SSETokenEvent       → appends delta to streaming message bubble.
 *  • On SSEMetaEvent        → finalises message with citations + metadata.
 *  • On SSEErrorEvent       → surfaces error, resets streaming state.
 *  • On SSEDoneEvent        → re-enables input.
 *  • sendMessage()          → persists user msg, submits to backend, creates
 *                             streaming message placeholder.
 */
import { useCallback } from 'react';
import { v4 as uuid } from 'uuid';
import { useSSE } from './useSSE';
import { chatApi } from '../api/chatApi';
import { useChatStore } from '../store/chatStore';
import { useAuthStore } from '../store/authStore';
import type { SSEEvent, SSEPipelineStepEvent } from '../types/api';

export function useChat() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Use individual selectors to avoid re-rendering on every store change.
  const streamingStatus     = useChatStore((s) => s.streamingStatus);
  const addMessage          = useChatStore((s) => s.addMessage);
  const appendToken         = useChatStore((s) => s.appendToken);
  const finaliseMessage     = useChatStore((s) => s.finaliseMessage);
  const setPipeline         = useChatStore((s) => s.setPipeline);
  const setStreamingStatus  = useChatStore((s) => s.setStreamingStatus);
  const setStreamingMessageId = useChatStore((s) => s.setStreamingMessageId);
  const resetPipeline       = useChatStore((s) => s.resetPipeline);

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      // Always read the latest sessionId from the store — avoids stale closure.
      const sessionId = useChatStore.getState().activeSessionId;
      if (!sessionId) return;

      switch (event.event) {
        case 'pipeline_step': {
          const e = event as SSEPipelineStepEvent;
          const { completedSteps } = useChatStore.getState().pipeline;
          setPipeline({
            activeStep: e.step,
            route: e.route ?? null,
            completedSteps: completedSteps.includes(e.step)
              ? completedSteps
              : [...completedSteps, e.step],
          });
          break;
        }

        case 'token': {
          const msgId = useChatStore.getState().streamingMessageId;
          if (!msgId) break;
          appendToken(sessionId, msgId, event.delta);
          break;
        }

        case 'meta': {
          const msgId = useChatStore.getState().streamingMessageId;
          if (!msgId) break;
          const targetSessionId = event.session_id || sessionId;
          finaliseMessage(targetSessionId, msgId, {
            citations: event.citations,
            routeTaken: event.route_taken,
            latencyMs: event.latency_ms,
            tokens: event.tokens,
            hallucination_flag: event.hallucination_flag,
          });
          break;
        }

        case 'error': {
          const msgId = useChatStore.getState().streamingMessageId;
          if (msgId) {
            finaliseMessage(sessionId, msgId, {
              content: event.message || 'An error occurred while processing your request.',
              isStreaming: false,
            });
          }
          setStreamingStatus('error');
          setStreamingMessageId(null);
          resetPipeline();
          break;
        }

        case 'done': {
          const store = useChatStore.getState();
          const msgId = store.streamingMessageId;
          if (msgId) {
            const currentMsgs = store.messages[sessionId] ?? [];
            const astMsg = currentMsgs.find(m => m.id === msgId);
            if (astMsg && !astMsg.content) {
              finaliseMessage(sessionId, msgId, {
                content: 'No response received from the server. Please try again.',
                isStreaming: false,
              });
            } else if (astMsg && astMsg.isStreaming) {
              finaliseMessage(sessionId, msgId, {
                isStreaming: false,
              });
            }
          }
          setStreamingStatus('done');
          setStreamingMessageId(null);
          resetPipeline();
          break;
        }

        // connected, ping — no action needed
        default:
          break;
      }
    },
    [appendToken, finaliseMessage, setPipeline, setStreamingStatus, setStreamingMessageId, resetPipeline],
  );

  const { status: sseStatus, connectionId } = useSSE({
    onEvent: handleEvent,
    enabled: isAuthenticated,
  });

  const sendMessage = useCallback(
    async (message: string, category: string, sessionId?: string) => {
      // Read latest state directly to avoid stale closures from selector re-renders.
      const store = useChatStore.getState();
      const targetSessionId = sessionId ?? store.activeSessionId;
      if (!targetSessionId) return;
      if (store.streamingStatus === 'streaming') return;

      // 1. Add user message immediately under the current (frontend) session key.
      addMessage(targetSessionId, {
        id: uuid(),
        role: 'user',
        content: message,
        createdAt: new Date(),
      });

      // 2. Create streaming placeholder for assistant.
      const assistantMsgId = uuid();
      addMessage(targetSessionId, {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        isStreaming: true,
        createdAt: new Date(),
      });
      setStreamingMessageId(assistantMsgId);
      setStreamingStatus('streaming');

      // 3. Submit to backend. Backend always returns the real DB session_id.
      //    We send session_id=undefined for brand-new local sessions so the
      //    backend creates a proper one.
      try {
        const isPersistedSession = store.sessions.some(s => s.id === targetSessionId && !s.isLocal);
        const res = await chatApi.submit({
          session_id: isPersistedSession ? targetSessionId : undefined,
          category,
          message,
        });

        const backendSessionId: string = res.session_id;

        if (backendSessionId && backendSessionId !== targetSessionId) {
          // Backend created/returned a real session ID.
          // Atomically migrate messages and session so SSE tokens land correctly.
          useChatStore.getState().migrateSession(targetSessionId, backendSessionId, category);
        }
      } catch (err) {
        setStreamingStatus('error');
        setStreamingMessageId(null);
        finaliseMessage(targetSessionId, assistantMsgId, {
          content: 'Failed to send message. Please try again.',
          isStreaming: false,
        });
        resetPipeline();
        throw err;
      }
    },
    [addMessage, setStreamingMessageId, setStreamingStatus, finaliseMessage, resetPipeline],
  );

  return {
    sseStatus,
    connectionId,
    streamingStatus,
    sendMessage,
  };
}
