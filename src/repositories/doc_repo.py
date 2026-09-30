from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.models.sql import Document

class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def get_by_id(self, doc_id: UUID) -> Optional[Document]:
        stmt = select(Document).where(Document.id == doc_id, Document.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_status(self, doc_id: UUID, status: str) -> None:
        doc = await self.get_by_id(doc_id)
        if doc:
            doc.status = status
            await self.session.commit()
