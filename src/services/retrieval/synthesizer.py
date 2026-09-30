from __future__ import annotations

from typing import Callable, Awaitable

from src.infra.llm import call_llm, call_llm_streaming, get_synthesis_llm_kwargs
from src.models.api import Citation
from src.core.logger import log
from src.core.prompts import SYNTHESIS_SYSTEM_PROMPT

_NO_CONTEXT_REPLY = "I could not find relevant information in the knowledge base for your query."


def _build_messages(
    query: str,
    context_chunks: list[dict],
    chat_history: list[dict],
) -> tuple[list[dict], list[Citation]]:
    """Shared message-building logic for both batch and streaming variants."""
    if not context_chunks:
        return [], []

    context_text = "\n\n".join(
        f"[{i + 1}] (type={chunk.get('source_type', 'document_chunk')}) {chunk.get('content', str(chunk))}"
        for i, chunk in enumerate(context_chunks)
    )

    messages: list[dict] = [{"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT}]

    if chat_history:
        history_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in chat_history)
        messages.append({"role": "user", "content": f"Conversation so far:\n{history_text}"})

    messages.append({
        "role": "user",
        "content": f"Context:\n{context_text}\n\nQuestion: {query}",
    })

    citations = [
        Citation(
            source_type=chunk.get("source_type", "document_chunk"),
            content=str(chunk.get("content", chunk))[:300],
            metadata={k: v for k, v in chunk.items() if k not in ("content", "source_type")},
        )
        for chunk in context_chunks
    ]

    return messages, citations

async def synthesize_answer(
    query: str,
    context_chunks: list[dict],
    chat_history: list[dict],
) -> tuple[str, list[Citation], dict]:
    """
    Tier 3 Synthesis (batch).
    Combines retrieved vector/graph context to produce a cited natural language answer.
    Returns (final_answer, citations, usage).
    """
    messages, citations = _build_messages(query, context_chunks, chat_history)
    if not messages:
        return _NO_CONTEXT_REPLY, [], {}

    llm_kwargs = get_synthesis_llm_kwargs()
    log.info("synthesizer_batch_start", context_chunks=len(context_chunks))

    response = await call_llm(messages=messages, llm_kwargs=llm_kwargs)
    answer_text = response.choices[0].message.content
    usage = response.usage.model_dump() if response.usage else {}

    return answer_text, citations, usage


async def synthesize_answer_streaming(
    query: str,
    context_chunks: list[dict],
    chat_history: list[dict],
    on_token: Callable[[str], Awaitable[None]],
) -> tuple[str, list[Citation], dict]:
    """
    Tier 3 Synthesis (streaming).
    Identical to synthesize_answer() but forwards each token delta to `on_token`
    as it arrives.  Used by the SSE pipeline path.
    Returns (full_answer, citations, usage) after the stream closes.
    """
    messages, citations = _build_messages(query, context_chunks, chat_history)
    if not messages:
        # No context — send the fallback reply as a single "token" so the client
        # still gets it through the streaming channel.
        await on_token(_NO_CONTEXT_REPLY)
        return _NO_CONTEXT_REPLY, [], {}

    llm_kwargs = get_synthesis_llm_kwargs()
    log.info("synthesizer_stream_start", context_chunks=len(context_chunks))

    full_text, usage = await call_llm_streaming(
        messages=messages,
        llm_kwargs=llm_kwargs,
        on_token=on_token,
    )

    return full_text, citations, usage
