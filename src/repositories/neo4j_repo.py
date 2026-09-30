from typing import Optional
from neo4j import AsyncDriver
from src.models.graph import GraphExtractionResult, DocumentChunk
from src.core.logger import log


class Neo4jRepository:
    def __init__(self, driver: AsyncDriver):
        self.driver = driver

    async def ingest_graph(
        self,
        doc_id: str,
        chunks: list[DocumentChunk],
        extraction_result: GraphExtractionResult,
        category: str,
        filename: Optional[str] = None,
    ) -> None:
        """
        Atomically writes the full provenance-aware graph into Neo4j within a
        single transaction:  (:Document)-[:HAS_CHUNK]->(:Chunk)-[:MENTIONS]->(:Entity)

        If any of the 5 steps fail, the transaction is rolled back in its entirety,
        preventing orphaned chunks, dangling entities, or missing relationship edges.
        """
        chunk_data = [
            {"id": c.id, "text": c.text, "seq_index": c.seq_index, "embedding": c.embedding}
            for c in chunks
        ]
        nodes_data = [
            {"id": n.id, "label": n.label, "properties": n.properties}
            for n in extraction_result.nodes
        ]
        edges_data = [
            {"source_id": e.source_id, "target_id": e.target_id, "type": e.type, "properties": e.properties}
            for e in extraction_result.edges
        ]
        mappings_data = [
            {"chunk_id": m.chunk_id, "entity_id": m.entity_id}
            for m in extraction_result.chunk_mappings
        ]

        async with self.driver.session() as session:
            tx = await session.begin_transaction()
            try:
                # Step 1: Merge the Document node
                await tx.run(
                    "MERGE (d:Document {id: $doc_id}) SET d.category = $category, d.filename = $filename",
                    doc_id=doc_id,
                    category=category,
                    filename=filename or "",
                )

                # Step 2: Ingest Chunks, link to Document, and write embedding vectors
                chunk_query = """
                UNWIND $chunks AS c
                MERGE (chunk:Chunk {id: c.id})
                SET chunk.text      = c.text,
                    chunk.seq_index = c.seq_index,
                    chunk.category  = $category
                WITH chunk, c
                MATCH (d:Document {id: $doc_id})
                MERGE (d)-[:HAS_CHUNK]->(chunk)
                WITH chunk, c
                CALL db.create.setNodeVectorProperty(chunk, 'embedding', c.embedding)
                """
                await tx.run(chunk_query, chunks=chunk_data, doc_id=doc_id, category=category)
                log.info("Neo4j chunks staged in transaction", count=len(chunk_data))

                # Step 3: Ingest Entities
                if nodes_data:
                    node_query = """
                    UNWIND $nodes AS n
                    MERGE (node:Entity {id: n.id})
                    SET node += n.properties, node.category = $category
                    WITH node, n
                    CALL apoc.create.addLabels(node, [n.label]) YIELD node AS labeledNode
                    RETURN count(labeledNode) AS nodesCreated
                    """
                    await tx.run(node_query, nodes=nodes_data, category=category)
                    log.info("Neo4j entities staged in transaction", count=len(nodes_data))

                # Step 4: Ingest Entity-to-Entity edges
                if edges_data:
                    edge_query = """
                    UNWIND $edges AS e
                    MATCH (source:Entity {id: e.source_id, category: $category})
                    MATCH (target:Entity {id: e.target_id, category: $category})
                    CALL apoc.create.relationship(source, e.type, e.properties, target) YIELD rel
                    RETURN count(rel) AS edgesCreated
                    """
                    await tx.run(edge_query, edges=edges_data, category=category)
                    log.info("Neo4j entity edges staged in transaction", count=len(edges_data))

                # Step 5: Wire Chunks to the Entities they mention
                if mappings_data:
                    mapping_query = """
                    UNWIND $mappings AS m
                    MATCH (c:Chunk {id: m.chunk_id})
                    MATCH (e:Entity {id: m.entity_id, category: $category})
                    MERGE (c)-[:MENTIONS]->(e)
                    """
                    await tx.run(mapping_query, mappings=mappings_data, category=category)
                    log.info("Neo4j chunk→entity mappings staged in transaction", count=len(mappings_data))

                await tx.commit()
                log.info("Neo4j graph transaction committed", doc_id=doc_id)

            except Exception as exc:
                await tx.rollback()
                log.error("Neo4j ingestion transaction rolled back", doc_id=doc_id, error=str(exc))
                raise

    async def execute_cypher(self, query: str, parameters: dict | None = None) -> list[dict]:
        """
        Executes a read-only Cypher query generated by the agent.

        Security is enforced at the database level via the reader_client role
        (READ + TRAVERSE privileges only). This driver instance must be initialized
        with the read-only credentials from settings.NEO4J_READER_USER.
        No application-level regex filtering is needed or used.
        """
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            return await result.data()

    async def vector_search(self, embedding: list[float], category: str, top_k: int) -> list[dict]:
        """
        HNSW dense vector search over Chunk nodes filtered by category.

        The category filter is applied as a WHERE clause AFTER the HNSW scan.
        To guarantee `top_k` relevant results, we over-fetch by requesting
        `top_k * 5` candidates from the index, then filter and return the top_k.

        NOTE: For a fully pre-filtered approach, migrate to a category-partitioned
        vector index or use Neo4j 5.18+ native pre-filter metadata support when
        your deployment supports it.
        """
        # Over-fetch to compensate for post-filter recall loss
        fetch_k = top_k * 5
        query = """
        CALL db.index.vector.queryNodes('chunk_embedding', $fetch_k, $embedding)
        YIELD node, score
        WHERE node.category = $category
        OPTIONAL MATCH (d:Document)-[:HAS_CHUNK]->(node)
        RETURN node.id AS id, node.text AS content, node.category AS category, score,
               d.id AS doc_id, d.filename AS filename
        ORDER BY score DESC
        LIMIT $top_k
        """
        async with self.driver.session() as session:
            result = await session.run(
                query, embedding=embedding, category=category, top_k=top_k, fetch_k=fetch_k
            )
            return await result.data()
