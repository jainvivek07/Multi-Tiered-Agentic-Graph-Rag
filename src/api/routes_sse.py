"""
SSE streaming endpoints.

Two-endpoint split pattern:
  GET  /api/v1/stream/connect   — opens the SSE stream (long-lived GET).
  POST /api/v1/stream/submit    — submits a chat request; pipeline runs in a
                                  background asyncio.Task and publishes events
                                  through the SSE manager.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.dependencies import get_current_user
from src.core.config import settings
from src.core.limiter import limiter
from src.core.logger import log
from src.core.sse_manager import sse_manager
from src.infra.postgres import get_db_session
from src.models.api import CurrentUser
from src.models.sql import ChatMessage
from src.models.sse import DoneEvent, ErrorEvent, MetaEvent, PingEvent, ConnectedEvent, TokenDeltaEvent
from src.repositories.chat_repo import ChatRepository
from src.services.retrieval.graph import run_pipeline_streaming
from src.services.guardrails.input_guard import check_input

router = APIRouter()


# ─── Request schema ───────────────────────────────────────────────────────────

class StreamSubmitRequest(BaseModel):
    session_id: Optional[uuid.UUID] = None
    category: str = Field(..., description="Category to restrict the search space")
    message: str = Field(..., min_length=1, max_length=4096, description="The user's query")


# ─── GET /connect ─────────────────────────────────────────────────────────────

@router.get(
    "/connect",
    summary="Open SSE stream",
    response_class=StreamingResponse,
    responses={
        200: {"description": "text/event-stream — long-lived SSE connection"},
        401: {"description": "Not authenticated"},
    },
)
async def connect(
    user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """
    Opens a Server-Sent Events stream for the authenticated user.
    The connection stays open until the client disconnects or the server
    sends a `done` event.  Keepalive `ping` events are sent every
    `SSE_KEEPALIVE_INTERVAL` seconds to prevent proxy timeouts.
    """
    user_id = str(user.id)
    connection_id, queue = await sse_manager.connect(user_id)

    async def event_generator():
        try:
            # Acknowledge connection immediately.
            yield ConnectedEvent(
                user_id=user_id,
                connection_id=connection_id,
            ).to_wire()

            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=settings.SSE_KEEPALIVE_INTERVAL,
                    )
                    yield event.to_wire()
                except asyncio.TimeoutError:
                    yield PingEvent().to_wire()

        except asyncio.CancelledError:
            log.info("sse_client_disconnected", user_id=user_id, connection_id=connection_id)
            raise
        finally:
            await sse_manager.disconnect(user_id, connection_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── POST /submit ─────────────────────────────────────────────────────────────

@router.post(
    "/submit",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a chat message for streaming",
    responses={
        202: {"description": "Pipeline task queued — events will arrive on the SSE stream"},
        400: {"description": "Input validation failed or guardrail blocked"},
        401: {"description": "Not authenticated"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def submit(
    request: Request,
    response: Response,
    body: StreamSubmitRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Validates the request, sets up the chat session, persists the user message,
    then dispatches `_run_streaming_pipeline` as a background asyncio.Task.
    Returns 202 immediately — results arrive via the SSE stream.
    """
    user_id = str(user.id)

    # ── Input guardrail (fast — runs before the pipeline task) ───────────────
    is_safe, reason = await check_input(body.message)
    if not is_safe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    # ── Session management ────────────────────────────────────────────────────
    chat_repo = ChatRepository(session)

    if body.session_id:
        try:
            chat_session = await chat_repo.get_session(body.session_id)
            if not chat_session or chat_session.user_id != user.id:
                # Session not found or belongs to another user — fallback to new session
                log.warning(f"Session {body.session_id} not found, creating new session.")
                chat_session = await chat_repo.create_session(user_id=user.id, category=body.category)
        except Exception:
            # Invalid UUID format, fallback to new session
            chat_session = await chat_repo.create_session(user_id=user.id, category=body.category)
    else:
        chat_session = await chat_repo.create_session(user_id=user.id, category=body.category)

    # ── Sliding window memory ─────────────────────────────────────────────────
    recent_messages = await chat_repo.get_recent_messages(
        session_id=chat_session.id,
        limit=settings.CHAT_HISTORY_WINDOW_SIZE,
    )
    chat_history = [{"role": m.role, "content": m.content} for m in recent_messages]

    # ── Persist the user message before dispatching ───────────────────────────
    await chat_repo.add_message(ChatMessage(
        session_id=chat_session.id,
        role="user",
        content=body.message,
    ))

    session_id_str = str(chat_session.id)

    # ── Dispatch pipeline as a fire-and-forget asyncio.Task ──────────────────
    asyncio.create_task(
        _run_streaming_pipeline(
            user_id=user_id,
            session_id=session_id_str,
            query=body.message,
            category=body.category,
            chat_history=chat_history,
        ),
        name=f"pipeline:{user_id}:{session_id_str}",
    )

    return {"session_id": session_id_str, "status": "queued"}


# ─── Background pipeline task ─────────────────────────────────────────────────

async def _run_streaming_pipeline(
    user_id: str,
    session_id: str,
    query: str,
    category: str,
    chat_history: list[dict],
) -> None:
    """
    Runs inside an asyncio.Task.  All exceptions are caught so a failing
    pipeline cannot crash the event loop — instead an ErrorEvent is published
    so the client knows something went wrong.

    Persistence (assistant message write) happens here after the stream
    closes, keeping the HTTP submit handler fast.
    """
    start = time.monotonic()

    async def cb(event):
        await sse_manager.publish(user_id, event)

    try:
        final_state = await run_pipeline_streaming(
            query=query,
            category=category,
            chat_history=chat_history,
            progress_cb=cb,
        )

        usage = final_state.get("usage", {})
        citations_raw = final_state.get("citations", [])
        citations_dicts = [
            c.model_dump() if hasattr(c, "model_dump") else (c if isinstance(c, dict) else {})
            for c in citations_raw
        ]

        # ── If cache hit, no tokens were streamed — emit the answer now ───────
        if final_state.get("route") == "cache_hit":
            cached_answer = final_state.get("final_answer", "")
            if cached_answer:
                await sse_manager.publish(user_id, TokenDeltaEvent(delta=cached_answer))

        # ── Emit final metadata ───────────────────────────────────────────────
        await sse_manager.publish(user_id, MetaEvent(
            session_id=session_id,
            route_taken=final_state.get("route", "unknown"),
            latency_ms=int((time.monotonic() - start) * 1000),
            citations=citations_dicts,
            tokens={
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            },
            hallucination_flag=final_state.get("hallucination_flag", False),
            guard_passed=True,
        ))

        # ── Persist assistant message (non-blocking, after stream) ────────────
        try:
            from src.infra.postgres import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                repo = ChatRepository(db)
                await repo.add_message(ChatMessage(
                    session_id=uuid.UUID(session_id),
                    role="assistant",
                    content=final_state.get("final_answer", ""),
                    route_taken=final_state.get("route"),
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    latency_ms=final_state.get("latency_ms"),
                ))
        except Exception as db_exc:
            log.error("pipeline_persist_failed", session_id=session_id, error=str(db_exc))

    except Exception as exc:
        log.error("pipeline_task_failed", user_id=user_id, session_id=session_id, error=str(exc))
        await sse_manager.publish(user_id, ErrorEvent(
            code="PIPELINE_FAILED",
            message="An error occurred while processing your request.",
        ))
    finally:
        await sse_manager.publish(user_id, DoneEvent())
