import os
import tempfile
from pathlib import Path
from typing import Optional

# Supabase client is lazily initialized only in deployment mode
_supabase_client = None

BUCKET_NAME = "agentic_graph_rag_documents"


def _get_client():
    """Returns a Supabase client, initializing it on first use (deployment mode only)."""
    global _supabase_client
    if _supabase_client is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set when APP_ENV=deployment"
            )
        _supabase_client = create_client(url, key)
    return _supabase_client


def upload_file_to_supabase(file_bytes: bytes, file_path: str, content_type: str) -> str:
    """Uploads file bytes directly to the Supabase storage bucket."""
    client = _get_client()
    client.storage.from_(BUCKET_NAME).upload(
        file=file_bytes,
        path=file_path,
        file_options={"content-type": content_type, "upsert": "false"},
    )
    return file_path


def download_file_from_supabase(file_path: str) -> bytes:
    """Downloads a file from the private Supabase bucket into memory."""
    client = _get_client()
    return client.storage.from_(BUCKET_NAME).download(file_path)


def get_signed_url(file_path: str, expires_in_seconds: int = 3600) -> str:
    """Generates a temporary viewing URL for the frontend."""
    client = _get_client()
    res = client.storage.from_(BUCKET_NAME).create_signed_url(file_path, expires_in_seconds)
    return res["signedURL"]
