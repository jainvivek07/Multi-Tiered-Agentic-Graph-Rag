/* Mirrors backend Pydantic models exactly. */

export interface Token {
  access_token: string;
  token_type: string;
  refresh_token?: string;
}

export interface UserCreate {
  email: string;
  password: string;
}

export interface UserResponse {
  id: string;
  email: string;
  role: 'admin' | 'user';
  is_active: boolean;
}

export interface Citation {
  source_type: 'document_chunk' | 'graph_node';
  content: string;
  metadata: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  citations: Citation[];
  route_taken?: string;
  latency_ms?: number;
}

export interface StreamSubmitRequest {
  session_id?: string;
  category: string;
  message: string;
}

export interface StreamSubmitResponse {
  session_id: string;
  status: 'queued';
}

/* ── SSE Event types (discriminated union) ─────────────────────────────── */

export type PipelineStep =
  | 'cache_check'
  | 'input_guard'
  | 'router'
  | 'vector_search'
  | 'cypher_search'
  | 'output_guard'
  | 'synthesizer';

export interface SSEConnectedEvent {
  event: 'connected';
  user_id: string;
  connection_id: string;
  ts: number;
}

export interface SSEPingEvent {
  event: 'ping';
  ts: number;
}

export interface SSEPipelineStepEvent {
  event: 'pipeline_step';
  step: PipelineStep;
  detail: string;
  route?: string;
}

export interface SSETokenEvent {
  event: 'token';
  delta: string;
}

export interface SSEMetaEvent {
  event: 'meta';
  session_id: string;
  route_taken: string;
  latency_ms: number;
  citations: Citation[];
  tokens: { prompt: number; completion: number; total: number };
  hallucination_flag: boolean;
  guard_passed: boolean;
}

export interface SSEErrorEvent {
  event: 'error';
  code: string;
  message: string;
}

export interface SSEDoneEvent {
  event: 'done';
}

export type SSEEvent =
  | SSEConnectedEvent
  | SSEPingEvent
  | SSEPipelineStepEvent
  | SSETokenEvent
  | SSEMetaEvent
  | SSEErrorEvent
  | SSEDoneEvent;

/* ── Admin ──────────────────────────────────────────────────────────────── */

export interface DashboardMetrics {
  total_queries_processed: number;
  total_tokens_used: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  avg_latency_ms: number;
  cache_hit_rate: number;
  route_distribution: {
    vector: number;
    graph: number;
    hybrid: number;
    cache_hit: number;
  };
  active_users: number;
}

export interface Document {
  id: string;
  filename: string;
  category: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  has_file?: boolean;
}
