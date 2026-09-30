import asyncio
from src.models.graph import GraphExtractionResult, NodeSchema, EdgeSchema, DocumentChunk, ChunkEntityMapping
from src.infra.llm import get_router_llm_kwargs, call_llm
from src.core.utils import parse_llm_json
from src.core.logger import log
from src.core.prompts import EXTRACTION_SYSTEM_PROMPT
from src.core.config import settings


async def _extract_single_chunk(
    chunk: DocumentChunk,
    llm_kwargs: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[str, NodeSchema], list[EdgeSchema], list[ChunkEntityMapping]]:
    """
    Processes a single chunk through the LLM extractor under a shared semaphore.
    Returns a tuple of (nodes_dict, edges, mappings) for this chunk.
    Returns empty collections on failure so the rest of the document is unaffected.
    """
    async with semaphore:
        log.info("Extracting graph from chunk", chunk_id=chunk.id, seq_index=chunk.seq_index)
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract the knowledge graph:\n\n{chunk.text}"},
        ]
        try:
            response = await call_llm(messages=messages, llm_kwargs=llm_kwargs)
            data = parse_llm_json(response.choices[0].message.content)

            nodes: dict[str, NodeSchema] = {}
            edges: list[EdgeSchema] = []
            mappings: list[ChunkEntityMapping] = []

            for node_dict in data.get("nodes", []):
                node = NodeSchema(**node_dict)
                nodes[node.id] = node
                mappings.append(ChunkEntityMapping(chunk_id=chunk.id, entity_id=node.id))

            edges.extend([EdgeSchema(**e) for e in data.get("edges", [])])
            return nodes, edges, mappings

        except Exception as exc:
            log.error("Chunk extraction failed — skipping", chunk_id=chunk.id, error=str(exc))
            return {}, [], []


async def extract_graph(chunks: list[DocumentChunk]) -> GraphExtractionResult:
    """
    Processes DocumentChunks through the LLM extractor concurrently.

    Uses an asyncio.Semaphore to bound the number of simultaneous in-flight LLM
    requests to settings.EXTRACTION_CONCURRENCY (default: 10), preventing rate-limit
    errors while still achieving near-linear speedup over the previous sequential loop.

    Deterministically maps extracted entities back to their source chunks.
    The LLM is restricted to pure taxonomy — it never touches the raw verbatim text.
    """
    llm_kwargs = get_router_llm_kwargs()
    llm_kwargs["response_format"] = {"type": "json_object"}

    semaphore = asyncio.Semaphore(settings.EXTRACTION_CONCURRENCY)

    # Fan-out: launch all chunk extractions concurrently under the semaphore
    results = await asyncio.gather(
        *[_extract_single_chunk(chunk, llm_kwargs, semaphore) for chunk in chunks],
        return_exceptions=False,
    )

    # Merge results — later chunks overwrite duplicate node IDs (same deterministic LLM output)
    all_nodes: dict[str, NodeSchema] = {}
    all_edges: list[EdgeSchema] = []
    chunk_mappings: list[ChunkEntityMapping] = []

    for nodes, edges, mappings in results:
        all_nodes.update(nodes)
        all_edges.extend(edges)
        chunk_mappings.extend(mappings)

    # Filter edges that reference nodes from failed chunks
    valid_node_ids = set(all_nodes.keys())
    valid_edges = [e for e in all_edges if e.source_id in valid_node_ids and e.target_id in valid_node_ids]

    log.info(
        "Graph extraction complete",
        chunks_processed=len(chunks),
        nodes=len(all_nodes),
        edges=len(valid_edges),
        skipped_edges=len(all_edges) - len(valid_edges),
    )
    return GraphExtractionResult(
        nodes=list(all_nodes.values()),
        edges=valid_edges,
        chunk_mappings=chunk_mappings,
    )
