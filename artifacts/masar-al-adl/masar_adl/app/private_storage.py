"""Private PDF objects, preserving the existing document schema and policy.

Only opaque references go in documents.file_name. No public/signed URL is
issued; callers must authorize the document before invoking a read operation.
Legacy local filenames are deliberately not migrated or used as cloud fallbacks.
"""
import hashlib
import os
import re
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path

from .errors import AppError, NotFound

REFERENCE = re.compile(r"cloud-v1-(demo|sqlserver)-([0-9a-f]{32})-([0-9a-f]{64})\.pdf\Z")


class StorageUnavailable(AppError):
    status = 503

    def __init__(self):
        super().__init__("تعذّر الوصول إلى التخزين الخاص. لم يُستخدم بديل محلي؛ حاول لاحقًا.")


def configure(settings, repository_mode):
    """Bind to the repository's *actual* mode, including auto-mode fallback."""
    settings._pdf_scope = repository_mode
    backend = getattr(settings, "pdf_storage_backend", "local")
    if backend not in ("local", "app_storage"):
        raise ValueError("PDF_STORAGE_BACKEND must be local or app_storage")
    if backend == "app_storage" and (
        not getattr(settings, "pdf_storage_bucket", "") or repository_mode not in ("demo", "sqlserver")
    ):
        raise ValueError("Private PDF storage needs an explicit bucket and a supported repository mode")


def is_reference(value):
    return isinstance(value, str) and value.startswith("cloud-v1-")


def object_key(settings, reference):
    match = REFERENCE.fullmatch(reference) if isinstance(reference, str) else None
    scope = getattr(settings, "_pdf_scope", getattr(settings, "data_mode", "demo"))
    if not match or match[1] != scope:
        raise NotFound()
    return f"masar-al-adl/private-pdfs/v1/{match[1]}/{match[2]}/{match[3]}.pdf"


@lru_cache(maxsize=4)
def _client(bucket):
    # Explicit selection is essential: SDK default-bucket discovery is separate
    # from provisioning and is not reliable in every development environment.
    from replit.object_storage import Client
    return Client(bucket_id=bucket)


def _call(settings, method, *args):
    bucket = getattr(settings, "pdf_storage_bucket", "")
    if not bucket:
        raise StorageUnavailable()
    try:
        return getattr(_client(bucket), method)(*args)
    except Exception as error:
        # Missing objects are not service outages. Never return raw SDK errors,
        # bucket identifiers, signed URLs, transport details or credentials.
        from replit.object_storage.errors import ObjectNotFoundError
        if isinstance(error, ObjectNotFoundError):
            raise NotFound("الملف غير موجود في التخزين الخاص") from None
        raise StorageUnavailable() from None


def save(settings, data):
    if not data.startswith(b"%PDF-") or len(data) > settings.max_upload_bytes:
        raise StorageUnavailable()
    scope = getattr(settings, "_pdf_scope", getattr(settings, "data_mode", "demo"))
    digest = hashlib.sha256(data).hexdigest()
    reference = f"cloud-v1-{scope}-{uuid.uuid4().hex}-{digest}.pdf"
    key = object_key(settings, reference)
    # UUID + content digest: even a UUID collision cannot overwrite other
    # content. No filename, citizen identifier or case title enters an object key.
    _call(settings, "upload_from_bytes", key, data)
    return reference


def discard(path):
    if path is not None:
        Path(path).unlink(missing_ok=True)


def resolve(settings, reference, verify_only=False):
    key = object_key(settings, reference)
    if verify_only:
        if not _call(settings, "exists", key):
            raise NotFound("الملف غير موجود في التخزين الخاص")
        return None
    data = _call(settings, "download_as_bytes", key)
    digest = REFERENCE.fullmatch(reference)[3]
    if (not isinstance(data, bytes) or not data.startswith(b"%PDF-")
            or len(data) > settings.max_upload_bytes or hashlib.sha256(data).hexdigest() != digest):
        raise StorageUnavailable()
    cache = settings.storage_dir / ".private-pdf-transfers"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, filename = tempfile.mkstemp(prefix="transfer-", suffix=".pdf", dir=cache)
    path = Path(filename)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
    except BaseException:
        discard(path)
        raise
    return path
