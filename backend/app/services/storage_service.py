import uuid
from supabase import create_client, Client
from app.core.config import settings

BUCKET = "user-documents"


def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def upload_file(user_id: str, filename: str, content: bytes, content_type: str) -> str:
    """Upload file to Supabase Storage. Returns storage path."""
    supabase = get_supabase()
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    path = f"{user_id}/{uuid.uuid4()}.{ext}"
    supabase.storage.from_(BUCKET).upload(path, content, {"content-type": content_type})
    return path


def download_file(storage_path: str) -> bytes:
    """Download file bytes from Supabase Storage."""
    supabase = get_supabase()
    return supabase.storage.from_(BUCKET).download(storage_path)


def delete_file(storage_path: str) -> None:
    supabase = get_supabase()
    supabase.storage.from_(BUCKET).remove([storage_path])
