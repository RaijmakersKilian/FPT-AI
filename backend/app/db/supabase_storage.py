import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def _get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    return create_client(url, key)


def get_db() -> Client:
    """Return the Supabase client for database (PostgREST) operations."""
    return _get_client()


def upload_file(bucket: str, storage_path: str, data: bytes, content_type: str) -> str:
    """Upload bytes to a Supabase Storage bucket and return the public URL."""
    client = _get_client()
    client.storage.from_(bucket).upload(
        path=storage_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return client.storage.from_(bucket).get_public_url(storage_path)


def delete_file(bucket: str, storage_path: str) -> None:
    """Remove a file from Supabase Storage (ignores errors if file is missing)."""
    try:
        _get_client().storage.from_(bucket).remove([storage_path])
    except Exception:
        pass


def path_from_public_url(url: str, bucket: str) -> str | None:
    """Extract the storage path from a Supabase public URL."""
    marker = f"/storage/v1/object/public/{bucket}/"
    idx = url.find(marker)
    if idx == -1:
        return None
    return url[idx + len(marker):]
