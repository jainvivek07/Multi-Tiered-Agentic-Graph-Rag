import { apiFetch, apiFetchRaw } from './client';
import type { StreamSubmitRequest, StreamSubmitResponse } from '../types/api';

const PREFIX = '/api/v1/stream';

export const chatApi = {
  /**
   * Opens the SSE stream.  Returns the raw Response so the caller can
   * attach a ReadableStream reader.
   */
  openStream: (): Promise<Response> =>
    apiFetchRaw(`${PREFIX}/connect`),

  /**
   * Submit a chat message.  Returns 202 immediately — pipeline events
   * arrive on the SSE stream opened via openStream().
   */
  submit: (req: StreamSubmitRequest): Promise<StreamSubmitResponse> =>
    apiFetch<StreamSubmitResponse>(`${PREFIX}/submit`, {
      method: 'POST',
      body: req,
    }),
};

export const sessionApi = {
  getSessions: () =>
    apiFetch<{ id: string; category: string; created_at: string }[]>(
      '/api/v1/user/sessions',
    ),

  getMessages: (sessionId: string) =>
    apiFetch<
      {
        id: string;
        role: string;
        content: string;
        route_taken?: string;
        latency_ms?: number;
        created_at: string;
      }[]
    >(`/api/v1/user/sessions/${sessionId}/messages`),

  getCategories: () =>
    apiFetch<string[]>('/api/v1/user/categories'),
};
