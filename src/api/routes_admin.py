import mimetypes
import shutil
import tempfile
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.postgres import get_db_session
from src.api.dependencies import get_current_admin, get_current_user
from src.models.sql import Document
from src.models.api import CurrentUser
from src.repositories.doc_repo import DocumentRepository
from src.services.admin_service import AdminService
from src.tasks.ingestion_tasks import process_document_task
from src.core.logger import log
from src.infra.neo4j import neo4j_manager
from src.core.config import settings
from sqlalchemy.future import select
from typing import Optional

router = APIRouter()

@router.get("/users")
async def get_users(
    admin: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session)
):
    from src.models.sql import User
    stmt = select(User)
    result = await session.execute(stmt)
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None
        }
        for u in users
    ]

@router.put("/users/{user_id}/active")
async def update_user_status(
    user_id: str,
    is_active: str = Form(...),
    admin: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session)
):
    from src.models.sql import User
    import uuid
    
    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await session.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_active = is_active.lower() == 'true'
    await session.commit()
    return {"message": "User status updated"}

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str = Form(...),
    admin: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session)
):
    from src.models.sql import User
    import uuid
    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await session.execute(stmt)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.role = role.lower()
    await session.commit()
    return {"message": "User role updated"}

@router.delete("/categories/{category}")
async def delete_category(
    category: str,
    admin: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session)
):
    from src.models.sql import Document, ChatSession
    from sqlalchemy import delete
    import urllib.parse
    
    cat_decoded = urllib.parse.unquote(category).lower()
    
    # 1. Delete SQL documents and sessions for this category
    await session.execute(delete(Document).where(Document.category == cat_decoded))
    await session.execute(delete(ChatSession).where(ChatSession.category == cat_decoded))
    await session.commit()
    
    # 2. Delete Neo4j nodes (Entities and Chunks) for this category
    try:
        driver = await neo4j_manager.get_driver()
        async with driver.session() as neo4j_session:
            await neo4j_session.run(
                "MATCH (n) WHERE n.category = $category DETACH DELETE n",
                {"category": cat_decoded}
            )
    except Exception as e:
        log.error("neo4j_category_delete_failed", error=str(e))
        
    return {"message": f"Category {cat_decoded} deleted successfully"}


@router.get("/categories/{category}/documents")
async def list_category_documents(
    category: str,
    admin: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """Return all non-deleted documents in a given category."""
    import urllib.parse
    cat_decoded = urllib.parse.unquote(category).lower()

    stmt = select(Document).where(
        Document.category == cat_decoded,
        Document.is_deleted == False,
    ).order_by(Document.created_at.desc())
    result = await session.execute(stmt)
    docs = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "category": d.category,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            # In deployment mode file_path holds the Supabase storage key (always present if set);
            # in local mode we check the file actually exists on disk.
            "has_file": (
                bool(d.file_path)
                if settings.APP_ENV == "deployment"
                else bool(d.file_path and Path(d.file_path).exists())
            ),
        }
        for d in docs
    ]


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    admin: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """Soft-delete a single document and purge its Neo4j chunks."""
    import uuid as _uuid

    try:
        doc_uuid = _uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document id")

    stmt = select(Document).where(Document.id == doc_uuid)
    result = await session.execute(stmt)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Soft-delete in Postgres
    doc.is_deleted = True
    await session.commit()

    # Remove Neo4j Chunk nodes that belong to this document
    try:
        driver = await neo4j_manager.get_driver()
        async with driver.session() as neo4j_session:
            await neo4j_session.run(
                "MATCH (c:Chunk) WHERE c.doc_id = $doc_id DETACH DELETE c",
                {"doc_id": doc_id},
            )
    except Exception as e:
        log.warning("neo4j_doc_delete_failed", doc_id=doc_id, error=str(e))

    # Delete the stored file if it exists
    if doc.file_path:
        try:
            Path(doc.file_path).unlink(missing_ok=True)
        except Exception as e:
            log.warning("file_delete_failed", doc_id=doc_id, error=str(e))

    log.info("document_deleted", doc_id=doc_id, filename=doc.filename)
    return {"message": f"Document '{doc.filename}' deleted successfully"}


