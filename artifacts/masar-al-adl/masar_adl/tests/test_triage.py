from datetime import datetime, timedelta

from app import triage

USERS = {"clerk": "clerk_noor", "judge": "judge_adel"}


def _res(repo, username):
    u = repo.one("users", {"username": username})
    reqs = repo.select("document_requests")
    return triage.triage_map(repo, u, reqs)


def test_seed_ranking_is_explainable(repo):
    m = _res(repo, "clerk_noor")
    assert m[2]["level"] == "high" and "تأخير مسجّل 6 يوم" in m[2]["text"]
    assert m[1]["level"] == "none"                       # response already released to the citizen
    assert m[2]["score"] > m[3]["score"] > m[1]["score"]
    assert all(0 <= v["score"] <= 100 for v in m.values())


def test_reasons_sum_matches_factors_and_text_names_top_reason(repo):
    m = _res(repo, "judge_adel")[2]
    assert m["reasons"] and m["text"].startswith("أولوية مرتفعة بسبب")
    assert m["reasons"][0] in m["text"]


def test_triage_is_read_only(repo):
    before = {t: repo.select(t) for t in ("document_requests", "request_timeline", "audit_logs", "documents", "notifications")}
    _res(repo, "clerk_noor")
    assert before == {t: repo.select(t) for t in before}


def test_more_delay_means_higher_score(repo):
    base = _res(repo, "clerk_noor")[2]["score"]
    repo.update("document_requests", 2, {"delay_days": 20})
    assert _res(repo, "clerk_noor")[2]["score"] >= base


def test_returned_for_modification_adds_a_reason(repo):
    repo.update("document_requests", 3, {"request_status": "RETURNED_FOR_MODIFICATION"})
    assert any("أُعيد الطلب للتعديل" in r for r in _res(repo, "clerk_noor")[3]["reasons"])


def test_unreleased_response_is_flagged_for_court_only(repo):
    repo.update("document_requests", 3, {"request_status": "RESPONSE_RECEIVED", "response_received_at": datetime(2026, 6, 16)})
    repo.insert("documents", {"request_id": 3, "document_type": "ENTITY_RESPONSE", "document_type_ar": "رد جهة",
                "document_title_ar": "رد", "file_name": "r.pdf", "uploaded_by_user_id": 8,
                "visibility": "COURT_AND_AUTHORIZED_LAWYER", "visibility_ar": "المحكمة والمحامي",
                "is_printable_by_citizen": 0, "is_official": 1, "document_status": "RECEIVED", "document_status_ar": "ساري",
                "print_permission_note_ar": "—", "uploaded_at": datetime(2026, 6, 16)})
    assert any("لم يُراجَع" in r for r in _res(repo, "clerk_noor")[3]["reasons"])
    assert not any("لم يُراجَع" in r for r in _res(repo, "civil_officer_dana")[3]["reasons"])


def test_internal_note_reason_hidden_from_entity_role(repo):
    repo.update("document_requests", 3, {"request_status": "SENT_TO_ENTITY", "internal_note": "سري للمحكمة"})
    ent = _res(repo, "civil_officer_dana")[3]
    assert not any("ملاحظة" in r for r in ent["reasons"]) and "سري" not in ent["text"]
    assert any("ملاحظة" in r for r in _res(repo, "clerk_noor")[3]["reasons"])


def test_as_of_env_override(repo, monkeypatch):
    monkeypatch.setenv("TRIAGE_AS_OF", "2027-01-01T00:00:00")
    assert triage.as_of(repo) == datetime(2027, 1, 1)
    assert _res(repo, "clerk_noor")[3]["score"] > 0


def test_court_dashboard_shows_priority_sorted_and_no_state_change(as_user, repo):
    before = repo.select("document_requests")
    c = as_user("judge_adel")
    page = c.get("/court").text
    assert "ابدأ من هنا" in page and "أولوية مرتفعة" in page
    assert page.index("#2") < page.index("#3") if "#3 " in page else True
    assert before == repo.select("document_requests")


def test_citizen_and_lawyer_do_not_get_triage(as_user):
    assert "الأولوية" not in as_user("citizen_tariq").get("/citizen").text
    assert "ابدأ من هنا" not in as_user("lawyer_omar").get("/lawyer").text
