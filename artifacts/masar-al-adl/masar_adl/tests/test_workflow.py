from conftest import PDF, act, audit_rows, flow_to_review, post


def status(repo, rid):
    return repo.get("document_requests", rid)["request_status"]


def test_full_lifecycle_with_court_release(as_user, repo):
    omar, rid = flow_to_review(as_user, repo)
    noor, adel, dana = as_user("clerk_noor"), as_user("judge_adel"), as_user("civil_officer_dana")
    tariq = as_user("citizen_tariq")
    assert status(repo, rid) == "SUBMITTED"
    assert act(noor, rid, "start_review").status_code == 303 and status(repo, rid) == "UNDER_COURT_REVIEW"
    assert act(noor, rid, "approve").status_code == 403                      # clerk: judge decision -> needs approval
    assert ("APPROVE_DOCUMENT_REQUEST", "FAILURE") in [(a["action_code"], a["result"]) for a in audit_rows(repo, actor_user_id=5)]
    assert status(repo, rid) == "UNDER_COURT_REVIEW"
    act(adel, rid, "approve", reason="الطلب مستوفٍ للمتطلبات")
    assert status(repo, rid) == "APPROVED" and repo.get("document_requests", rid)["court_decision_by_user_id"] == 6
    assert dana.get(f"/requests/{rid}").status_code == 404                   # entity cannot see before sending
    act(noor, rid, "send")
    r = repo.get("document_requests", rid)
    assert r["request_status"] == "SENT_TO_ENTITY" and r["sent_to_entity_at"]
    assert dana.get(f"/requests/{rid}").status_code == 200
    act(dana, rid, "start_processing")
    act(dana, rid, "mark_delayed", delay_days="4", delay_reason_code="MISSING_INFORMATION")
    r = repo.get("document_requests", rid)
    assert r["request_status"] == "DELAYED" and r["delay_days"] == 4
    assert "تأخير" in tariq.get(f"/requests/{rid}").text
    act(dana, rid, "resume")
    act(dana, rid, "upload_response", files={"file": ("resp.pdf", PDF, "application/pdf")})
    assert status(repo, rid) == "RESPONSE_RECEIVED"
    doc = [d for d in repo.select("documents", {"request_id": rid}) if d["document_type"] == "ENTITY_RESPONSE"][0]
    # not yet released: citizen cannot get it, lawyer can
    assert tariq.get(f"/documents/{doc['document_id']}/view").status_code == 403
    assert omar.get(f"/documents/{doc['document_id']}/view").status_code == 200
    assert act(tariq, rid, "release_response").status_code in (403, 404)
    act(noor, rid, "release_response")
    assert tariq.get(f"/documents/{doc['document_id']}/view").status_code == 200
    assert tariq.get(f"/documents/{doc['document_id']}/print").status_code == 200
    # notifications reached the right people, citizen only for citizen-visible events
    n_cit = repo.select("notifications", {"user_id": 1})
    assert any(n["request_id"] == rid and n["notification_type"] == "RESPONSE_AVAILABLE" for n in n_cit)
    assert not any(n["request_id"] == rid and n["notification_type"] == "RESPONSE_PENDING_RELEASE" for n in n_cit)
    assert any(n["user_id"] == 3 and n["request_id"] == rid for n in repo.select("notifications"))
    # timeline: citizen sees only citizen-visible events; every transition is audited
    tl = repo.select("request_timeline", {"request_id": rid})
    hidden = [t for t in tl if not t["is_visible_to_citizen"]]
    page = tariq.get(f"/requests/{rid}").text
    assert all(t["event_description_ar"] not in page for t in hidden) and hidden
    assert len([a for a in audit_rows(repo, request_id=rid) if a["result"] == "SUCCESS"]) >= 10


def test_return_for_modification_and_resubmit(as_user, repo):
    omar, rid = flow_to_review(as_user, repo)
    noor = as_user("clerk_noor")
    assert act(noor, rid, "return").status_code == 303                   # missing reason -> flash error, no change
    assert status(repo, rid) == "SUBMITTED"
    act(noor, rid, "return", reason="المرفق غير مقروء")
    assert status(repo, rid) == "RETURNED_FOR_MODIFICATION"
    n = [x for x in repo.select("notifications", {"user_id": 3}) if x["request_id"] == rid][-1]
    assert "المرفق غير مقروء" in n["message_ar"]
    assert "المرفق غير مقروء" not in as_user("citizen_tariq").get(f"/requests/{rid}").text
    post(omar, f"/requests/{rid}/pdf", files={"file": ("b.pdf", PDF, "application/pdf")})
    act(omar, rid, "submit")
    assert status(repo, rid) == "SUBMITTED"
    assert len([d for d in repo.select("documents", {"request_id": rid}) if d["document_status"] == "REVOKED"]) == 1


