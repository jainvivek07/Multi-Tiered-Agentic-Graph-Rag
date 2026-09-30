from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from src.core.exceptions import NotAuthorizedException, ResourceNotFoundException
from src.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from src.repositories.user_repo import UserRepository
from src.models.api import UserCreate, Token
from src.models.sql import User
from fastapi import HTTPException, status

class AuthService:
    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)

    async def authenticate_user(self, email: str, password: str) -> Token:
        user = await self.repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise NotAuthorizedException("Incorrect email or password")
        access_token = create_access_token(user_id=str(user.id), email=user.email, role=user.role)
        refresh_token = create_refresh_token(user_id=str(user.id))
        return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")

    async def refresh_token_pair(self, refresh_token_str: str) -> Token:
        try:
            payload = decode_refresh_token(refresh_token_str)
            user_id = payload.get("sub")
            if not user_id:
                raise NotAuthorizedException("Invalid refresh token payload")
        except Exception:
            raise NotAuthorizedException("Invalid or expired refresh token")

        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise NotAuthorizedException("User inactive or not found")

        access_token = create_access_token(user_id=str(user.id), email=user.email, role=user.role)
        new_refresh_token = create_refresh_token(user_id=str(user.id))
        return Token(access_token=access_token, refresh_token=new_refresh_token, token_type="bearer")

    async def register_user(self, user_create: UserCreate) -> User:
        existing = await self.repo.get_by_email(user_create.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists"
            )
        hashed = get_password_hash(user_create.password)
        new_user = User(email=user_create.email, hashed_password=hashed)
        try:
            return await self.repo.create(new_user)
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists"
            )
