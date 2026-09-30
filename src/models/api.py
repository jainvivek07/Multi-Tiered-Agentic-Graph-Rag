from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional
from uuid import UUID

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str
    is_active: bool

class ChatRequest(BaseModel):
    session_id: Optional[UUID] = None
    category: str = Field(..., description="Category to restrict the search space")
    message: str = Field(..., description="The user's query")

class Citation(BaseModel):
    source_type: str  # 'document_chunk' | 'graph_node'
    content: str
    metadata: dict

class ChatResponse(BaseModel):
    session_id: UUID
    answer: str
    citations: List[Citation] = []
    route_taken: Optional[str] = None
    latency_ms: Optional[int] = None

class CurrentUser(BaseModel):
    id: UUID
    email: EmailStr
    role: str
