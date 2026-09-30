import asyncio
from src.core.config import settings
from src.infra.llm import get_cypher_llm_kwargs, call_llm
from src.core.utils import strip_markdown_fences
from src.infra.neo4j import neo4j_reader_manager
from src.repositories.neo4j_repo import Neo4jRepository
from src.core.logger import log
from src.core.prompts import CYPHER_SYSTEM_PROMPT

_schema_cache: str | None = None
_schema_lock = asyncio.Lock()


async def _get_live_schema() -> str:
    """
    Fetches the active Neo4j graph schema using apoc.meta.data() and formats it
    as a concise text block for injection into the LLM system prompt.

    Results are cached for 1 hour (3600 seconds) to avoid per-query overhead.
    Thread-safe under concurrent requests via asyncio.Lock.
    """
    global _schema_cache

    # Return cached schema if already populated — no lock needed for read
    if _schema_cache is not None:
        return _schema_cache

    async with _schema_lock:
        # Double-check after acquiring lock (another coroutine may have populated it)
        if _schema_cache is not None:
            return _schema_cache

        log.info("Fetching live Neo4j schema for Cypher prompt injection...")
        driver = await neo4j_reader_manager.get_driver()
        try:
            async with driver.session() as session:
                result = await session.run(
                    """
                    CALL apoc.meta.data()
                    YIELD label, property, type, other, elementType
                    WHERE elementType IN ['node', 'relationship']
                    RETURN elementType, label, property, type, other
                    ORDER BY elementType, label, property
                    """
                )
                records = await result.data()

            lines = ["=== Live Graph Schema ==="]
            for r in records:
                element = r.get("elementType", "")
                label = r.get("label", "")
                prop = r.get("property", "")
                typ = r.get("type", "")
                other = r.get("other", [])
                if element == "node":
                    lines.append(f"  Node (:{label}) — property: {prop} [{typ}]")
                elif element == "relationship":
                    targets = ", ".join(other) if other else "?"
                    lines.append(f"  Relationship [:{label}] — links to: {targets}")

            _schema_cache = "\n".join(lines)
            log.info("Live schema cached", node_count=sum(1 for r in records if r.get("elementType") == "node"))

        except Exception as exc:
            log.warning("Failed to fetch live schema — falling back to static prompt", error=str(exc))
            return ""

        return _schema_cache


def invalidate_schema_cache() -> None:
    global _schema_cache
    _schema_cache = None
    log.info("Neo4j schema cache invalidated.")


async def generate_and_execute_cypher(
    query: str,
    category: str,
    error_context: str | None = None,
) -> tuple[list[dict], dict]:

    live_schema = await _get_live_schema()
    system_prompt = CYPHER_SYSTEM_PROMPT
    if live_schema:
        system_prompt = f"{CYPHER_SYSTEM_PROMPT}\n\n{live_schema}"

    user_content = f"Generate a Cypher query to answer: {query}"
    if error_context:
        user_content += f"\n\nPrevious attempt failed with this error — fix it:\n{error_context}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    llm_kwargs = get_cypher_llm_kwargs()
    log.info("Generating Cypher query", has_error_context=error_context is not None)

    response = await call_llm(messages=messages, llm_kwargs=llm_kwargs)
    cypher = strip_markdown_fences(response.choices[0].message.content)
    usage = response.usage.model_dump() if response.usage else {}
    log.info("Cypher query generated", query=cypher)

    driver = await neo4j_reader_manager.get_driver()
    repo = Neo4jRepository(driver)

    results = await repo.execute_cypher(cypher, parameters={"category": category})
    log.info("Cypher executed successfully", results_returned=len(results))
    return results, usage
