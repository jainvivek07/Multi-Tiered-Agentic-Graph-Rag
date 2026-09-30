from pydantic import BaseModel
from src.infra.llm import get_router_llm_kwargs, call_llm
from src.core.utils import parse_llm_json
from src.core.logger import log
from src.core.prompts import ROUTER_SYSTEM_PROMPT

class RouterOutput(BaseModel):
    rewritten_query: str
    intent: str  # 'vector' | 'graph' | 'hybrid'
    reasoning: str

async def route_query(query: str, chat_history: list[dict]) -> RouterOutput:
    """
    Tier 1 Router: rewrites the query using conversation context, then classifies intent.
    """
    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history
    ) if chat_history else "No prior conversation."

    messages = [
        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Conversation history:\n{history_text}\n\nCurrent query: {query}"},
    ]

    llm_kwargs = get_router_llm_kwargs()
    llm_kwargs["response_format"] = {"type": "json_object"}

    response = await call_llm(messages=messages, llm_kwargs=llm_kwargs)
    raw = response.choices[0].message.content
    usage = response.usage.model_dump() if response.usage else {}

    try:
        data = parse_llm_json(raw)
        output = RouterOutput(**data)
        log.info("Query routed", intent=output.intent, rewritten=output.rewritten_query)
        return output, usage
    except Exception as exc:
        log.error("Router failed to parse output", error=str(exc), raw=raw[:300])
        return RouterOutput(rewritten_query=query, intent="vector", reasoning="Fallback to vector on parse error."), usage
