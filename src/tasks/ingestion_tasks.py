import asyncio
from pathlib import Path

from src.tasks.celery_app import celery_app
from src.infra.postgres import AsyncSessionLocal, engine
from src.infra.neo4j import neo4j_manager
from src.repositories.doc_repo import DocumentRepository
from src.services.ingestion.parser import parse_document
from src.services.ingestion.extractor import extract_graph
from src.services.ingestion.loader import load_graph_to_neo4j
from src.core.logger import log


async def _execute_pipeline(doc_id: str, file_path: str, category: str) -> None:
    """
    Async core of the ingestion pipeline.
    Creates its own DB session since Celery workers run outside the FastAPI process.
    """
    async with AsyncSessionLocal() as db_session:
        doc_repo = DocumentRepository(db_session)
        doc = await doc_repo.get_by_id(doc_id)
        filename = doc.filename if doc else Path(file_path).name
        await doc_repo.update_status(doc_id, "processing")
        try:
            chunks = parse_document(file_path, doc_id)
            graph_result = await extract_graph(chunks)
            await load_graph_to_neo4j(doc_id, chunks, graph_result, category, filename=filename)
            await doc_repo.update_status(doc_id, "completed")
            log.info("Ingestion pipeline complete", doc_id=doc_id)
        except Exception as exc:
            log.error("Ingestion pipeline failed", doc_id=doc_id, error=str(exc))
            await doc_repo.update_status(doc_id, "failed")
            raise
        finally:
            Path(file_path).unlink(missing_ok=True)

            await engine.dispose()
            await neo4j_manager.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="src.tasks.ingestion_tasks.process_document_task",
)
def process_document_task(self, doc_id: str, file_path: str, category: str) -> None:
    try:
        asyncio.run(_execute_pipeline(doc_id, file_path, category))
    except Exception as exc:
        log.error("Celery task failed, scheduling retry", doc_id=doc_id, attempt=self.request.retries, error=str(exc))
        raise self.retry(exc=exc)
