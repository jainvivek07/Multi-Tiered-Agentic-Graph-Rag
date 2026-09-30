from typing import Optional
from fastapi import Depends, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from src.core.config import settings
from src.core.exceptions import NotAuthorizedException, ForbiddenException
from src.models.api import CurrentUser

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    access_token: Optional[str] = Cookie(None)
) -> CurrentUser:
    token = None
    if credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token
    
    if not token:
        raise NotAuthorizedException("Not authenticated")
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        token_type = payload.get("type")
        if token_type and token_type != "access":
            raise NotAuthorizedException("Invalid token type")
            
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role")
        
        if not user_id or not email or not role:
            raise NotAuthorizedException("Invalid token payload")
            
        return CurrentUser(id=user_id, email=email, role=role)
    except JWTError:
        raise NotAuthorizedException("Could not validate credentials")

async def get_current_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise ForbiddenException("The user doesn't have enough privileges")
    return current_user
