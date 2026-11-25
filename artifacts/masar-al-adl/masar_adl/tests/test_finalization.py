"""TEST-only PDF, private-file and restart-boundary regressions. No database IO."""
import hashlib
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app import documents
from conftest import PDF, flow_to_review


@pytest.mark.parametrize("username,code", [
    ("citizen_tariq", 200), ("citizen_layla", 404),
    ("lawyer_omar", 200), ("lawyer_sara", 404),
    ("clerk_noor", 200), ("judge_adel", 200),
    ("land_officer_rami", 200), ("civil_officer_dana", 404),
    ("gov_tax_fadi", 404), ("gov_gam_hana", 404),
])
def test_preview_uses_existing_document_authorization(as_user, username, code):
    assert as_user(username).get("/documents/2/preview").status_code == code


def test_preview_does_not_grant_print_or_download(as_user, repo):
    # Judge can view this TEST certificate, but cannot download it.
    judge = as_user("judge_adel")
    assert judge.get("/documents/3/preview").status_code == 200
    assert judge.get("/documents/3/download").status_code == 403
    citizen = as_user("citizen_tariq")
    repo.update("documents", 2, {"is_printable_by_citizen": 0})
    assert citizen.get("/documents/2/preview").status_code == 200
    assert citizen.get("/documents/2/print").status_code == 403
    assert citizen.get("/documents/2/raw?for=print").status_code == 403


def test_preview_rechecks_permission_and_logs_denials(as_user, repo):
    citizen = as_user("citizen_tariq")
    assert citizen.get("/documents/2/preview").status_code == 200
    repo.update("documents", 2, {"document_status": "REVOKED"})
    assert citizen.get("/documents/2/preview").status_code == 403
    assert citizen.get("/documents/2/raw?for=view").status_code == 403
    assert repo.select("audit_logs", {"actor_user_id": 1, "action_code": "VIEW_DOCUMENT", "result": "FAILURE"})


def test_preview_still_hides_an_unreleased_reply(as_user, repo):
    repo.update("documents", 2, {"is_printable_by_citizen": 0,
                               "visibility": "COURT_AND_AUTHORIZED_LAWYER"})
    assert as_user("citizen_tariq").get("/documents/2/preview").status_code == 403
    assert as_user("lawyer_omar").get("/documents/2/preview").status_code == 200


def test_preview_needs_login_and_original_pdf_contract_stays_intact(app_, as_user):
    from client import Client
    assert Client(app_).get("/documents/2/preview").location == "/login"
    response = as_user("citizen_tariq").get("/documents/2/view")
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert response.headers["cache-control"] == "no-store"


def test_pdf_library_is_local_and_only_allowlisted_files_are_served(app_, tmp_path, monkeypatch):
    import app.main as main
    from client import Client
    # Keep Python-only installs testable; browser tests exercise the real bundle.
    bundle = tmp_path / "TEST-library"
    bundle.mkdir()
    for name in main.PDFJS_ASSETS.values():
        (bundle / name).write_text("/* TEST library fixture */", encoding="utf-8")
    monkeypatch.setattr(main, "PDFJS_DIR", bundle)
    client = Client(app_)
    for name in ("pdf.mjs", "pdf.worker.mjs"):
        response = client.get(f"/static/vendor/pdfjs/{name}")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]
    for name in ("package.json", "pdf.mjs.map", "documents.pdf", "pdf.sandbox.mjs"):
        assert client.get(f"/static/vendor/pdfjs/{name}").status_code == 404


def test_missing_optional_pdf_bundle_preserves_original_pdf_and_print(as_user, tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "PDFJS_DIR", tmp_path / "TEST-uninstalled")
    citizen = as_user("citizen_tariq")
    page = citizen.get("/documents/2/print")
    assert page.status_code == 200
    assert "مكتبة المعاينة المحلية غير مثبّتة" in page.text
    assert '<iframe class="pdf"' in page.text
    assert citizen.get("/documents/2/view").content.startswith(b"%PDF-")


