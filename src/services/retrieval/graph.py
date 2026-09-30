
from __future__ import annotations

import json
import time
import uuid
import numpy as np
from typing import Callable, Awaitable, Literal

from langgraph.graph import StateGraph, END

from src.models.state import GraphState
from src.models.sse import (
    PipelineStepEvent,
    TokenDeltaEvent,
    SSEEvent,
)
from src.core.config import settings
from src.core.logger import log
from src.infra.redis import redis_manager, redis_binary_manager, SEMANTIC_CACHE_INDEX, SEMANTIC_CACHE_PREFIX
from src.infra.embeddings import embed_texts_local
from src.services.retrieval.router import route_query
from src.services.retrieval.vector import hybrid_vector_search
from src.services.retrieval.cypher import generate_and_execute_cypher
from src.services.retrieval.synthesizer import synthesize_answer, synthesize_answer_streaming
from src.services.guardrails.input_guard import check_input
from src.services.guardrails.output_guard import check_output

ProgressCallback = Callable[[SSEEvent], Awaitable[None]]

async def node_router(state: GraphState) -> dict:
    output, usage = await route_query(state["original_query"], state["chat_history"])
    return {
        "rewritten_query": output.rewritten_query,
        "route": output.intent,
        "usage": usage,
    }


async def node_vector_search(state: GraphState) -> dict:
    results = await hybrid_vector_search(
        query=state["rewritten_query"] or state["original_query"],
        category=state["category"],
    )
    return {"retrieved_context": [{"source_type": "document_chunk", **r} for r in results]}


async def node_cypher_search(state: GraphState) -> dict:
    error_context = state["cypher_errors"][-1] if state["cypher_errors"] else None
    try:
        results, usage = await generate_and_execute_cypher(
            query=state["rewritten_query"] or state["original_query"],
            category=state["category"],
            error_context=error_context,
        )
        return {
            "retrieved_context": [{"source_type": "graph_node", **r} for r in results],
            "usage": usage,
        }
    except Exception as exc:
        log.warning("Cypher execution failed", error=str(exc))
        return {"cypher_errors": [str(exc)]}


async def node_synthesizer(state: GraphState) -> dict:
    answer, citations, usage = await synthesize_answer(
        query=state["rewritten_query"] or state["original_query"],
        context_chunks=state["retrieved_context"],
        chat_history=state["chat_history"],
    )
    return {"final_answer": answer, "citations": citations, "usage": usage}


def decide_after_router(state: GraphState) -> list[str]:
    route = state.get("route", "vector")
    if route == "hybrid":
        return ["vector_search", "cypher_search"]
    elif route == "graph":
        return ["cypher_search"]
    return ["vector_search"]


def decide_after_cypher(state: GraphState) -> Literal["cypher_search", "synthesizer"]:
    errors = state.get("cypher_errors", [])
    if errors and len(errors) < settings.CYPHER_MAX_RETRIES:
        log.info("Self-healing Cypher", attempt=len(errors))
        return "cypher_search"
    return "synthesizer"

def build_retrieval_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("router", node_router)
    graph.add_node("vector_search", node_vector_search)
    graph.add_node("cypher_search", node_cypher_search)
    graph.add_node("synthesizer", node_synthesizer)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        decide_after_router,
        ["vector_search", "cypher_search"],
    )

    graph.add_edge("vector_search", "synthesizer")

    graph.add_conditional_edges(
        "cypher_search",
        decide_after_cypher,
        {"cypher_search": "cypher_search", "synthesizer": "synthesizer"},
    )

    graph.add_edge("synthesizer", END)

    return graph.compile()


_compiled_graph = build_retrieval_graph()


async def _semantic_cache_lookup(
    query_embedding: list[float],
    category: str,
) -> dict | None:
    
    client = await redis_binary_manager.get_client()
    emb_bytes = np.array(query_embedding, dtype=np.float32).tobytes()
    distance_threshold = 1.0 - settings.SEMANTIC_CACHE_THRESHOLD

    query_str = f"@category:{{{category}}} @embedding:[VECTOR_RANGE $distance_threshold $vec]=>{{$YIELD_DISTANCE_AS: __score}}"

    try:
        results = await client.execute_command(
            "FT.SEARCH", SEMANTIC_CACHE_INDEX,
            query_str,
            "PARAMS", "4", "vec", emb_bytes, "distance_threshold", str(distance_threshold),
            "RETURN", "3", "__score", "answer", "citations",
            "SORTBY", "__score",
            "DIALECT", "2",
            "LIMIT", "0", "1",
        )
    except Exception as exc:
        log.warning("Semantic cache lookup failed — proceeding without cache", error=str(exc))
        return None

    field_map: dict[str, str] = {}

    if isinstance(results, dict):
        total = results.get(b"total_results", 0)
        if not total:
            return None
        docs = results.get(b"results", [])
        if not docs:
            return None
        attrs = docs[0].get(b"extra_attributes", {})
        for k, v in attrs.items():
            field_map[k.decode() if isinstance(k, bytes) else k] = (
                v.decode() if isinstance(v, bytes) else v
            )
    else:
        if not results or results[0] == 0:
            return None
        fields = results[2]
        for i in range(0, len(fields) - 1, 2):
            k = fields[i].decode() if isinstance(fields[i], bytes) else fields[i]
            v = fields[i + 1].decode() if isinstance(fields[i + 1], bytes) else fields[i + 1]
            field_map[k] = v

    score_raw = field_map.get("__score")
    if score_raw is None:
        return None

    distance = float(score_raw)
    similarity = 1.0 - distance

    log.info("Semantic cache probe", similarity=round(similarity, 4), threshold=settings.SEMANTIC_CACHE_THRESHOLD)

    if similarity >= settings.SEMANTIC_CACHE_THRESHOLD:
        log.info("Semantic cache HIT", similarity=round(similarity, 4))
        return {
            "final_answer": field_map.get("answer", ""),
            "citations": json.loads(field_map.get("citations", "[]")),
        }

    return None


