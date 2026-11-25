"""Role-specific HTTP journeys against isolated demo fixtures, never live SQL."""
import re

import pytest

from app.workflow import request_type_options
from conftest import PDF, act, post


ACCOUNTS = [
    ("citizen_tariq", "/citizen", (1,), (1, 2)),
    ("citizen_layla", "/citizen", (2,), (3,)),
    ("lawyer_omar", "/lawyer", (1,), (1, 2)),
    ("lawyer_sara", "/lawyer", (2,), (3,)),
    ("clerk_noor", "/court", (1, 2), (1, 2, 3)),
    ("judge_adel", "/court", (1, 2), (1, 2, 3)),
    ("land_officer_rami", "/entity", (), (1,)),
    ("civil_officer_dana", "/entity", (), ()),
    ("gov_tax_fadi", "/entity", (), ()),
    ("gov_gam_hana", "/entity", (), (2,)),
]


@pytest.mark.parametrize("username,home,cases,requests", ACCOUNTS)
def test_exact_role_navigation_and_record_scope(as_user, username, home, cases, requests):
    client = as_user(username)
    assert client.get("/").location == home
    page = client.get(home)
    assert page.status_code == 200
    assert '<html lang="ar" dir="rtl">' in page.text
    assert 'id="menu-btn"' in page.text and 'aria-controls="topnav"' in page.text
    for dashboard in ("/citizen", "/lawyer", "/court", "/entity"):
        assert client.get(dashboard).status_code == (200 if dashboard == home else 403)
    for case_id in (1, 2):
        assert client.get(f"/cases/{case_id}").status_code == (200 if case_id in cases else 404)
    for request_id in (1, 2, 3):
        assert client.get(f"/requests/{request_id}").status_code == (200 if request_id in requests else 404)
    is_court = home == "/court"
    for path in ("/audit", "/integrity"):
        assert client.get(path).status_code == (200 if is_court else 403)
    assert client.get("/requests/new").status_code == (200 if home == "/lawyer" else 403)
    assert client.get("/notifications").status_code == 200
    assert post(client, "/logout").status_code == 303
    assert client.get(home).location == "/login"


@pytest.mark.parametrize("username,_,__,___", ACCOUNTS)
def test_mark_notifications_read_only_changes_current_account(as_user, repo, username, _, __, ___):
    user = repo.one("users", {"username": username})
    others = [n for n in repo.select("notifications") if n["user_id"] != user["user_id"]]
    client = as_user(username)
    assert post(client, "/notifications/read").status_code == 303
    assert all(n["is_read"] for n in repo.select("notifications", {"user_id": user["user_id"]}))
    assert [n for n in repo.select("notifications") if n["user_id"] != user["user_id"]] == others


def test_missing_pdf_submission_recovers_on_saved_draft(as_user, repo):
    lawyer = as_user("lawyer_omar")
    response = post(lawyer, "/requests/new", {
        "case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
        "title": "طلب محفوظ دون مرفق", "intent": "submit",
    })
    rid = max(r["request_id"] for r in repo.select("document_requests"))
    assert response.status_code == 303 and response.location == f"/requests/{rid}"
    assert repo.get("document_requests", rid)["request_status"] == "DRAFT"
    page = lawyer.get(response.location)
    assert "حُفظت المسودة، ولم يُقدَّم الطلب" in page.text
    assert f'action="/requests/{rid}/pdf"' in page.text
    assert as_user("citizen_tariq").get(response.location).status_code == 404
    assert post(lawyer, f"/requests/{rid}/pdf",
                files={"file": ("request.pdf", PDF, "application/pdf")}).status_code == 303
    assert act(lawyer, rid, "submit").status_code == 303
    assert repo.get("document_requests", rid)["request_status"] == "SUBMITTED"


@pytest.mark.parametrize("officer", [
    "land_officer_rami", "civil_officer_dana", "gov_tax_fadi", "gov_gam_hana",
])
def test_each_entity_can_process_only_its_own_sent_request(as_user, repo, officer):
    user = repo.one("users", {"username": officer})
    lawyer = as_user("lawyer_omar")
    request_type = request_type_options(repo, user["entity_id"])[0][0]
    response = post(lawyer, "/requests/new", {
        "case_id": 1, "entity_id": user["entity_id"], "request_type": request_type,
        "title": "اختبار مسار الجهة المختصة", "intent": "submit",
    }, files={"file": ("request.pdf", PDF, "application/pdf")})
    rid = int(response.location.rsplit("/", 1)[1])
    clerk, judge = as_user("clerk_noor"), as_user("judge_adel")
    entity = as_user(officer)
    assert entity.get(f"/requests/{rid}").status_code == 404
    assert act(clerk, rid, "start_review").status_code == 303
    assert act(judge, rid, "approve", reason="مستوفٍ للشروط").status_code == 303
    assert act(clerk, rid, "send").status_code == 303
    page = entity.get(f"/requests/{rid}")
    assert page.status_code == 200
    assert not re.search(r'href="/cases/\d+"', page.text)
    outsider = as_user("gov_tax_fadi" if officer != "gov_tax_fadi" else "land_officer_rami")
    assert outsider.get(f"/requests/{rid}").status_code == 404
    assert act(outsider, rid, "start_processing").status_code == 404
    assert act(entity, rid, "start_processing").status_code == 303
    assert repo.get("document_requests", rid)["request_status"] == "UNDER_PROCESSING"
    assert act(entity, rid, "upload_response",
               files={"file": ("response.pdf", PDF, "application/pdf")}).status_code == 303
    assert repo.get("document_requests", rid)["request_status"] == "RESPONSE_RECEIVED"
    doc = repo.one("documents", {"request_id": rid, "document_type": "ENTITY_RESPONSE"})
    citizen = as_user("citizen_tariq")
    url = f"/documents/{doc['document_id']}/view"
    assert citizen.get(url).status_code == 403
    assert 'name="action" value="release_response"' in clerk.get(f"/requests/{rid}").text
    assert act(clerk, rid, "release_response").status_code == 303
    assert citizen.get(url).status_code == 200
    assert 'name="action" value="release_response"' not in clerk.get(f"/requests/{rid}").text


def test_invalid_pdf_preserves_escaped_form_fields(as_user, repo):
    lawyer = as_user("lawyer_omar")
    title = 'طلب <script>alert("x")</script>'
    before = repo.select("document_requests")
    response = post(lawyer, "/requests/new", {
        "case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
        "title": title, "intent": "submit",
    }, files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    assert response.status_code == 422
    assert 'value="1" selected' in response.text
    assert 'value="3" selected' in response.text
    assert 'data-selected-type="CIVIL_RECORD_CHECK"' in response.text
    assert '&lt;script&gt;' in response.text and title not in response.text
    assert "أعد اختيار ملف PDF" in response.text
    assert repo.select("document_requests") == before
    assert post(lawyer, "/requests/new", {
        "case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
        "title": "طلب صحيح بعد تصحيح المرفق", "intent": "submit",
    }, files={"file": ("ok.pdf", PDF, "application/pdf")}).status_code == 303
