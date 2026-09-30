from contextlib import asynccontextmanager
from fastapi import FastAPI
import re
from fastapi.middleware.cors import CORSMiddleware
from starlette_csrf import CSRFMiddleware

from src.core.config import settings
from src.core.logger import log
from src.infra.postgres import engine
from src.infra.neo4j import neo4j_manager, neo4j_reader_manager
from src.infra.redis import redis_manager, redis_binary_manager, ensure_semantic_cache_index
from src.core.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from src.api.routes_auth import router as auth_router
from src.api.routes_admin import router as admin_router
from src.api.routes_user import router as user_router
from src.api.routes_sse import router as sse_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting up application...")

    driver = await neo4j_manager.get_driver()
    async with driver.session() as neo4j_session:
        await neo4j_session.run(
            "CREATE INDEX entity_category IF NOT EXISTS FOR (e:Entity) ON (e.category)"
        )
        await neo4j_session.run(
            "CREATE INDEX chunk_category IF NOT EXISTS FOR (c:Chunk) ON (c.category)"
        )
        await neo4j_session.run(
            f"""
            CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {{
                indexConfig: {{
                    `vector.dimensions`: {settings.EMBEDDING_DIMENSIONS},
                    `vector.similarity_function`: 'cosine'
                }}
            }}
            """
        )
        log.info("Neo4j indexes ensured.")

    
    await neo4j_reader_manager.get_driver()

    await redis_manager.get_client()
    await redis_binary_manager.get_client()
    await ensure_semantic_cache_index()

    yield

    log.info("Shutting down application...")
    await engine.dispose()
    await neo4j_manager.close()
    await neo4j_reader_manager.close()
    await redis_manager.close()
    await redis_binary_manager.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# app.add_middleware(
#     CSRFMiddleware,
#     secret=settings.SECRET_KEY,
#     exempt_urls=[
#         re.compile(r"^/health$"),
#         re.compile(r"^/api/v1/openapi\.json$"),
#         re.compile(r"^/api/v1/auth/login$"),
#         re.compile(r"^/api/v1/auth/register$"),
#         re.compile(r"^/api/v1/auth/refresh$"),
#     ],
# )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRFToken"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])
app.include_router(user_router, prefix=f"{settings.API_V1_STR}/user", tags=["user"])
app.include_router(sse_router, prefix=f"{settings.API_V1_STR}/stream", tags=["stream"])


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