def test_private_save_uses_owner_only_permissions_and_no_overwrite(tmp_path, monkeypatch):
    settings = SimpleNamespace(storage_dir=tmp_path / "TEST-private")
    class FixedID:
        hex = "test-only-collision"
    monkeypatch.setattr(documents.uuid, "uuid4", lambda: FixedID())
    name = documents.save_pdf(settings, PDF)
    file = settings.storage_dir / name
    assert file.read_bytes() == PDF
    assert file.stat().st_mode & 0o777 == 0o600
    assert settings.storage_dir.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        documents.save_pdf(settings, b"must not overwrite")
    assert file.read_bytes() == PDF


def test_disk_write_failure_leaves_no_partial_upload(tmp_path, monkeypatch):
    settings = SimpleNamespace(storage_dir=tmp_path / "TEST-failed-write")
    def failed_sync(fd):
        raise OSError("TEST simulated disk failure")
    monkeypatch.setattr(documents.os, "fsync", failed_sync)
    with pytest.raises(OSError, match="TEST"):
        documents.save_pdf(settings, PDF)
    assert not list(settings.storage_dir.iterdir())


def test_new_upload_does_not_follow_a_preexisting_symlink(tmp_path, monkeypatch):
    settings = SimpleNamespace(storage_dir=tmp_path / "TEST-private")
    settings.storage_dir.mkdir()
    target = tmp_path / "TEST-untouched.pdf"
    target.write_bytes(b"TEST untouched")
    class FixedID:
        hex = "test-only-symlink"
    monkeypatch.setattr(documents.uuid, "uuid4", lambda: FixedID())
    (settings.storage_dir / "test-only-symlink.pdf").symlink_to(target)
    with pytest.raises(FileExistsError):
        documents.save_pdf(settings, PDF)
    assert target.read_bytes() == b"TEST untouched"


def test_private_pdf_survives_a_fresh_python_process_on_same_disk(tmp_path):
    # Deliberately not a claim of cloud/redeploy durability or retained metadata.
    directory = tmp_path / "TEST-restart"
    writer = (
        "import sys; from pathlib import Path; from types import SimpleNamespace; "
        "from app.documents import save_pdf; "
        f"print(save_pdf(SimpleNamespace(storage_dir=Path(sys.argv[1])), {PDF!r}))"
    )
    # The actual writer exits completely before the independent reader starts.
    saved = subprocess.run([sys.executable, "-c", writer, str(directory)],
                           check=True, text=True, capture_output=True)
    name = saved.stdout.strip()
    code = (
        "import hashlib,sys; from pathlib import Path; "
        "print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())"
    )
    result = subprocess.run([sys.executable, "-c", code, str(directory / name)],
                            check=True, text=True, capture_output=True)
    assert result.stdout.strip() == hashlib.sha256(PDF).hexdigest()


def test_fresh_demo_application_does_not_pretend_uploaded_metadata_is_durable(env, as_user):
    from app.main import create_app
    from app.repositories import DemoRepository
    app, repo, settings = env
    _, rid = flow_to_review(as_user, repo)
    doc = repo.one("documents", {"request_id": rid, "document_type": "LAWYER_REQUEST_PDF"})
    path = documents._path(settings, doc["file_name"])
    original = path.read_bytes()
    fresh = create_app(settings, repo=DemoRepository())
    assert path.read_bytes() == original
    assert fresh.state.repo.get("document_requests", rid) is None
    assert fresh.state.repo.get("documents", doc["document_id"]) is None


def test_incomplete_storage_does_not_expose_private_files(as_user, settings):
    citizen = as_user("citizen_tariq")
    for path in ("/storage/resp_1041_dls_extract_test.pdf",
                 "/static/storage/resp_1041_dls_extract_test.pdf",
                 "/documents/2/unknown"):
        assert citizen.get(path).status_code == 404
