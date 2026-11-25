"""Additional regressions. Original test coverage is retained, not replaced."""
import asyncio
import hashlib
import re
from pathlib import Path

import httpx
from fastapi import FastAPI

from app.auth import make_pin_hash, verify_pin
from app.documents import ensure_demo_files, sample_pdf_bytes
from client import Client
from conftest import act, flow_to_review


def test_application_is_fastapi(app_):
    assert isinstance(app_, FastAPI)
    assert Client(app_).get("/health").status_code == 200


def test_new_hashes_use_argon2id():
    hashed = make_pin_hash("test-only-password")
    assert hashed.startswith("$argon2id$")
    assert verify_pin("test-only-password", hashed)
    assert not verify_pin("wrong", hashed)


def test_legacy_scrypt_hash_remains_supported():
    salt = bytes(range(16))
    value = hashlib.scrypt(b"legacy-test-value", salt=salt, n=16384, r=8, p=1, dklen=32)
    stored = f"scrypt$16384$8$1${salt.hex()}${value.hex()}"
    assert verify_pin("legacy-test-value", stored)
    assert not verify_pin("incorrect", stored)
    assert not verify_pin("anything", "invalid")
    assert not verify_pin("anything", None)


def test_direct_raw_pdf_access_is_audited(as_user, repo):
    citizen = as_user("citizen_tariq")
    before = len(repo.select("audit_logs", {"actor_user_id": 1, "action_code": "VIEW_DOCUMENT"}))
    assert citizen.get("/documents/2/raw").status_code == 200
    rows = repo.select("audit_logs", {"actor_user_id": 1, "action_code": "VIEW_DOCUMENT"})
    assert len(rows) == before + 1 and rows[-1]["result"] == "SUCCESS"


def test_real_database_never_gets_synthetic_documents(repo, settings, monkeypatch):
    settings.storage_dir = settings.storage_dir / "live-private-storage"
    monkeypatch.setattr(repo, "mode", "sqlserver")
    ensure_demo_files(repo, settings)
    assert not settings.storage_dir.exists()


def test_demo_pdf_has_embedded_arabic_font():
    pdf = sample_pdf_bytes("test")
    assert pdf.startswith(b"%PDF-") and b"%%EOF" in pdf
    assert b"/FontFile2" in pdf and b"/ToUnicode" in pdf


def test_https_login_sets_secure_cookie(app_):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_),
                                    base_url="https://testserver") as client:
            login_page = await client.get("/login")
            token = re.search(r'name="login_token" value="([^"]+)"', login_page.text).group(1)
            response = await client.post("/demo-login", data={
                "login_token": token, "username": "citizen_tariq",
            })
            assert response.status_code == 303
            assert "secure" in response.headers["set-cookie"].lower()
    asyncio.run(scenario())


def test_judge_approval_requires_reason_and_audits_failure(as_user, repo):
    _, rid = flow_to_review(as_user, repo)
    act(as_user("clerk_noor"), rid, "start_review")
    judge = as_user("judge_adel")
    assert act(judge, rid, "approve").status_code == 303
    assert repo.get("document_requests", rid)["request_status"] == "UNDER_COURT_REVIEW"
    assert repo.select("audit_logs", {
        "request_id": rid, "action_code": "APPROVE_DOCUMENT_REQUEST", "result": "FAILURE",
    })
    act(judge, rid, "approve", reason="مراجعة مستوفاة")
    req = repo.get("document_requests", rid)
    assert req["request_status"] == "APPROVED" and req["court_decision_at"]
    assert "مراجعة مستوفاة" in req["internal_note"]
    assert "مراجعة مستوفاة" not in as_user("citizen_tariq").get(f"/requests/{rid}").text


def test_bad_delay_inputs_are_audited(as_user, repo):
    staff = as_user("gov_gam_hana")
    act(staff, 2, "resume")
    assert repo.get("document_requests", 2)["request_status"] == "UNDER_PROCESSING"
    act(staff, 2, "mark_delayed", delay_days="invalid", delay_reason_code="ENTITY_QUEUE_BACKLOG")
    assert repo.get("document_requests", 2)["request_status"] == "UNDER_PROCESSING"
    assert repo.select("audit_logs", {
        "request_id": 2, "action_code": "MARK_REQUEST_DELAYED", "result": "FAILURE",
    })


