from sentence_transformers import SentenceTransformer
from src.core.config import settings
from src.core.logger import log
import asyncio

class EmbeddingManager:
    """
    Singleton wrapper around SentenceTransformer to ensure the model is only loaded into memory once.
    """
    _instance = None

    def __init__(self):
        model_name = settings.EMBEDDING_MODEL.replace("huggingface/", "")
        log.info("Loading local embedding model via sentence-transformers", model=model_name)
        self.model = SentenceTransformer(model_name)

    @classmethod
    def get_instance(cls) -> "EmbeddingManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embeds a list of texts locally. SentenceTransformer returns a numpy array,
        so we convert it to standard Python lists of floats for Neo4j.
        """
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

# Global instance
embedding_manager = None

def get_embedding_manager() -> EmbeddingManager:
    global embedding_manager
    if embedding_manager is None:
        embedding_manager = EmbeddingManager.get_instance()
    return embedding_manager

async def embed_texts_local(texts: list[str]) -> list[list[float]]:
    """
    Async wrapper for embedding texts locally to prevent blocking the event loop.
    """
    manager = get_embedding_manager()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, manager.embed_texts, texts)
