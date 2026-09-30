from starlette.requests import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from jose import jwt, JWTError

from src.core.config import settings


def get_rate_limit_key(request: Request) -> str:
    """
    Derives rate limit key from JWT Bearer token / cookie if authenticated,
    falling back to client IP address.
    """
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except (JWTError, Exception):
            pass

    return get_remote_address(request)


limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    enabled=settings.RATE_LIMIT_ENABLED,
    headers_enabled=True,
)
