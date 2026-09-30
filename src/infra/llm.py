from __future__ import annotations

import litellm
from typing import Callable, Awaitable
from src.core.config import settings
from src.core.logger import log

litellm.success_callback = []
litellm.failure_callback = []

def _build_kwargs(model: str, temperature: float, max_tokens: int) -> dict:
    return {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

def get_router_llm_kwargs() -> dict:
    """
    Returns kwargs for the Router LLM (ChatGroq — deterministic intent classification).
    Pass these directly to litellm.acompletion(**kwargs, messages=[...]).
    """
    return _build_kwargs(
        model=settings.ROUTER_MODEL,
        temperature=0.0,
        max_tokens=2048,
    )

def get_cypher_llm_kwargs() -> dict:
    """
    Returns kwargs for the Cypher generation LLM (Nemotron — deterministic Cypher output).
    """
    return _build_kwargs(
        model=settings.CYPHER_MODEL,
        temperature=0.0,
        max_tokens=4096,
    )

def get_synthesis_llm_kwargs() -> dict:
    """
    Returns kwargs for the Synthesis LLM (Nemotron — natural language answer with citations).
    """
    return _build_kwargs(
        model=settings.SYNTHESIS_MODEL,
        temperature=0.3,
        max_tokens=4096,
    )

async def call_llm(messages: list[dict], llm_kwargs: dict) -> litellm.ModelResponse:
    model = llm_kwargs.get("model", "")
    
    if model.startswith("naga/"):
        llm_kwargs["model"] = model.replace("naga/", "openai/")
        llm_kwargs["api_base"] = "https://api.naga.ac/v1"  # Naga's base URL
        llm_kwargs["api_key"] = settings.NAGA_API_KEY

    try:
        response = await litellm.acompletion(messages=messages, num_retries=3, **llm_kwargs)
        return response
    except litellm.exceptions.RateLimitError as e:
        log.error("LiteLLM rate limit hit", model=llm_kwargs.get("model"), error=str(e))
        raise
    except litellm.exceptions.APIError as e:
        log.error("LiteLLM API error", model=llm_kwargs.get("model"), error=str(e))
        raise


async def call_llm_streaming(
    messages: list[dict],
    llm_kwargs: dict,
    on_token: Callable[[str], Awaitable[None]],
) -> tuple[str, dict]:
    """
    Streaming variant of call_llm.
    """
    llm_kwargs = {**llm_kwargs, "stream": True}
    model = llm_kwargs.get("model", "")

    if model.startswith("naga/"):
        llm_kwargs["model"] = model.replace("naga/", "openai/")
        llm_kwargs["api_base"] = "https://api.naga.ac/v1"
        llm_kwargs["api_key"] = settings.NAGA_API_KEY

    try:
        stream = await litellm.acompletion(messages=messages, num_retries=3, **llm_kwargs)
    except litellm.exceptions.RateLimitError as e:
        log.error("LiteLLM stream rate limit hit", model=llm_kwargs.get("model"), error=str(e))
        raise
    except litellm.exceptions.APIError as e:
        log.error("LiteLLM stream API error", model=llm_kwargs.get("model"), error=str(e))
        raise

    full_text = ""
    usage: dict = {}

    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            full_text += delta
            await on_token(delta)

        if hasattr(chunk, "usage") and chunk.usage:
            usage = chunk.usage.model_dump() if hasattr(chunk.usage, "model_dump") else {}

    return full_text, usage
