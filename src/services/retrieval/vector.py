import litellm
from flashrank import Ranker, RerankRequest
from src.infra.embeddings import embed_texts_local
from src.core.config import settings
from src.infra.neo4j import neo4j_manager
from src.repositories.neo4j_repo import Neo4jRepository
from src.core.logger import log

_ranker = Ranker(model_name=settings.RERANKER_MODEL)

async def hybrid_vector_search(query: str, category: str) -> list[dict]:
    """
    Tier 2 Vector Path:
    1. Embeds the (rewritten) query via LiteLLM.
    2. Runs HNSW dense vector search in Neo4j filtered by category (top VECTOR_TOP_K).
    3. Reranks with FlashRank cross-encoder, returning top VECTOR_RERANK_TOP_K.
    """
    log.info(
        "Running vector search",
        category=category,
        top_k=settings.VECTOR_TOP_K,
        rerank_top_k=settings.VECTOR_RERANK_TOP_K,
    )

    log.info("Generating local embedding for query")
    embeddings = await embed_texts_local([query])
    query_embedding = embeddings[0]

    driver = await neo4j_manager.get_driver()
    repo = Neo4jRepository(driver)

    raw_results = await repo.vector_search(
        embedding=query_embedding,
        category=category,
        top_k=settings.VECTOR_TOP_K,
    )

    if not raw_results:
        log.info("Vector search returned no results")
        return []

    passages = [
        {"id": i, "text": str(r.get("content") or "")}
        for i, r in enumerate(raw_results)
    ]
    rerank_request = RerankRequest(query=query, passages=passages)
    reranked = _ranker.rerank(rerank_request)

    top_indices = [p["id"] for p in reranked[: settings.VECTOR_RERANK_TOP_K]]
    top_results = [raw_results[i] for i in top_indices]

    # Enrich any chunk missing a filename by looking up its Document record in PostgreSQL
    missing_doc_ids = {
        r["doc_id"] for r in top_results if r.get("doc_id") and not r.get("filename")
    }
    if missing_doc_ids:
        try:
            import uuid as _uuid
            from sqlalchemy.future import select
            from src.infra.postgres import AsyncSessionLocal
            from src.models.sql import Document

            async with AsyncSessionLocal() as session:
                for doc_id_str in missing_doc_ids:
                    try:
                        stmt = select(Document).where(Document.id == _uuid.UUID(str(doc_id_str)))
                        res = await session.execute(stmt)
                        doc_obj = res.scalars().first()
                        if doc_obj and doc_obj.filename:
                            for r in top_results:
                                if str(r.get("doc_id")) == str(doc_id_str):
                                    r["filename"] = doc_obj.filename
                    except Exception:
                        pass
        except Exception as e:
            log.warning("failed_to_enrich_document_filenames", error=str(e))

    log.info(
        "Vector search and rerank complete",
        raw=len(raw_results),
        after_rerank=len(top_results),
    )
    return top_results
