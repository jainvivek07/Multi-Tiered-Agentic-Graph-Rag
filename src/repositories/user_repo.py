from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.models.sql import User

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email, User.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, user_id: UUID | str) -> Optional[User]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        stmt = select(User).where(User.id == user_id, User.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
