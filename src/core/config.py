from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Tiered Agentic Graph RAG"
    API_V1_STR: str = "/api/v1"

    # Deployment mode: 'local' | 'deployment'
    APP_ENV: Literal["local", "deployment"] = "deployment"

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: str
    POSTGRES_DB: str

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.APP_ENV=="local":
            return (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        
        return self.SUPABASE_URL

    # Neo4j — admin (read-write) connection
    NEO4J_URI: str
    NEO4J_USER: str
    NEO4J_PASSWORD: str

    # Neo4j — read-only connection for user-facing Cypher queries
    NEO4J_READER_USER: str
    NEO4J_READER_PASSWORD: str

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USERNAME: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_DECODE_RESPONSES: bool = True

    # LLM Model Names
    ROUTER_MODEL: str
    CYPHER_MODEL: str
    SYNTHESIS_MODEL: str
    EMBEDDING_MODEL: str
    RERANKER_MODEL: str = "ms-marco-MiniLM-L-12-v2"

    # LLM API Keys
    GROQ_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None
    NAGA_API_KEY: Optional[str] = None

    # LangSmith Observability
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "tiered-agentic-rag"

    # Agent Behaviour
    CHAT_HISTORY_WINDOW_SIZE: int = 5
    CYPHER_MAX_RETRIES: int = 3
    VECTOR_TOP_K: int = 20
    VECTOR_RERANK_TOP_K: int = 5
    EMBEDDING_DIMENSIONS: int = 1024

    # Semantic Cache
    SEMANTIC_CACHE_THRESHOLD: float = 0.8

    # NeMo Guardrails
    NEMO_CONFIG_PATH: str = "config/nemo"

    # Supabase (required when APP_ENV=deployment)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Parallel LLM extraction
    EXTRACTION_CONCURRENCY: int = 10

    # CORS — comma-separated list of allowed frontend origins
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Rate Limiting (SlowAPI)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URI: str = "memory://"
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_CHAT: str = "10/minute"

    # SSE Streaming
    SSE_QUEUE_SIZE: int = 100          # max buffered events per connection
    SSE_KEEPALIVE_INTERVAL: float = 15.0  # seconds between ping heartbeats
    SSE_REQUEST_TTL: int = 300         # seconds before an unstarted request is discarded

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
