"""Cloud behavior with a fake SDK only. No bucket, SQL or network is accessed."""
import hashlib
from pathlib import Path

import pytest
from replit.object_storage.errors import ObjectNotFoundError

from app import documents, private_storage
from app.main import create_app
from app.repositories import DemoRepository
from conftest import PDF, login, post


class FakeBucket:
    def __init__(self):
        self.files = {}
        self.calls = []
        self.failure = None

    def upload_from_bytes(self, key, data):
        self.calls.append(("upload", key))
        if self.failure:
            raise self.failure
        self.files[key] = data

    def download_as_bytes(self, key):
        self.calls.append(("download", key))
        if self.failure:
            raise self.failure
        if key not in self.files:
            raise ObjectNotFoundError("TEST missing object")
        return self.files[key]

    def exists(self, key):
        self.calls.append(("exists", key))
        if self.failure:
            raise self.failure
        return key in self.files


@pytest.fixture
def cloud(env, monkeypatch):
    _, _, settings = env
    settings.pdf_storage_backend = "app_storage"
    settings.pdf_storage_bucket = "TEST-bucket-not-real"
    bucket = FakeBucket()
    monkeypatch.setattr(private_storage, "_client", lambda name: bucket)
    repo = DemoRepository()
    app = create_app(settings, repo=repo)
    return app, repo, settings, bucket


def attach_response(cloud):
    _, repo, settings, bucket = cloud
    reference = documents.save_pdf(settings, PDF)
    repo.update("documents", 2, {"file_name": reference})
    return reference


def transfers(settings):
    return list((settings.storage_dir / ".private-pdf-transfers").glob("*.pdf"))


def test_cloud_save_is_private_opaque_and_fits_the_existing_filename_column(cloud):
    _, _, settings, bucket = cloud
    reference = documents.save_pdf(settings, PDF)
    assert len(reference) <= 255
    assert private_storage.REFERENCE.fullmatch(reference)
    assert hashlib.sha256(PDF).hexdigest() in reference
    key = private_storage.object_key(settings, reference)
    assert key.startswith("masar-al-adl/private-pdfs/v1/demo/")
    assert bucket.files[key] == PDF
    assert not (settings.storage_dir / reference).exists()


@pytest.mark.parametrize("mode,disposition", [
    ("view", "inline"), ("download", "attachment"), ("raw?for=view", "inline"), ("raw?for=print", "inline"),
])
def test_cloud_pdf_keeps_headers_audit_and_removes_transfer_file(cloud, mode, disposition):
    app, repo, settings, bucket = cloud
    attach_response(cloud)
    response = login(app, "citizen_tariq").get(f"/documents/2/{mode}")
    assert response.status_code == 200 and response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith(disposition)
    assert response.headers["cache-control"] == "no-store"
    assert not transfers(settings)
    action = "DOWNLOAD_DOCUMENT" if mode == "download" else "PRINT_DOCUMENT" if "for=print" in mode else "VIEW_DOCUMENT"
    assert repo.select("audit_logs", {"actor_user_id": 1, "action_code": action, "result": "SUCCESS"})


@pytest.mark.parametrize("mode", ["view", "download", "print", "preview", "raw?for=view", "raw?for=print"])
def test_unrelated_citizen_cannot_trigger_cloud_io(cloud, mode):
    app, _, _, bucket = cloud
    attach_response(cloud)
    bucket.calls.clear()
    assert login(app, "citizen_layla").get(f"/documents/2/{mode}").status_code == 404
    assert bucket.calls == []


@pytest.mark.parametrize("mode", ["print", "raw?for=print"])
def test_print_denial_occurs_before_cloud_access(cloud, mode):
    app, repo, _, bucket = cloud
    attach_response(cloud)
    repo.update("documents", 2, {"is_printable_by_citizen": 0})
    bucket.calls.clear()
    assert login(app, "citizen_tariq").get(f"/documents/2/{mode}").status_code == 403
    assert bucket.calls == []


def test_unreleased_or_revoked_cloud_responses_stay_hidden(cloud):
    app, repo, _, bucket = cloud
    attach_response(cloud)
    repo.update("documents", 2, {"visibility": "COURT_AND_AUTHORIZED_LAWYER", "is_printable_by_citizen": 0})
    bucket.calls.clear()
    citizen = login(app, "citizen_tariq")
    assert citizen.get("/documents/2/view").status_code == 403
    assert bucket.calls == []
    repo.update("documents", 2, {"document_status": "REVOKED"})
    assert citizen.get("/documents/2/raw?for=view").status_code == 403
    assert bucket.calls == []


@pytest.mark.parametrize("mode", ["print", "preview"])
def test_html_pages_check_existence_without_creating_transfer_files(cloud, mode):
    app, _, settings, bucket = cloud
    attach_response(cloud)
    bucket.calls.clear()
    assert login(app, "citizen_tariq").get(f"/documents/2/{mode}").status_code == 200
    assert [method for method, _ in bucket.calls] == ["exists"]
    assert not transfers(settings)


def test_legacy_local_files_remain_available_without_touching_cloud(cloud):
    app, _, _, bucket = cloud
    response = login(app, "citizen_tariq").get("/documents/2/view")
    assert response.status_code == 200 and response.content.startswith(b"%PDF-")
    assert bucket.calls == []


