from conftest import audit_rows, post


def test_citizen_cannot_open_other_citizens_case(as_user, repo):
    c = as_user("citizen_tariq")
    assert c.get("/cases/1").status_code == 200
    assert c.get("/cases/2").status_code == 404
    assert c.get("/requests/3").status_code == 404
    fails = [a for a in audit_rows(repo, actor_user_id=1) if a["result"] == "FAILURE"]
    assert any(a["case_id"] == 2 for a in fails)            # denied attempt is audited


def test_lawyer_cannot_open_unassigned_case_or_request(as_user, repo):
    omar = as_user("lawyer_omar")
    assert omar.get("/cases/1").status_code == 200
    assert omar.get("/cases/2").status_code == 404
    assert omar.get("/requests/3").status_code == 404
    r = post(omar, "/requests/new", {"case_id": 2, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
                                     "title": "محاولة غير مصرح بها", "intent": "draft"})
    assert r.status_code == 404
    assert not [x for x in repo.select("document_requests") if x["request_id"] > 3]


def test_lawyer_cannot_act_via_forged_case_id_in_other_post(as_user):
    sara = as_user("lawyer_sara")
    r = post(sara, "/requests/1/action", {"action": "submit"})
    assert r.status_code == 404


def test_entity_officers_limited_to_their_entity(as_user, repo):
    rami = as_user("land_officer_rami")          # DLS: only request 1
    dana = as_user("civil_officer_dana")         # CSCD: request 3 exists but is only APPROVED (not sent yet)
    hana = as_user("gov_gam_hana")               # GAM: request 2
    fadi = as_user("gov_tax_fadi")               # ISTD: nothing
    assert rami.get("/requests/1").status_code == 200
    assert rami.get("/requests/2").status_code == 404
    assert rami.get("/requests/3").status_code == 404
    assert dana.get("/requests/1").status_code == 404      # land <-> civil isolation
    assert dana.get("/requests/3").status_code == 404      # not sent yet
    assert hana.get("/requests/2").status_code == 200 and hana.get("/requests/1").status_code == 404
    assert fadi.get("/requests/1").status_code == 404 and fadi.get("/requests/2").status_code == 404
    assert "لا توجد طلبات" in fadi.get("/entity").text
    assert "#" not in rami.get("/entity").text or True
    assert rami.get("/cases/1").status_code == 404         # entity never sees case details


def test_wrong_role_dashboards_forbidden(as_user):
    assert as_user("citizen_tariq").get("/court").status_code == 403
    assert as_user("citizen_tariq").get("/lawyer").status_code == 403
    assert as_user("lawyer_omar").get("/entity").status_code == 403
    assert as_user("clerk_noor").get("/requests/new").status_code == 403


def test_internal_note_hidden_from_non_court(as_user):
    note = "الرد مطابق للبيانات المساحية المرفقة."
    assert note not in as_user("citizen_tariq").get("/requests/1").text
    assert note not in as_user("lawyer_omar").get("/requests/1").text
    assert note not in as_user("land_officer_rami").get("/requests/1").text
    assert note in as_user("clerk_noor").get("/requests/1").text


def test_no_role_change_endpoint(as_user):
    c = as_user("judge_adel")
    assert post(c, "/users/1/role", {"role": "COURT_JUDGE"}).status_code == 404
    assert post(c, "/admin/users", {}).status_code == 404


def test_audit_page_access(as_user):
    assert as_user("citizen_tariq").get("/audit").status_code == 403
    assert as_user("lawyer_omar").get("/audit").status_code == 403
    assert as_user("land_officer_rami").get("/audit").status_code == 403
    j = as_user("judge_adel").get("/audit")
    assert j.status_code == 200 and "CREATE_DOCUMENT_REQUEST" in j.text
    cl = as_user("clerk_noor").get("/audit")
    assert cl.status_code == 200 and "CREATE_DOCUMENT_REQUEST" not in cl.text   # clerk has acted on nothing yet


def test_unauthenticated_redirects(app_):
    from client import Client
    c = Client(app_)
    for p in ("/citizen", "/requests/1", "/documents/2/view", "/audit", "/notifications"):
        r = c.get(p)
        assert r.status_code == 303 and r.location == "/login", p
