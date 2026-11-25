from conftest import audit_rows, post


def codes(repo, uid):
    return [(a["action_code"], a["result"]) for a in audit_rows(repo, actor_user_id=uid)]


def test_citizen_can_view_download_print_entity_response(as_user, repo):
    c = as_user("citizen_tariq")
    for mode in ("view", "download", "print"):
        assert c.get(f"/documents/2/{mode}").status_code == 200, mode
    assert c.get("/documents/2/download").headers["content-disposition"].startswith("attachment")
    assert c.get("/documents/2/raw?for=print").content.startswith(b"%PDF-")
    got = codes(repo, 1)
    for code in ("VIEW_DOCUMENT", "DOWNLOAD_DOCUMENT", "PRINT_DOCUMENT"):
        assert (code, "SUCCESS") in got


def test_citizen_can_use_public_status_certificate(as_user):
    c = as_user("citizen_tariq")
    for mode in ("view", "download", "print"):
        assert c.get(f"/documents/3/{mode}").status_code == 200


def test_citizen_blocked_from_lawyer_pdf_and_attempt_is_audited(as_user, repo):
    c = as_user("citizen_tariq")
    for mode in ("view", "download", "print"):
        assert c.get(f"/documents/1/{mode}").status_code == 403, mode
    assert ("VIEW_DOCUMENT", "FAILURE") in codes(repo, 1)
    assert ("DOWNLOAD_DOCUMENT", "FAILURE") in codes(repo, 1)
    assert "نسخة PDF لطلب المحامي" not in c.get("/requests/1").text     # not even listed


def test_other_citizen_gets_404_not_403(as_user):
    layla = as_user("citizen_layla")
    for d in (1, 2, 3):
        assert layla.get(f"/documents/{d}/view").status_code == 404


def test_print_denied_when_not_printable_but_view_ok(as_user, repo):
    repo.update("documents", 2, {"is_printable_by_citizen": 0, "print_permission_note_ar": "x"})
    c = as_user("citizen_tariq")
    assert c.get("/documents/2/view").status_code == 200
    r = c.get("/documents/2/print")
    assert r.status_code == 403 and "غير متاح للطباعة" in r.text
    assert c.get("/documents/2/raw?for=print").status_code == 403
    assert ("PRINT_DOCUMENT", "FAILURE") in codes(repo, 1)


def test_citizen_blocked_when_permission_row_disabled(as_user, repo):
    perm = repo.one("document_permissions", {"role": "CITIZEN", "document_type": "ENTITY_RESPONSE"})
    repo.update("document_permissions", perm["permission_id"], {"can_print": 0})
    c = as_user("citizen_tariq")
    assert c.get("/documents/2/print").status_code == 403
    assert c.get("/documents/2/download").status_code == 200
    repo.update("document_permissions", perm["permission_id"], {"can_print": 0, "can_download": 0})
    assert c.get("/documents/2/download").status_code == 403


def test_citizen_blocked_when_status_revoked_or_visibility_changes(as_user, repo):
    c = as_user("citizen_tariq")
    repo.update("documents", 2, {"document_status": "REVOKED", "document_status_ar": "مسحوب"})
    assert c.get("/documents/2/view").status_code == 403
    repo.update("documents", 2, {"document_status": "RECEIVED", "is_printable_by_citizen": 0,
                                 "visibility": "COURT_AND_AUTHORIZED_LAWYER"})
    assert c.get("/documents/2/view").status_code == 403


def test_staff_and_entity_document_rules(as_user):
    assert as_user("lawyer_omar").get("/documents/1/print").status_code == 200
    assert as_user("lawyer_sara").get("/documents/1/view").status_code == 404
    assert as_user("clerk_noor").get("/documents/1/download").status_code == 200
    assert as_user("clerk_noor").get("/documents/1/print").status_code == 403     # can_print=0
    assert as_user("judge_adel").get("/documents/3/view").status_code == 200
    assert as_user("judge_adel").get("/documents/3/download").status_code == 403   # can_download=0
    rami = as_user("land_officer_rami")
    assert rami.get("/documents/2/view").status_code == 200
    assert rami.get("/documents/1/view").status_code == 403                        # no permission row for entities
    assert as_user("gov_gam_hana").get("/documents/2/view").status_code == 404     # other entity


def test_idor_guessing(as_user):
    c = as_user("citizen_tariq")
    for p in ("/documents/999/view", "/documents/abc/view", "/documents/0/download", "/documents/2/zzz",
              "/documents/2/raw?for=download", "/documents/../../etc/passwd/view"):
        assert c.get(p).status_code == 404, p


def test_storage_path_traversal_blocked(settings, repo, as_user):
    from app import documents
    assert documents._path(settings, "../../etc/passwd").parent == settings.storage_dir.resolve()
    repo.update("documents", 2, {"file_name": "../secret.pdf"})
    assert as_user("citizen_tariq").get("/documents/2/view").status_code == 404
