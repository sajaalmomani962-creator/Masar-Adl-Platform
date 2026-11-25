import os
import uuid
from io import BytesIO
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import audit, private_storage
from .authz import Decision, document_decision
from .errors import BadRequest, Forbidden, NotFound

ACTION_CODE = {"view": "VIEW_DOCUMENT", "download": "DOWNLOAD_DOCUMENT", "print": "PRINT_DOCUMENT"}


def _sample_pdf(text: str) -> bytes:
    text = text.encode("latin-1", "replace").decode("latin-1").replace("(", "[").replace(")", "]")
    stream = f"BT /F1 20 Tf 60 740 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


def sample_pdf_bytes(label: str) -> bytes:
    """A valid one-page PDF with a visible Arabic demo watermark."""
    font_path = Path(__file__).parent / "resources" / "DejaVuSans.ttf"
    if "MasarArabic" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("MasarArabic", str(font_path)))
    output = BytesIO()
    page = canvas.Canvas(output, pagesize=(595, 842), invariant=1)
    page.setTitle("Masar Al-Adl — DEMO / TEST DOCUMENT")
    page.setFillColorRGB(0.043, 0.235, 0.365)
    page.setFont("MasarArabic", 30)
    page.drawCentredString(297.5, 710, get_display(arabic_reshaper.reshape("مستند تجريبي")))
    page.setFont("Helvetica", 16)
    page.drawCentredString(297.5, 650, "DEMO / TEST DOCUMENT")
    page.setFont("Helvetica", 11)
    page.drawCentredString(297.5, 620, label[:100])
    page.setFont("MasarArabic", 13)
    page.drawCentredString(297.5, 560, get_display(arabic_reshaper.reshape("نموذج أولي للعرض — ليس مستندًا رسميًا")))
    page.showPage()
    page.save()
    return output.getvalue()


def ensure_demo_files(repo, settings):
    """Seed rows reference PDFs that do not exist; create placeholder files in private storage."""
    if repo.mode != "demo":
        # Never fabricate an official response for a real database record.
        return
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    for d in repo.select("documents"):
        if private_storage.is_reference(d["file_name"]):
            # A missing private object must never become a fabricated local PDF.
            continue
        p = _path(settings, d["file_name"])
        if p and not p.exists():
            p.write_bytes(sample_pdf_bytes(f"doc {d['document_id']} {d['document_type']}"))


def _path(settings, file_name):
    base = settings.storage_dir.resolve()
    p = (base / Path(file_name).name).resolve()
    return p if p.parent == base else None  # blocks path traversal


def validate_pdf(filename, content_type, data, max_bytes):
    if not data:
        raise BadRequest("الملف فارغ")
    if len(data) > max_bytes:
        raise BadRequest("حجم الملف يتجاوز الحد المسموح (10MB)")
    if not (filename or "").lower().endswith(".pdf"):
        raise BadRequest("يُسمح بملفات PDF فقط")
    if (content_type or "").split(";")[0].strip().lower() != "application/pdf":
        raise BadRequest("نوع الملف غير مسموح")
    if not data.startswith(b"%PDF-"):
        raise BadRequest("محتوى الملف ليس PDF صالحًا")


def save_pdf(settings, data) -> str:
    if getattr(settings, "pdf_storage_backend", "local") == "app_storage":
        return private_storage.save(settings, data)
    settings.storage_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = f"{uuid.uuid4().hex}.pdf"
    path = settings.storage_dir / name
    # Exclusive creation neither follows an existing symlink nor overwrites a
    # collision. New uploads are owner-only even with a permissive process umask.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return name


def open_document(repo, settings, user, doc_id, action, log=True, verify_only=False):
    """Check access (server-side, every time), audit, and return (doc, path)."""
    doc = repo.get("documents", doc_id) if isinstance(doc_id, int) else None
    if not doc:
        raise NotFound()
    req = repo.get("document_requests", doc["request_id"])
    decision, reason, related = document_decision(repo, user, doc, req, action)
    if decision != Decision.ALLOW:
        audit.write(repo, user["user_id"], req["case_id"], req["request_id"], ACTION_CODE[action], False,
                    f"رفض {action} للمستند {doc_id}: {reason}")
        if not related:
            raise NotFound()
        raise Forbidden(reason)
    remote = private_storage.is_reference(doc["file_name"])
    if remote:
        path = private_storage.resolve(settings, doc["file_name"], verify_only=verify_only)
    else:
        path = _path(settings, doc["file_name"])
        if path is None or not path.exists():
            raise NotFound("الملف غير موجود في التخزين")
    try:
        if log:
            audit.write(repo, user["user_id"], req["case_id"], req["request_id"], ACTION_CODE[action], True,
                        f"{action} للمستند {doc_id} ({doc['document_type']})")
    except BaseException:
        if remote:
            private_storage.discard(path)
        raise
    return doc, path
