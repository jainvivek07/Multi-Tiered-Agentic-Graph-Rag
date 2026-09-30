/**
 * useSSE — Core Server-Sent Events reader hook.
 *
 * Responsibilities:
 * • Opens GET /api/v1/stream/connect via fetch (credentials: include).
 * • Reads the response body as a ReadableStream, decoding SSE lines.
 * • Dispatches parsed, typed SSEEvent objects to `onEvent`.
 * • Sends keepalive pings as no-ops (filtered here).
 * • Reconnects with exponential back-off on network errors (max 3 attempts).
 * • Cleans up AbortController + reader on unmount or when `enabled` becomes false.
 * • Exposes { status, connectionId } for the UI to react to.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { chatApi } from '../api/chatApi';
import type { SSEEvent } from '../types/api';

export type SSEStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'error' | 'closed';

interface UseSSEOptions {
  onEvent: (event: SSEEvent) => void;
  enabled?: boolean;
}

interface UseSSEResult {
  status: SSEStatus;
  connectionId: string | null;
}

const MAX_RETRIES = 3;
const BACKOFF_BASE_MS = 1000;

export function useSSE({ onEvent, enabled = true }: UseSSEOptions): UseSSEResult {
  const [status, setStatus] = useState<SSEStatus>('idle');
  const [connectionId, setConnectionId] = useState<string | null>(null);

  // Stable ref so the reconnect loop doesn't capture stale `onEvent`.
  const onEventRef = useRef(onEvent);
  useEffect(() => { onEventRef.current = onEvent; }, [onEvent]);

  const abortRef = useRef<AbortController | null>(null);
  const retryRef = useRef(0);

  const connect = useCallback(async () => {
    if (!enabled) return;

    // Cancel any previous connection.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus('connecting');

    try {
      const res = await chatApi.openStream();

      if (!res.body) {
        throw new Error('SSE response has no readable body');
      }

      retryRef.current = 0;
      setStatus('open');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // eslint-disable-next-line no-constant-condition
      while (true) {
        if (controller.signal.aborted) break;

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE messages are delimited by double newline.
        const messages = buffer.split('\n\n');
        buffer = messages.pop() ?? '';  // last chunk may be incomplete

        for (const rawMsg of messages) {
          if (!rawMsg.trim()) continue;

          let dataLine = '';

          for (const line of rawMsg.split('\n')) {
            if (line.startsWith('data: '))  dataLine  = line.slice(6).trim();
          }

          if (!dataLine) continue;

          try {
            const parsed = JSON.parse(dataLine) as SSEEvent;

            // Capture connection id from the first connected event.
            if (parsed.event === 'connected') {
              setConnectionId(parsed.connection_id);
            }

            // Skip keepalive pings — no need to surface them to consumers.
            if (parsed.event === 'ping') continue;

            onEventRef.current(parsed);

            if (parsed.event === 'done') {
              // Instead of closing permanently, just break out to let the stream reset naturally
              // or let the consumer handle the 'done' event.
              // Wait, the backend explicitly closes the connection by terminating the generator 
              // after yielding the DoneEvent. So the reader will hit `done: true` next anyway.
              // We don't need to manually cancel and return here!
            }
          } catch {
            // Malformed JSON — log and skip.
            console.warn('[useSSE] Failed to parse event:', dataLine);
          }
        }
      }

      if (!controller.signal.aborted) {
        retryRef.current += 1;
        if (retryRef.current <= MAX_RETRIES) {
          const delay = BACKOFF_BASE_MS * 2 ** (retryRef.current - 1);
          setStatus('reconnecting');
          setTimeout(() => {
            if (!controller.signal.aborted) {
              connect();
            }
          }, delay);
        } else {
          setStatus('closed');
        }
      }
    } catch (err) {
      if (controller.signal.aborted) return;

      console.error('[useSSE] Connection error:', err);
      retryRef.current += 1;

      if (retryRef.current <= MAX_RETRIES) {
        const delay = BACKOFF_BASE_MS * 2 ** (retryRef.current - 1);
        setStatus('reconnecting');
        setTimeout(connect, delay);
      } else {
        setStatus('error');
      }
    }
  }, [enabled]);

  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      abortRef.current?.abort();
      setStatus('idle');
      setConnectionId(null);
      retryRef.current = 0;
    }

    return () => {
      abortRef.current?.abort();
    };
  }, [enabled, connect]);

  return { status, connectionId };
}
