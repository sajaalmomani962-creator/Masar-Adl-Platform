import re
from pathlib import Path

import pytest

from app.fixtures import EXPECTED_COUNTS
from client import Client
from conftest import PDF, act, flow_to_review, post


# ---------- seed parity ----------
def test_demo_matches_seed_counts_and_ids(repo):
    assert {t: len(repo.select(t)) for t in EXPECTED_COUNTS} == EXPECTED_COUNTS
    assert EXPECTED_COUNTS == {"government_entities": 8, "users": 10, "cases": 2, "case_parties": 5,
                               "document_requests": 3, "documents": 3, "request_timeline": 4, "audit_logs": 4,
                               "notifications": 3, "document_permissions": 15}
    assert repo.get("users", 7)["username"] == "land_officer_rami" and repo.get("users", 7)["entity_id"] == 2


def test_seed_file_values_match_sql_file(repo):
    """Cross-check: every username / case number in the SQL seed exists in the fixture."""
    sql = (Path(__file__).resolve().parent.parent / "db" / "judicial_exchange_seed_data.sql").read_text(encoding="utf-8")
    for u in re.findall(r"N'((?:citizen|lawyer|clerk|judge|land_officer|civil_officer|gov)_[a-z_]+)'", sql):
        assert repo.one("users", {"username": u}), u
    for n in re.findall(r"N'(2026-CIV-\d+)'", sql):
        assert repo.one("cases", {"case_number": n}), n


def test_app_never_executes_sql_scripts():
    root = Path(__file__).resolve().parent.parent / "app"
    for p in root.rglob("*.py"):
        txt = p.read_text(encoding="utf-8")
        assert not re.search(r"(open|read_text|read_bytes)\(.*\.sql", txt), p
        for ddl in ("CREATE TABLE", "CREATE DATABASE", "DROP TABLE", "ALTER TABLE"):
            assert ddl not in txt.upper().replace("# ", ""), (p, ddl)


def test_demo_repo_enforces_schema_constraints(repo):
    with pytest.raises(ValueError):
        repo.insert("audit_logs", {"actor_user_id": 1, "case_id": None, "action_code": "X", "result": "SUCCESS", "details": "d"})
    with pytest.raises(ValueError):
        repo.insert("users", {"national_id": "N1", "username": "u1", "display_name": "x", "role": "SYSTEM_ADMIN", "role_ar": "x"})
    with pytest.raises(ValueError):
        repo.update("documents", 1, {"is_printable_by_citizen": 1})      # visibility is COURT_AND_AUTHORIZED_LAWYER
    with pytest.raises(ValueError):
        repo.insert("audit_logs", {"actor_user_id": 1, "case_id": 1, "action_code": "X", "result": "DENIED", "details": "d"})


# ---------- citizen summary on seed + workflow-produced states ----------
def test_summary_seed_states(as_user):
    tariq = as_user("citizen_tariq")
    page = tariq.get("/citizen").text
    assert "تم استلام رد دائرة الأراضي وإرفاقه بملف الدعوى." in page          # request 1: response received
    assert "تأخير مسجّل" in page and "6 يوم" in page                          # request 2: delayed
    assert "ازدحام في قائمة الانتظار" in page and "ليست مهلة قانونية" in page
    assert "الرد مطابق للبيانات" not in page and "تم إرسال تنبيه متابعة" not in page   # internal notes never shown
    assert "الملخص العام" in page and "دعوى إثبات ملكية" in page
    layla = as_user("citizen_layla").get("/citizen").text                    # request 3: approved, no timeline
    assert "تمت موافقة المحكمة على الكتاب وجارٍ إرساله للأحوال المدنية." in layla
    assert "لا توجد أحداث متاحة" in layla


def test_summary_under_review_and_returned(as_user, repo):
    omar, rid = flow_to_review(as_user, repo)
    noor = as_user("clerk_noor")
    act(noor, rid, "start_review")
    assert "الطلب قيد المراجعة لدى المحكمة." in as_user("citizen_tariq").get("/citizen").text
    act(noor, rid, "return", reason="نقص")
    page = as_user("citizen_tariq").get("/citizen").text
    assert "أُعيد الطلب إلى المحامي لاستكمال متطلباته." in page and "نقص" not in page


