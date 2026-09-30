from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from src.models.sql import ChatSession, ChatMessage

class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_session(self, session_id: UUID) -> ChatSession | None:
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_session(self, user_id: UUID, category: str) -> ChatSession:
        chat_session = ChatSession(user_id=user_id, category=category)
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return chat_session

    async def add_message(self, message: ChatMessage) -> ChatMessage:
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def get_recent_messages(self, session_id: UUID, limit: int = 5) -> List[ChatMessage]:
        """
        Fetches the most recent N messages for the sliding window memory context.
        Orders by created_at DESC, but returns them in chronological order.
        """
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(desc(ChatMessage.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse() # Return chronological order
        return messages

    async def get_user_sessions(self, user_id: UUID) -> List[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(desc(ChatSession.created_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_session_messages(self, session_id: UUID) -> List[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