@router.get("/documents/{doc_id}/file")
async def serve_document_file(
    doc_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Serve the original uploaded file for a document."""
    import uuid as _uuid

    try:
        doc_uuid = _uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document id")

    stmt = select(Document).where(Document.id == doc_uuid, Document.is_deleted == False)
    result = await session.execute(stmt)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if settings.APP_ENV == "deployment":
        # In deployment mode, file_path stores the Supabase storage key.
        if not doc.file_path:
            raise HTTPException(status_code=404, detail="No file associated with this document")
        from src.core.storage import get_signed_url
        signed_url = get_signed_url(doc.file_path, expires_in_seconds=3600)
        return {"url": signed_url}

    # Local mode — serve directly from disk
    if not doc.file_path or not Path(doc.file_path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    media_type, _ = mimetypes.guess_type(doc.filename or "")
    return FileResponse(
        path=doc.file_path,
        filename=doc.filename,
        media_type=media_type or "application/octet-stream",
        content_disposition_type="inline",
    )


@router.get("/graph")
async def get_graph(
    category: Optional[str] = None,
    admin: CurrentUser = Depends(get_current_admin)
):
    """Fetches knowledge graph nodes and edges for visualization, optionally filtered by category."""
    try:
        driver = await neo4j_manager.get_driver()
        async with driver.session() as neo4j_session:
            if category:
                q = """
                MATCH (n) WHERE n.category = $category
                OPTIONAL MATCH (n)-[r]->(m) WHERE m.category = $category
                RETURN elementId(n) AS n_id, labels(n) AS n_labels, properties(n) AS n_props,
                       elementId(m) AS m_id, labels(m) AS m_labels, properties(m) AS m_props,
                       type(r) AS r_type
                LIMIT 500
                """
                result = await neo4j_session.run(q, {"category": category})
            else:
                q = """
                MATCH (n)
                OPTIONAL MATCH (n)-[r]->(m)
                RETURN elementId(n) AS n_id, labels(n) AS n_labels, properties(n) AS n_props,
                       elementId(m) AS m_id, labels(m) AS m_labels, properties(m) AS m_props,
                       type(r) AS r_type
                LIMIT 500
                """
                result = await neo4j_session.run(q)
                
            records = await result.data()
            
            nodes_dict = {}
            links = []
            
            for row in records:
                if row["n_id"] and row["n_id"] not in nodes_dict:
                    labels = row["n_labels"] or []
                    nodes_dict[row["n_id"]] = {
                        "id": row["n_id"],
                        "label": row["n_props"].get("id", row["n_props"].get("name", "Unknown")),
                        "type": "entity" if "Entity" in labels else "chunk",
                        "category": row["n_props"].get("category", "")
                    }
                if row["m_id"] and row["m_id"] not in nodes_dict:
                    labels = row["m_labels"] or []
                    nodes_dict[row["m_id"]] = {
                        "id": row["m_id"],
                        "label": row["m_props"].get("id", row["m_props"].get("name", "Unknown")),
                        "type": "entity" if "Entity" in labels else "chunk",
                        "category": row["m_props"].get("category", "")
                    }
                if row["n_id"] and row["m_id"] and row["r_type"]:
                    links.append({
                        "source": row["n_id"],
                        "target": row["m_id"],
                        "type": row["r_type"]
                    })
                    
            return {
                "nodes": list(nodes_dict.values()),
                "links": links
            }
    except Exception as e:
        log.error("failed_to_fetch_graph", error=str(e))
        return {
            "nodes": [],
            "links": []
        }

@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion(
    category: str = Form(...),
    file: UploadFile = File(...),
    admin: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Admin-only: Upload a document for offline ingestion.
    File metadata is persisted immediately; parsing and graph loading are
    dispatched to a durable Celery task queue (not an in-process background task).
    """
    allowed_types = {"application/pdf", "text/html", "text/plain"}
    allowed_extensions = {".pdf", ".html", ".htm", ".txt"}

    suffix = Path(file.filename or "doc").suffix.lower()
    content_type = file.content_type

    if content_type == "application/octet-stream" or not content_type:
        guessed_type, _ = mimetypes.guess_type(file.filename or "")
        if guessed_type:
            content_type = guessed_type

    if content_type not in allowed_types and suffix not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: PDF, HTML, TXT.",
        )

    doc_repo = DocumentRepository(session)

    if settings.APP_ENV == "deployment":
        # --- Deployment path: stream directly to Supabase Storage ---
        from src.core.storage import upload_file_to_supabase

        file_bytes = await file.read()
        storage_key = f"{uuid.uuid4()}{suffix}"
        upload_file_to_supabase(file_bytes, storage_key, content_type)

        doc = await doc_repo.create(Document(
            filename=file.filename,
            category=category,
            uploaded_by=admin.id,
            status="pending",
            file_path=storage_key,   # reuse file_path column to store Supabase key
        ))

        process_document_task.delay(
            doc_id=str(doc.id),
            file_path=storage_key,   # worker will interpret this as a Supabase key
            category=category,
        )
    else:
        # --- Local path: save to uploads/ on disk (original behaviour) ---
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        shutil.copyfileobj(file.file, tmp_file)
        tmp_file.close()

        doc = await doc_repo.create(Document(
            filename=file.filename,
            category=category,
            uploaded_by=admin.id,
            status="pending",
        ))

        uploads_dir = Path("uploads")
        uploads_dir.mkdir(exist_ok=True)
        safe_filename = f"{doc.id}_{Path(file.filename or 'document').name}"
        persistent_path = uploads_dir / safe_filename
        shutil.copy2(tmp_file.name, persistent_path)

        doc.file_path = str(persistent_path)
        await session.commit()

        process_document_task.delay(
            doc_id=str(doc.id),
            file_path=tmp_file.name,
            category=category,
        )

    log.info("Ingestion task enqueued", doc_id=str(doc.id), category=category)
    return {"document_id": str(doc.id), "status": "pending", "message": "Ingestion queued."}


@router.get("/metrics")
async def get_dashboard_metrics(
    admin: CurrentUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """Admin dashboard — token usage, latency, cache rates, route distribution."""
    admin_service = AdminService(session)
    return await admin_service.get_dashboard_metrics()
