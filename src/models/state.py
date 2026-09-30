from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator
from src.models.api import Citation

def add_usage(left: dict, right: dict) -> dict:
    """Merges token usage dictionaries across multiple agent hops."""
    return {
        "prompt_tokens": left.get("prompt_tokens", 0) + right.get("prompt_tokens", 0),
        "completion_tokens": left.get("completion_tokens", 0) + right.get("completion_tokens", 0),
        "total_tokens": left.get("total_tokens", 0) + right.get("total_tokens", 0),
    }

class GraphState(TypedDict):
    """
    Represents the state of the LangGraph orchestration workflow.
    Fields annotated with operator.add are reducers — LangGraph appends
    new items from each node rather than overwriting, preventing race conditions
    in hybrid mode where vector and graph nodes run concurrently.
    """
    original_query: str
    rewritten_query: Optional[str]
    category: str
    chat_history: List[Dict[str, str]]
    route: Optional[str]
    cypher_query: Optional[str]
    retrieved_context: Annotated[List[Any], operator.add]
    cypher_errors: Annotated[List[str], operator.add]
    final_answer: Optional[str]
    citations: List[Citation]
    hallucination_flag: bool
    usage: Annotated[dict, add_usage]
