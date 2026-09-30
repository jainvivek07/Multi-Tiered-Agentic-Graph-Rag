from neo4j import AsyncGraphDatabase, AsyncDriver
from src.core.config import settings
from src.core.logger import log


class Neo4jSingleton:
    """
    Admin (read-write) driver used exclusively by the ingestion pipeline.
    Connects with full write privileges (settings.NEO4J_USER / NEO4J_PASSWORD).
    """
    _instance: AsyncDriver | None = None

    @classmethod
    async def get_driver(cls) -> AsyncDriver:
        if cls._instance is None:
            log.info("Initializing Neo4j admin connection pool...")
            cls._instance = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            await cls._instance.verify_connectivity()
            log.info("Neo4j admin connection successful.")
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance is not None:
            log.info("Closing Neo4j admin connection pool...")
            await cls._instance.close()
            cls._instance = None


class Neo4jReaderSingleton:
    _instance: AsyncDriver | None = None

    @classmethod
    async def get_driver(cls) -> AsyncDriver:
        if cls._instance is None:
            log.info("Initializing Neo4j read-only connection pool...")
            cls._instance = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_READER_USER, settings.NEO4J_READER_PASSWORD)
            )
            await cls._instance.verify_connectivity()
            log.info("Neo4j read-only connection successful.")
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance is not None:
            log.info("Closing Neo4j read-only connection pool...")
            await cls._instance.close()
            cls._instance = None


neo4j_manager = Neo4jSingleton()
neo4j_reader_manager = Neo4jReaderSingleton()