async def _semantic_cache_write(
    query_embedding: list[float],
    category: str,
    final_answer: str,
    citations: list,
) -> None:
    """Stores the query embedding + answer into the Redis vector index."""
    client = await redis_binary_manager.get_client()
    entry_id = f"{SEMANTIC_CACHE_PREFIX}{uuid.uuid4().hex}"
    emb_bytes = np.array(query_embedding, dtype=np.float32).tobytes()

    citations_json = json.dumps([c.model_dump() if hasattr(c, "model_dump") else c for c in citations])

    try:
        await client.hset(entry_id, mapping={
            b"category": category.encode(),
            b"embedding": emb_bytes,
            b"answer": final_answer.encode(),
            b"citations": citations_json.encode(),
        })
        await client.expire(entry_id, 3600)  # 1-hour TTL
        log.info("Semantic cache entry written", entry_id=entry_id)
    except Exception as exc:
        log.warning("Semantic cache write failed — non-fatal", error=str(exc))


async def _run_pre_graph(
    query: str,
    category: str,
    chat_history: list[dict],
    cb: ProgressCallback | None,
) -> dict | None:
    """
    Tiers 0–1: semantic cache check and NeMo input guardrail.
    Returns a short-circuit result dict if either fires, otherwise None.
    """
    if not chat_history:
        if cb:
            await cb(PipelineStepEvent(step="cache_check", detail="Checking semantic cache..."))
        query_embedding = (await embed_texts_local([query]))[0]
        cached = await _semantic_cache_lookup(query_embedding, category)
        if cached:
            if cb:
                await cb(PipelineStepEvent(step="cache_check", detail="Cache hit — returning cached answer.", route="cache_hit"))
            return {"route": "cache_hit", "_embedding": query_embedding, **cached}

    # ── Tier-1: NeMo Input Guardrails ────────────────────────────────────────
    if cb:
        await cb(PipelineStepEvent(step="input_guard", detail="Running input guardrails..."))
    is_safe, reason = await check_input(query)
    if not is_safe:
        log.warning("Query blocked by input guardrails", reason=reason[:200])
        return {
            "route": "blocked_by_guardrails",
            "final_answer": reason,
            "citations": [],
            "hallucination_flag": False,
        }

    return None


async def _run_post_graph(
    final_state: dict,
    query: str,
    chat_history: list[dict],
    query_embedding: list[float] | None,
    cb: ProgressCallback | None,
) -> dict:
    """
    Tiers 3–4: LettuceDetect output guard and semantic cache write.
    Mutates and returns final_state.
    """
    answer = final_state.get("final_answer", "")
    context = final_state.get("retrieved_context", [])

    if cb:
        await cb(PipelineStepEvent(step="output_guard", detail="Checking answer quality..."))

    is_hallucinated, detail = await check_output(answer, context, query)
    if is_hallucinated:
        log.warning("Hallucination detected — regenerating answer once", detail=detail)
        regen = await node_synthesizer(final_state)
        final_state["final_answer"] = regen.get("final_answer", answer)
        final_state["citations"] = regen.get("citations", final_state.get("citations", []))
        final_state["hallucination_flag"] = True
        log.info("One-shot regeneration complete", hallucination_flag=True)

    # ── Tier-4: Semantic Cache Write ──────────────────────────────────────────
    if not chat_history and final_state.get("final_answer"):
        emb = query_embedding or (await embed_texts_local([query]))[0]
        await _semantic_cache_write(
            query_embedding=emb,
            category=final_state.get("category", ""),
            final_answer=final_state["final_answer"],
            citations=final_state.get("citations", []),
        )

    return final_state

