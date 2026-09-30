import time
import uuid
from starlette.requests import Request
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.postgres import get_db_session
from src.api.dependencies import get_current_user
from src.models.sql import ChatSession, ChatMessage
from src.models.api import ChatRequest, ChatResponse, CurrentUser
from src.repositories.chat_repo import ChatRepository
from src.services.retrieval.graph import run_pipeline
from src.services.guardrails.input_guard import check_input
from src.services.guardrails.output_guard import check_output
from src.core.logger import log
from src.core.config import settings
from src.core.limiter import limiter
from src.infra.neo4j import neo4j_reader_manager
from typing import List

router = APIRouter()

@router.get("/categories")
async def get_categories() -> List[str]:
    """Fetches all distinct categories from Neo4j Chunk nodes."""
    try:
        driver = await neo4j_reader_manager.get_driver()
        async with driver.session() as session:
            result = await session.run("MATCH (c:Chunk) RETURN DISTINCT c.category AS category")
            categories = [record["category"] for record in await result.data() if record["category"]]
        return sorted(list(set(categories)))
    except Exception as e:
        log.error("failed_to_fetch_categories", error=str(e))
        return []

@router.get("/sessions")
async def get_sessions(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Fetches all chat sessions for the current user."""
    chat_repo = ChatRepository(session)
    sessions = await chat_repo.get_user_sessions(user.id)
    return [
        {
            "id": str(s.id),
            "category": s.category,
            "created_at": s.created_at.isoformat() if s.created_at else None
        }
        for s in sessions
    ]

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Fetches all messages for a specific session."""
    chat_repo = ChatRepository(db_session)
    chat_session = await chat_repo.get_session(session_id)
    if not chat_session or chat_session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    
    messages = await chat_repo.get_session_messages(session_id)
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "route_taken": m.route_taken,
            "latency_ms": m.latency_ms,
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
        for m in messages
    ]


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat(
    request: Request,
    response: Response,
    chat_data: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Main RAG query endpoint.
    Flow: Input Guard → Tier 0 Cache → LangGraph Pipeline → Output Guard → Persist → Return
    """
    # Input guardrail
    is_safe, reason = await check_input(chat_data.message)
    if not is_safe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    chat_repo = ChatRepository(session)

    # Session management
    if chat_data.session_id:
        chat_session = await chat_repo.get_session(chat_data.session_id)
        if not chat_session or chat_session.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    else:
        chat_session = await chat_repo.create_session(user_id=user.id, category=chat_data.category)

    # Sliding window memory
    recent_messages = await chat_repo.get_recent_messages(
        session_id=chat_session.id,
        limit=5,
    )
    chat_history = [{"role": m.role, "content": m.content} for m in recent_messages]

    # Persist the user message
    await chat_repo.add_message(ChatMessage(
        session_id=chat_session.id,
        role="user",
        content=chat_data.message,
    ))

    # Run the full LangGraph pipeline
    start = time.monotonic()
    result = await run_pipeline(
        query=chat_data.message,
        category=chat_data.category,
        chat_history=chat_history,
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    final_answer = result.get("final_answer", "")
    citations = result.get("citations", [])
    route_taken = result.get("route", "unknown")

    # Output hallucination guard — skip for cache hits (answer was verified at write time;
    # running it again with no retrieved_context always produces a false positive).
    if route_taken != "cache_hit":
        is_flagged, flag_reason = await check_output(final_answer, result.get("retrieved_context", []), chat_data.message)
        if is_flagged:
            log.warning("Output flagged by hallucination guard", reason=flag_reason, session=str(chat_session.id))

    # Extract token usage from LiteLLM response if available
    usage = result.get("usage", {})

    # Persist assistant message with metrics
    await chat_repo.add_message(ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content=final_answer,
        route_taken=route_taken,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
        latency_ms=latency_ms,
    ))

    return ChatResponse(
        session_id=chat_session.id,
        answer=final_answer,
        citations=citations,
        route_taken=route_taken,
        latency_ms=latency_ms,
    )
