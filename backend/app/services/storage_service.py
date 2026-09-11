import logging
import uuid

from supabase import Client, create_client

from app.core.config import settings

BUCKET = "user-documents"
logger = logging.getLogger(__name__)


def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def _ensure_bucket(supabase: Client) -> None:
    """Create storage bucket if it doesn't exist yet."""
    try:
        supabase.storage.get_bucket(BUCKET)
    except Exception:
        try:
            supabase.storage.create_bucket(BUCKET, options={"public": False})
        except Exception as exc:
            logger.debug("Supabase bucket create skipped for %s: %s", BUCKET, exc)


def _safe_extension(filename: str) -> str:
    """Restrict the storage suffix to a short alphanumeric token.

    The original filename is attacker-controlled. Carrying it into the storage
    key would allow path separators or traversal sequences in the object key,
    so only a conservative extension is preserved; everything else is dropped.
    """
    raw = filename.rsplit(".", 1)[-1] if "." in filename else ""
    cleaned = "".join(ch for ch in raw.lower() if ch.isascii() and ch.isalnum())
    return cleaned[:10] or "bin"


def upload_file(user_id: str, filename: str, content: bytes, content_type: str) -> str:
    """Upload file to Supabase Storage. Returns storage path."""
    supabase = get_supabase()
    _ensure_bucket(supabase)
    ext = _safe_extension(filename)
    path = f"{user_id}/{uuid.uuid4()}.{ext}"
    try:
        supabase.storage.from_(BUCKET).upload(path, content, {"content-type": content_type})
    except Exception as exc:
        logger.warning("Storage upload failed for %s: %s", path, exc)
        raise RuntimeError("Storage upload failed") from exc
    return path


def _assert_owns_path(owner_id: str, storage_path: str) -> str:
    """Ensure storage_path belongs to owner_id.

    Storage uses the service-role key, which bypasses RLS, so callers must
    prove ownership. Paths are laid out as "{user_id}/{uuid}.{ext}", so the
    first segment must equal owner_id. Defense-in-depth against IDOR even when
    a caller already checked the DB row.
    """
    if not owner_id:
        raise PermissionError("owner_id is required for storage access")
    # Normalize and reject traversal
    normalized = storage_path.lstrip("/")
    if ".." in normalized.split("/"):
        raise PermissionError(f"Illegal storage path: {storage_path}")
    prefix = normalized.split("/", 1)[0]
    if prefix != owner_id:
        raise PermissionError(
            f"Storage path {storage_path} does not belong to user {owner_id}"
        )
    return normalized


def download_file(storage_path: str, owner_id: str) -> bytes:
    """Download file bytes from Supabase Storage. Verifies ownership first."""
    storage_path = _assert_owns_path(owner_id, storage_path)
    supabase = get_supabase()
    try:
        return supabase.storage.from_(BUCKET).download(storage_path)
    except Exception as exc:
        logger.warning("Storage download failed for %s: %s", storage_path, exc)
        raise RuntimeError("Storage download failed") from exc


def delete_file(storage_path: str, owner_id: str) -> None:
    """Delete a file from Supabase Storage. Verifies ownership first."""
    storage_path = _assert_owns_path(owner_id, storage_path)
    supabase = get_supabase()
    try:
        supabase.storage.from_(BUCKET).remove([storage_path])
    except Exception as exc:
        logger.warning("Storage delete failed for %s: %s", storage_path, exc)
        raise RuntimeError("Storage delete failed") from exc
