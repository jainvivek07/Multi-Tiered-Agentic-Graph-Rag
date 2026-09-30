from __future__ import annotations

import json
import time
from typing import Any, Literal, Optional
from pydantic import BaseModel

class _BaseSSEEvent(BaseModel):
    """Serialises to the SSE wire format: 'event: <type>\\ndata: <json>\\n\\n'."""

    event: str

    def to_wire(self) -> str:
        return f"event: {self.event}\ndata: {self.model_dump_json()}\n\n"


class ConnectedEvent(_BaseSSEEvent):
    """Sent once immediately after the SSE connection is accepted."""
    event: Literal["connected"] = "connected"
    user_id: str
    connection_id: str
    ts: float = 0.0

    def model_post_init(self, __context: Any) -> None:
        if self.ts == 0.0:
            object.__setattr__(self, "ts", time.time())


class PingEvent(_BaseSSEEvent):
    """Keep-alive heartbeat, emitted every `SSE_KEEPALIVE_INTERVAL` seconds."""
    event: Literal["ping"] = "ping"
    ts: float = 0.0

    def model_post_init(self, __context: Any) -> None:
        if self.ts == 0.0:
            object.__setattr__(self, "ts", time.time())


class PipelineStepEvent(_BaseSSEEvent):
    """
    Emitted at the start of each LangGraph node.
    `route` is populated only after the router resolves.
    """
    event: Literal["pipeline_step"] = "pipeline_step"
    step: Literal["cache_check", "input_guard", "router", "vector_search", "cypher_search", "output_guard", "synthesizer"]
    detail: str
    route: Optional[str] = None


class TokenDeltaEvent(_BaseSSEEvent):
    """
    One streamed token chunk from the synthesis LLM.
    Frontend accumulates these to build the final answer.
    """
    event: Literal["token"] = "token"
    delta: str


class MetaEvent(_BaseSSEEvent):
    """
    Final metadata sent after the last token.
    Contains session, citations, token usage, latency, and guard flags.
    """
    event: Literal["meta"] = "meta"
    session_id: str
    route_taken: str
    latency_ms: int
    citations: list[dict]
    tokens: dict  # {"prompt": int, "completion": int, "total": int}
    hallucination_flag: bool
    guard_passed: bool


class ErrorEvent(_BaseSSEEvent):
    """Emitted on pipeline errors.  `code` maps to frontend error handling."""
    event: Literal["error"] = "error"
    code: str   # e.g. "RATE_LIMITED", "INPUT_BLOCKED", "PIPELINE_FAILED"
    message: str


class DoneEvent(_BaseSSEEvent):
    """Signals the client the stream for this request is complete."""
    event: Literal["done"] = "done"


SSEEvent = (
    ConnectedEvent
    | PingEvent
    | PipelineStepEvent
    | TokenDeltaEvent
    | MetaEvent
    | ErrorEvent
    | DoneEvent
)