def test_entity_cannot_open_court_and_lawyer_only_response(as_user, repo):
    repo.update("documents", 2, {
        "visibility": "COURT_AND_AUTHORIZED_LAWYER", "is_printable_by_citizen": 0,
    })
    assert as_user("land_officer_rami").get("/documents/2/view").status_code == 403
    assert as_user("lawyer_omar").get("/documents/2/view").status_code == 200


def test_disabled_entity_invalidates_existing_session(as_user, repo):
    officer = as_user("land_officer_rami")
    repo.update("government_entities", 2, {"is_active": 0})
    response = officer.get("/entity")
    assert response.status_code == 303 and response.location == "/login"


def test_oversized_login_input_is_generic(app_):
    client = Client(app_)
    token = re.search(r'name="login_token" value="([^"]+)"', client.get("/login").text).group(1)
    result = client.post("/login", {
        "login_token": token, "national_id": "x" * 1000, "password": "not-a-real-password",
    })
    assert result.status_code == 401
    assert "بيانات الدخول غير صحيحة" in result.text
    assert "x" * 100 not in result.text


def test_templates_work_under_strict_csp():
    root = Path(__file__).resolve().parent.parent / "app" / "templates"
    for file in root.glob("*.html"):
        text = file.read_text()
        assert not re.search(r'\bstyle\s*=', text, flags=re.I), file.name
        assert not re.search(r'\bon(?:click|submit|load|error)\s*=', text, flags=re.I), file.name
        for attributes, body in re.findall(r"<script\b([^>]*)>(.*?)</script>", text, flags=re.S):
            assert "src=" in attributes and not body.strip(), file.name


def test_clerk_is_not_offered_judge_decisions(as_user, repo):
    _, rid = flow_to_review(as_user, repo)
    clerk = as_user("clerk_noor")
    act(clerk, rid, "start_review")
    clerk_page = clerk.get(f"/requests/{rid}").text
    assert 'name="action" value="approve"' not in clerk_page
    assert 'name="action" value="reject"' not in clerk_page
    judge_page = as_user("judge_adel").get(f"/requests/{rid}").text
    assert 'name="action" value="approve"' in judge_page
    assert 'name="reason"' in judge_page


def test_release_action_requires_a_pending_response(as_user, repo):
    from conftest import PDF, act, flow_to_review

    # The seed response is already released, so neither court role should see
    # a release action. Server-side duplicate-release rejection remains intact.
    for username in ("clerk_noor", "judge_adel"):
        page = as_user(username).get("/requests/1").text
        assert 'name="action" value="release_response"' not in page

    _, rid = flow_to_review(as_user, repo)
    clerk, judge = as_user("clerk_noor"), as_user("judge_adel")
    act(clerk, rid, "start_review")
    act(judge, rid, "approve", reason="TEST سبب موافقة")
    act(clerk, rid, "send")
    officer = as_user("civil_officer_dana")
    act(officer, rid, "upload_response", files={"file": ("TEST-response.pdf", PDF, "application/pdf")})
    marker = 'name="action" value="release_response"'
    assert marker in clerk.get(f"/requests/{rid}").text
    assert marker in judge.get(f"/requests/{rid}").text
    act(clerk, rid, "release_response")
    assert marker not in clerk.get(f"/requests/{rid}").text
    assert marker not in judge.get(f"/requests/{rid}").text
    duplicate = act(clerk, rid, "release_response")
    assert duplicate.status_code == 303
    assert "لا يوجد رد بانتظار الإتاحة" in clerk.get(f"/requests/{rid}").text


def test_released_responses_are_not_in_pending_release_queue(as_user):
    from html.parser import HTMLParser

    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data.strip())

    page = as_user("clerk_noor").get("/court").text
    parser = Text()
    parser.feed(page)
    text = " ".join(parser.parts)
    # Seed response 1 is already published; pending-release stat must be zero.
    assert re.search(r"0\s+ردود بانتظار الإتاحة", text)