def test_notifications_page(as_user, repo):
    c = as_user("citizen_tariq")
    assert "تم استلام رد دائرة الأراضي" in c.get("/notifications").text
    post(c, "/notifications/read")
    assert all(n["is_read"] == 1 for n in repo.select("notifications", {"user_id": 1}))
    assert as_user("citizen_layla").get("/notifications").text.count("اعتماد طلب كتاب") == 0   # not Layla's


# ---------- security ----------
def test_csrf_required_on_post(as_user, repo):
    c = as_user("clerk_noor")
    r = c.post("/requests/3/action", {"action": "send"})
    assert r.status_code == 403 and repo.get("document_requests", 3)["request_status"] == "APPROVED"
    r = c.post("/requests/3/action", {"action": "send", "csrf": "forged"})
    assert r.status_code == 403
    assert c.post("/logout", {}).status_code == 403


def test_security_headers_and_no_store(as_user):
    r = as_user("citizen_tariq").get("/citizen")
    h = r.headers
    assert h["x-content-type-options"] == "nosniff" and "frame-ancestors" in h["content-security-policy"]
    assert h["cache-control"] == "no-store"


def test_errors_do_not_leak(as_user, repo):
    c = as_user("citizen_tariq")
    for p in ("/nope", "/requests/abc", "/cases/99999", "/requests/3"):
        r = c.get(p)
        assert r.status_code in (404, 403)
        assert "Traceback" not in r.text and "SELECT" not in r.text and "internal_note" not in r.text


def test_sql_injection_strings_are_inert(as_user, repo):
    c = as_user("judge_adel")
    r = c.get("/audit?action=%27%3BDROP%20TABLE%20users%3B--&actor=1%20OR%201%3D1")
    assert r.status_code == 200 and len(repo.select("users")) == 10
    assert as_user("citizen_tariq").get("/cases/1%20OR%201=1").status_code == 404


def test_xss_escaped(as_user, repo):
    omar = as_user("lawyer_omar")
    post(omar, "/requests/new", {"case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
                                 "title": "<script>alert(1)</script> عنوان", "intent": "draft"})
    rid = max(x["request_id"] for x in repo.select("document_requests"))
    html = omar.get(f"/requests/{rid}").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


def test_health_and_demo_banner(as_user, app_):
    r = Client(app_).get("/health")
    assert r.status_code == 200 and '"data_mode":"demo"' in r.text.replace(" ", "")
    assert "وضع تجريبي" in as_user("citizen_tariq").get("/citizen").text


def test_demo_reset(as_user, repo):
    c = as_user("clerk_noor")
    act(c, 3, "send")
    assert repo.get("document_requests", 3)["request_status"] == "SENT_TO_ENTITY"
    post(c, "/demo/reset")
    assert repo.get("document_requests", 3)["request_status"] == "APPROVED"


def test_log_masks_national_id(app_, tmp_path):
    from app import audit
    assert audit.mask_id("TEST-NID-9901001001").endswith("1001") and "9901" not in audit.mask_id("TEST-NID-9901001001")[:-4]


def test_every_page_renders_for_every_role(as_user):
    users = ["citizen_tariq", "citizen_layla", "lawyer_omar", "lawyer_sara", "clerk_noor", "judge_adel",
             "land_officer_rami", "civil_officer_dana", "gov_tax_fadi", "gov_gam_hana"]
    for u in users:
        c = as_user(u)
        for p in ("/", "/notifications", "/requests/new", "/audit", "/cases/1", "/cases/2", "/requests/1",
                  "/requests/2", "/requests/3", "/citizen", "/lawyer", "/court", "/entity"):
            r = c.get(p, follow=True)
            assert r.status_code in (200, 403, 404), (u, p, r.status_code)
            assert "Traceback" not in r.text and r.status_code != 500, (u, p)