def test_cloud_reference_remains_readable_when_new_writes_switch_to_local(cloud):
    app, _, settings, _ = cloud
    attach_response(cloud)
    settings.pdf_storage_backend = "local"
    assert login(app, "citizen_tariq").get("/documents/2/view").content == PDF


def test_missing_cloud_object_never_gets_a_fabricated_local_replacement(cloud):
    app, repo, settings, bucket = cloud
    reference = attach_response(cloud)
    bucket.files.clear()
    documents.ensure_demo_files(repo, settings)
    assert not (settings.storage_dir / reference).exists()
    assert login(app, "citizen_tariq").get("/documents/2/view").status_code == 404


def test_unavailable_cloud_returns_safe_503_not_a_stale_local_file(cloud):
    app, _, settings, bucket = cloud
    reference = attach_response(cloud)
    (settings.storage_dir / reference).write_bytes(PDF)
    bucket.failure = RuntimeError("TEST-sensitive-transport-detail")
    response = login(app, "citizen_tariq").get("/documents/2/view")
    assert response.status_code == 503
    assert "TEST-sensitive-transport-detail" not in response.text
    assert not transfers(settings)


@pytest.mark.parametrize("bad_data", [b"not PDF", PDF + b"corrupted"])
def test_hash_or_signature_mismatch_is_rejected_without_creating_cache(cloud, bad_data):
    app, _, settings, bucket = cloud
    reference = attach_response(cloud)
    bucket.files[private_storage.object_key(settings, reference)] = bad_data
    assert login(app, "citizen_tariq").get("/documents/2/view").status_code == 503
    assert not transfers(settings)


@pytest.mark.parametrize("reference", [
    "cloud-v1-../../private.pdf", "cloud-v1-demo-malformed.pdf",
    "cloud-v1-sqlserver-" + "a" * 32 + "-" + "b" * 64 + ".pdf",
])
def test_malformed_or_cross_environment_reference_never_accesses_cloud(cloud, reference):
    app, repo, _, bucket = cloud
    repo.update("documents", 2, {"file_name": reference})
    assert login(app, "citizen_tariq").get("/documents/2/view").status_code == 404
    assert bucket.calls == []


def test_failed_cloud_upload_rolls_back_the_request_and_has_no_local_fallback(cloud):
    app, repo, settings, bucket = cloud
    bucket.failure = RuntimeError("TEST upload unavailable")
    requests_before = len(repo.select("document_requests"))
    documents_before = len(repo.select("documents"))
    response = post(login(app, "lawyer_omar"), "/requests/new", {
        "case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
        "title": "TEST failed cloud upload", "intent": "draft",
    }, files={"file": ("TEST.pdf", PDF, "application/pdf")})
    assert response.status_code == 503
    assert len(repo.select("document_requests")) == requests_before
    assert len(repo.select("documents")) == documents_before
    assert "TEST upload unavailable" not in response.text
    assert not list(settings.storage_dir.glob("[a-f0-9]" * 32 + ".pdf"))


def test_audit_failure_removes_downloaded_transfer_file(cloud, monkeypatch):
    from app import audit
    _, repo, settings, _ = cloud
    attach_response(cloud)
    def fail(*args, **kwargs):
        raise RuntimeError("TEST audit failure")
    monkeypatch.setattr(audit, "write", fail)
    with pytest.raises(RuntimeError, match="TEST audit failure"):
        documents.open_document(repo, settings, repo.get("users", 1), 2, "view")
    assert not transfers(settings)


def test_cloud_files_are_not_mounted_under_static_or_storage(cloud):
    app, _, _, _ = cloud
    reference = attach_response(cloud)
    client = login(app, "citizen_tariq")
    for path in (f"/storage/{reference}", f"/static/{reference}", f"/objects/{reference}"):
        assert client.get(path).status_code == 404


def test_cloud_requires_explicit_bucket_and_valid_backend(env):
    _, _, settings = env
    settings.pdf_storage_backend = "app_storage"
    settings.pdf_storage_bucket = ""
    with pytest.raises(ValueError):
        create_app(settings, repo=DemoRepository())
    settings.pdf_storage_backend = "unrecognized"
    with pytest.raises(ValueError):
        create_app(settings, repo=DemoRepository())


def test_transfer_files_are_owner_only(cloud):
    _, repo, settings, _ = cloud
    attach_response(cloud)
    _, path = documents.open_document(repo, settings, repo.get("users", 1), 2, "view")
    assert path.stat().st_mode & 0o777 == 0o600
    private_storage.discard(path)
    assert not transfers(settings)


def test_response_disconnection_cleans_transfer_and_never_emits_pathsend(tmp_path):
    import asyncio
    from app.main import PrivatePDFResponse
    path = tmp_path / "TEST-response.pdf"
    path.write_bytes(PDF)
    response = PrivatePDFResponse(path, temporary=True, media_type="application/pdf")
    async def send(message):
        assert message["type"] != "http.response.pathsend"
        if message["type"] == "http.response.body":
            raise RuntimeError("TEST disconnected")
    async def receive():
        return {"type": "http.disconnect"}
    scope = {"type": "http", "method": "GET", "headers": [], "asgi": {"spec_version": "2.4"},
             "extensions": {"http.response.pathsend": {}}}
    with pytest.raises(RuntimeError, match="TEST disconnected"):
        asyncio.run(response(scope, receive, send))
    assert not path.exists()
