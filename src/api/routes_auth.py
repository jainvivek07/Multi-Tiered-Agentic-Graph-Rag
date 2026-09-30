from typing import Optional
from starlette.requests import Request
from fastapi import APIRouter, Depends, Response, Cookie, Body, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from src.infra.postgres import get_db_session
from src.core.config import settings
from src.core.limiter import limiter
from src.services.auth_service import AuthService
from src.models.api import Token, RefreshTokenRequest, UserCreate, UserResponse

router = APIRouter()

@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    auth_service = AuthService(session)
    token = await auth_service.authenticate_user(form_data.username, form_data.password)
    
    # Set short-lived access token cookie (accessible across all API endpoints)
    response.set_cookie(
        key="access_token",
        value=token.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    
    # Set long-lived refresh token cookie (scoped only to /auth endpoints)
    if token.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=token.refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path=f"{settings.API_V1_STR}/auth",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )
    
    return token

@router.post("/refresh", response_model=Token)
async def refresh(
    response: Response,
    body: Optional[RefreshTokenRequest] = Body(default=None),
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Refresh access token using either HttpOnly cookie or request body.
    Rotates the refresh token and verifies user status in PostgreSQL.
    """
    refresh_token = refresh_token_cookie or (body.refresh_token if body else None)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )
        
    auth_service = AuthService(session)
    new_token = await auth_service.refresh_token_pair(refresh_token)
    
    # Set new access token cookie
    response.set_cookie(
        key="access_token",
        value=new_token.access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    
    # Set rotated refresh token cookie
    if new_token.refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=new_token.refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            path=f"{settings.API_V1_STR}/auth",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )
        
    return new_token

@router.post("/logout")
async def logout(response: Response):
    """Clear access and refresh token cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path=f"{settings.API_V1_STR}/auth")
    return {"message": "Logged out successfully"}

@router.post("/register", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(
    request: Request,
    response: Response,
    user_create: UserCreate,
    session: AsyncSession = Depends(get_db_session),
):
    auth_service = AuthService(session)
    return await auth_service.register_user(user_create)