def test_reject_path(as_user, repo):
    omar, rid = flow_to_review(as_user, repo)
    act(as_user("clerk_noor"), rid, "start_review")
    adel = as_user("judge_adel")
    act(adel, rid, "reject")                                             # no reason
    assert status(repo, rid) == "UNDER_COURT_REVIEW"
    act(adel, rid, "reject", reason="الطلب غير مستوفٍ")
    assert status(repo, rid) == "REJECTED"
    assert act(as_user("clerk_noor"), rid, "send").status_code == 303 and status(repo, rid) == "REJECTED"


def test_invalid_transitions_rejected_and_audited(as_user, repo):
    omar, rid = flow_to_review(as_user, repo)
    adel, noor = as_user("judge_adel"), as_user("clerk_noor")
    act(adel, rid, "approve")                          # SUBMITTED -> APPROVED not allowed
    assert status(repo, rid) == "SUBMITTED"
    act(noor, rid, "send")                             # skip approval
    assert status(repo, rid) == "SUBMITTED"
    act(omar, rid, "approve")                          # lawyer attempting judge action
    assert status(repo, rid) == "SUBMITTED"
    fails = [a for a in audit_rows(repo, request_id=rid) if a["result"] == "FAILURE"]
    assert len(fails) >= 3
    assert act(omar, rid, "no_such_action").status_code == 303 and status(repo, rid) == "SUBMITTED"


def test_submit_requires_pdf_and_draft_hidden_from_citizen(as_user, repo):
    omar = as_user("lawyer_omar")
    post(omar, "/requests/new", {"case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
                                 "title": "مسودة بدون ملف", "intent": "submit"})
    rid = max(x["request_id"] for x in repo.select("document_requests"))
    assert status(repo, rid) == "DRAFT"                                  # submit blocked: no PDF
    assert as_user("citizen_tariq").get(f"/requests/{rid}").status_code == 404
    assert as_user("clerk_noor").get(f"/requests/{rid}").status_code == 200
    post(omar, f"/requests/{rid}/pdf", files={"file": ("a.pdf", PDF, "application/pdf")})
    act(omar, rid, "submit")
    assert status(repo, rid) == "SUBMITTED"


def test_upload_validation(as_user, repo, settings):
    omar = as_user("lawyer_omar")
    before = set(p.name for p in settings.storage_dir.iterdir())
    bad = [("a.exe", PDF, "application/pdf"), ("a.pdf", b"MZ\x90 not a pdf", "application/pdf"),
           ("a.pdf", PDF, "text/html"), ("a.pdf", b"", "application/pdf"),
           ("a.pdf", PDF + b"0" * (10 * 1024 * 1024 + 1), "application/pdf")]
    for f in bad:
        post(omar, "/requests/new", {"case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
                                     "title": "رفع غير صالح", "intent": "draft"}, files={"file": f})
    assert len(repo.select("document_requests")) == 3                     # nothing created
    assert set(p.name for p in settings.storage_dir.iterdir()) == before  # nothing stored


def test_citizen_and_entity_cannot_create_or_upload(as_user, repo):
    c = as_user("citizen_tariq")
    assert post(c, "/requests/new", {"case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
                                     "title": "مواطن", "intent": "draft"},
                files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 403
    assert post(c, "/requests/1/pdf", files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 404
    rami = as_user("land_officer_rami")
    assert act(rami, 1, "upload_response", files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 303
    assert len([d for d in repo.select("documents", {"request_id": 1})]) == 2   # unchanged: already RESPONSE_RECEIVED


def test_internal_note_court_only(as_user, repo):
    noor = as_user("clerk_noor")
    act(noor, 3, "note", note="ملاحظة اختبار")
    assert repo.get("document_requests", 3)["internal_note"] == "ملاحظة اختبار"
    assert act(as_user("lawyer_sara"), 3, "note", note="x").status_code == 403
    assert repo.get("document_requests", 3)["internal_note"] == "ملاحظة اختبار"


def test_transition_is_atomic_on_failure(repo, settings, monkeypatch):
    from app import workflow
    user = repo.get("users", 5)
    before = repo.get("document_requests", 3)
    orig = repo.insert

    def boom(table, row):
        if table == "audit_logs":
            raise RuntimeError("fail")
        return orig(table, row)
    monkeypatch.setattr(repo, "insert", boom)
    try:
        workflow.perform(repo, settings, repo.get("users", 5), 3, "send")
    except Exception:
        pass
    # request 3 is APPROVED; the failed 'send' must have rolled back completely
    assert repo.get("document_requests", 3) == before
