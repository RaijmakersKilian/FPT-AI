import os
from functools import lru_cache
from azure.storage.blob import BlobServiceClient, ContentSettings

MODELS_CONTAINER   = os.getenv("AZURE_MODELS_CONTAINER",   "3dmodels")
REPORTS_CONTAINER  = os.getenv("AZURE_REPORTS_CONTAINER",  "reports")


@lru_cache(maxsize=1)
def _get_client() -> BlobServiceClient:
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is not set in .env")
    return BlobServiceClient.from_connection_string(conn_str)


def upload_blob(container: str, blob_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to Azure Blob Storage and return the public URL."""
    client = _get_client()
    blob = client.get_blob_client(container=container, blob=blob_path)
    blob.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )
    account = client.account_name
    return f"https://{account}.blob.core.windows.net/{container}/{blob_path}"


def upload_file_to_blob(container: str, blob_path: str, file_path: str, content_type: str = "application/octet-stream") -> str:
    """Upload a local file to Azure Blob Storage and return the public URL."""
    with open(file_path, "rb") as f:
        return upload_blob(container, blob_path, f.read(), content_type)
