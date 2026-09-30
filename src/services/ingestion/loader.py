from typing import Optional
from src.core.logger import log
from src.models.graph import GraphExtractionResult, DocumentChunk
from src.repositories.neo4j_repo import Neo4jRepository
from src.infra.neo4j import neo4j_manager
from src.infra.embeddings import embed_texts_local


async def load_graph_to_neo4j(
    doc_id: str,
    chunks: list[DocumentChunk],
    extraction_result: GraphExtractionResult,
    category: str,
    filename: Optional[str] = None,
) -> None:
    """
    Embeds the verbatim text of each Chunk locally, then writes the full
    Document → Chunk → Entity graph lineage into Neo4j.
    """
    # 1. Embed the raw verbatim text of each chunk (not LLM-generated content)
    texts = [c.text for c in chunks]
    log.info("Generating local embeddings for chunks", count=len(texts))
    embeddings = await embed_texts_local(texts)

    # 2. Attach the embedding vectors back to each chunk object in-memory
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb

    # 3. Commit the full Document → Chunk → Entity graph to Neo4j
    driver = await neo4j_manager.get_driver()
    repo = Neo4jRepository(driver)
    await repo.ingest_graph(
        doc_id=doc_id,
        chunks=chunks,
        extraction_result=extraction_result,
        category=category,
        filename=filename,
    )
    log.info("Ingestion pipeline successfully committed to Neo4j", doc_id=doc_id)