async def run_pipeline(query: str, category: str, chat_history: list[dict]) -> dict:
    """
    Full runtime pipeline (batch — unchanged contract).

    [Tier-0] Semantic cache (Redis KNN, similarity > threshold) — bypassed for conversations.
    [Tier-1] NeMo Guardrails input check — blocks off-topic / jailbreak queries.
    [Tier-2] LangGraph retrieval (Router → Vector/Cypher → Synthesizer).
    [Tier-3] LettuceDetect output check — one-shot regeneration on hallucination.
    [Tier-4] Semantic cache write — stores successful answers for future lookups.
    """
    query_embedding: list[float] | None = None

    short_circuit = await _run_pre_graph(query, category, chat_history, cb=None)
    if short_circuit:
        query_embedding = short_circuit.pop("_embedding", None)
        return short_circuit

    start = time.monotonic()
    initial_state: GraphState = {
        "original_query": query,
        "rewritten_query": None,
        "category": category,
        "chat_history": chat_history,
        "route": None,
        "cypher_query": None,
        "cypher_errors": [],
        "retrieved_context": [],
        "final_answer": None,
        "citations": [],
        "hallucination_flag": False,
        "usage": {},
    }

    final_state = await _compiled_graph.ainvoke(initial_state)
    final_state["latency_ms"] = int((time.monotonic() - start) * 1000)

    final_state = await _run_post_graph(final_state, query, chat_history, query_embedding, cb=None)

    log.info(
        "pipeline_complete",
        route=final_state.get("route"),
        latency_ms=final_state["latency_ms"],
        hallucination_flag=final_state.get("hallucination_flag", False),
    )
    return final_state


async def run_pipeline_streaming(
    query: str,
    category: str,
    chat_history: list[dict],
    progress_cb: ProgressCallback,
) -> dict:
    """
    Full runtime pipeline (SSE streaming path).
    """
    query_embedding: list[float] | None = None

    short_circuit = await _run_pre_graph(query, category, chat_history, cb=progress_cb)
    if short_circuit:
        query_embedding = short_circuit.pop("_embedding", None)
        return short_circuit

    start = time.monotonic()

    # ── Tier-2: LangGraph Retrieval (with per-node progress events) ───────────
    await progress_cb(PipelineStepEvent(step="router", detail="Classifying query intent..."))
    query_text = query

    # Run router node manually to get route before the rest of the graph.
    router_state: GraphState = {
        "original_query": query,
        "rewritten_query": None,
        "category": category,
        "chat_history": chat_history,
        "route": None,
        "cypher_query": None,
        "cypher_errors": [],
        "retrieved_context": [],
        "final_answer": None,
        "citations": [],
        "hallucination_flag": False,
        "usage": {},
    }
    router_out = await node_router(router_state)
    route = router_out.get("route", "vector")
    rewritten_query = router_out.get("rewritten_query") or query

    await progress_cb(PipelineStepEvent(
        step="router",
        detail=f"Route resolved: {route}",
        route=route,
    ))

    # Retrieval nodes — run in parallel for hybrid (mirrors the compiled graph).
    retrieval_ctx: list = []
    usage: dict = router_out.get("usage", {})
    cypher_errors: list[str] = []

    if route in ("vector", "hybrid"):
        await progress_cb(PipelineStepEvent(step="vector_search", detail="Searching embedding space..."))
        vec_results = await hybrid_vector_search(query=rewritten_query, category=category)
        retrieval_ctx.extend([{"source_type": "document_chunk", **r} for r in vec_results])

    if route in ("graph", "hybrid"):
        await progress_cb(PipelineStepEvent(step="cypher_search", detail="Traversing knowledge graph..."))
        for attempt in range(settings.CYPHER_MAX_RETRIES):
            error_ctx = cypher_errors[-1] if cypher_errors else None
            try:
                graph_results, g_usage = await generate_and_execute_cypher(
                    query=rewritten_query,
                    category=category,
                    error_context=error_ctx,
                )
                retrieval_ctx.extend([{"source_type": "graph_node", **r} for r in graph_results])
                # Merge usage
                for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    usage[k] = usage.get(k, 0) + g_usage.get(k, 0)
                break
            except Exception as exc:
                cypher_errors.append(str(exc))
                log.warning("Cypher attempt failed", attempt=attempt + 1, error=str(exc))
                if attempt == settings.CYPHER_MAX_RETRIES - 1:
                    log.error("Cypher max retries exceeded", cypher_errors=cypher_errors)

    # ── Synthesizer (streaming) ────────────────────────────────────────────────
    await progress_cb(PipelineStepEvent(step="synthesizer", detail="Generating answer..."))

    async def _on_token(delta: str) -> None:
        await progress_cb(TokenDeltaEvent(delta=delta))

    final_answer, citations, synth_usage = await synthesize_answer_streaming(
        query=rewritten_query,
        context_chunks=retrieval_ctx,
        chat_history=chat_history,
        on_token=_on_token,
    )
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        usage[k] = usage.get(k, 0) + synth_usage.get(k, 0)

    final_state: dict = {
        "original_query": query,
        "rewritten_query": rewritten_query,
        "category": category,
        "chat_history": chat_history,
        "route": route,
        "cypher_query": None,
        "cypher_errors": cypher_errors,
        "retrieved_context": retrieval_ctx,
        "final_answer": final_answer,
        "citations": citations,
        "hallucination_flag": False,
        "usage": usage,
        "latency_ms": int((time.monotonic() - start) * 1000),
    }

    final_state = await _run_post_graph(final_state, query, chat_history, query_embedding, cb=progress_cb)

    log.info(
        "pipeline_streaming_complete",
        route=route,
        latency_ms=final_state["latency_ms"],
        hallucination_flag=final_state.get("hallucination_flag", False),
    )
    return final_state
