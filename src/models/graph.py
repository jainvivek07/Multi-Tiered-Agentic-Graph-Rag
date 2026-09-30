from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class NodeSchema(BaseModel):
    id: str = Field(..., description="Unique identifier for the node")
    label: str = Field(..., description="Entity type — e.g. 'Person', 'Document', 'Concept'")
    properties: Dict[str, str] = Field(default_factory=dict)

class EdgeSchema(BaseModel):
    source_id: str = Field(..., description="ID of the source node")
    target_id: str = Field(..., description="ID of the target node")
    type: str = Field(..., description="Relationship type — e.g. 'MENTIONS', 'BELONGS_TO'")
    properties: Dict[str, str] = Field(default_factory=dict)

class DocumentChunk(BaseModel):
    """Represents a single semantic chunk of a parsed document."""
    id: str
    text: str
    seq_index: int
    embedding: Optional[List[float]] = None

class ChunkEntityMapping(BaseModel):
    """Deterministic mapping of a Chunk to the Entities the LLM found within it."""
    chunk_id: str
    entity_id: str

class GraphExtractionResult(BaseModel):
    """Pydantic schema for the structured output of the LLM graph extraction step."""
    nodes: List[NodeSchema]
    edges: List[EdgeSchema]
    chunk_mappings: List[ChunkEntityMapping] = []
