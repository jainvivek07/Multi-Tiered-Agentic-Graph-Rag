import redis.asyncio as redis
from redis.exceptions import ResponseError
from src.core.config import settings
from src.core.logger import log


SEMANTIC_CACHE_INDEX = "semantic_cache_idx"
SEMANTIC_CACHE_PREFIX = "scache:"


class RedisSingleton:
    """Decoded client — used for plain string key/value operations."""
    _instance: redis.Redis | None = None

    @classmethod
    async def get_client(cls) -> redis.Redis:
        if cls._instance is None:
            log.info("Initializing Redis connection...")
            cls._instance = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                username=settings.REDIS_USERNAME,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=settings.REDIS_DECODE_RESPONSES
            )
            await cls._instance.ping()
            log.info("Redis connection successful.")
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance is not None:
            log.info("Closing Redis connection...")
            await cls._instance.close()
            cls._instance = None


class RedisBinaryClient:
    """Raw bytes client — required for RediSearch vector operations.
    decode_responses MUST be False so embeddings survive the round-trip as bytes."""
    _instance: redis.Redis | None = None

    @classmethod
    async def get_client(cls) -> redis.Redis:
        if cls._instance is None:
            log.info("Initializing Redis binary client for vector ops...")
            cls._instance = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                username=settings.REDIS_USERNAME,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=False,
            )
            await cls._instance.ping()
            log.info("Redis binary client ready.")
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None


async def ensure_semantic_cache_index() -> None:
    """
    Index schema:
      - category  : TAG  — filtered before ANN to avoid cross-category hits
      - embedding : VECTOR HNSW FLOAT32 — cosine similarity ANN
      - answer    : TEXT (stored, not indexed) — the cached LLM answer
      - citations : TEXT (stored, not indexed) — serialised citation JSON
    Safe to call every startup — raises nothing if the index already exists.
    """
    client = await RedisBinaryClient.get_client()
    try:
        await client.execute_command(
            "FT.CREATE", SEMANTIC_CACHE_INDEX,
            "ON", "HASH",
            "PREFIX", "1", SEMANTIC_CACHE_PREFIX,
            "SCHEMA",
            "category", "TAG",
            "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(settings.EMBEDDING_DIMENSIONS),
                "DISTANCE_METRIC", "COSINE",
            "answer", "TEXT", "NOSTEM",
            "citations", "TEXT", "NOSTEM",
        )
        log.info("Redis semantic cache index created.", index=SEMANTIC_CACHE_INDEX)
    except ResponseError as exc:
        if "Index already exists" in str(exc):
            log.info("Redis semantic cache index already exists — skipping.", index=SEMANTIC_CACHE_INDEX)
        else:
            log.error("Failed to create Redis semantic cache index", error=str(exc))
            raise


redis_manager = RedisSingleton()
redis_binary_manager = RedisBinaryClient()
