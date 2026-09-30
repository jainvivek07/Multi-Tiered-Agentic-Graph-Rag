from fastapi import HTTPException, status

class ResourceNotFoundException(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class NotAuthorizedException(HTTPException):
    def __init__(self, detail: str = "Not authorized"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Forbidden access"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
