from app import integrity
from conftest import act


def test_seed_findings_match_known_anomalies(repo):
    f = integrity.run(repo)
    rules = {(x["rule"], x["request_id"]) for x in f}
    assert any(r == "R8" for r, _ in rules)               # seed audit #4 anomaly
    assert all(x["severity"] in ("high", "medium", "low") for x in f)
    assert f == sorted(f, key=lambda x: ({"high": 0, "medium": 1, "low": 2}[x["severity"]], x["request_id"] or 0))


def test_integrity_is_read_only(repo):
    before = {t: repo.select(t) for t in ("document_requests", "request_timeline", "audit_logs", "documents")}
    integrity.run(repo)
    integrity.custody_report(repo, repo.select("document_requests")[0])
    assert before == {t: repo.select(t) for t in before}


def test_integrity_page_judge_sees_all_and_clerk_scoped(as_user, repo):
    judge = as_user("judge_adel")
    r = judge.get("/integrity")
    assert r.status_code == 200 and "مدقق سلامة المسار" in r.text
    clerk = as_user("clerk_noor")
    assert clerk.get("/integrity").status_code == 200
    scope = integrity.scope_cases(repo, repo.select("users", {"username": "clerk_noor"})[0])
    assert scope is not None and len(integrity.run(repo, scope)) <= len(integrity.run(repo))


def test_integrity_forbidden_for_non_court_roles(as_user):
    for u in ("citizen_tariq", "lawyer_omar", "land_officer_rami"):
        c = as_user(u)
        assert c.get("/integrity").status_code == 403
        assert c.get("/integrity/requests/1").status_code == 403


def test_custody_report_and_unknown_request(as_user):
    judge = as_user("judge_adel")
    r = judge.get("/integrity/requests/1")
    assert r.status_code == 200 and "سلسلة الحفظ" in r.text
    assert judge.get("/integrity/requests/99999").status_code == 404
    assert judge.get("/integrity/requests/abc").status_code == 404


def test_clean_workflow_produces_no_high_findings_for_new_request(as_user, repo):
    from conftest import flow_to_review
    rid = flow_to_review(as_user, repo)
    high = [x for x in integrity.run(repo) if x["request_id"] == rid and x["severity"] == "high"]
    assert high == []


def test_checker_detects_injected_inconsistency(repo):
    req = repo.select("document_requests")[0]
    repo.update("document_requests", req["request_id"],
                {"request_status": "RESPONSE_RECEIVED", "response_received_at": None})
    f = integrity.run(repo)
    assert any(x["request_id"] == req["request_id"] and x["rule"] in ("R2", "R3") for x in f)
