import re
import json

def parse_llm_json(text: str) -> dict:
    """Strips markdown code blocks before parsing JSON."""
    clean_text = re.sub(r"^```(?:json)?\n", "", text, flags=re.MULTILINE)
    clean_text = re.sub(r"```$", "", clean_text, flags=re.MULTILINE)
    return json.loads(clean_text.strip())

def strip_markdown_fences(text: str) -> str:
    """Strips markdown code blocks to retrieve raw text, useful for Cypher queries."""
    clean_text = re.sub(r"^```(?:cypher)?\n", "", text, flags=re.MULTILINE)
    clean_text = re.sub(r"```$", "", clean_text, flags=re.MULTILINE)
    return clean_text.strip()
