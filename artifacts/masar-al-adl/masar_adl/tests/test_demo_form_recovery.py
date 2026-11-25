"""Regressions for the issues observed during the real demo browser journey."""
from html.parser import HTMLParser

from conftest import PDF, post


class FormFields(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.title = None
        self.selected = {}
        self.select_name = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.select_name = attrs.get("name")
        elif tag == "option" and "selected" in attrs:
            self.selected[self.select_name] = attrs.get("value")
        elif tag == "input" and attrs.get("name") == "title":
            self.title = attrs.get("value")

    def handle_endtag(self, tag):
        if tag == "select":
            self.select_name = None


def test_invalid_pdf_preserves_text_and_all_selected_fields(as_user, repo):
    lawyer = as_user("lawyer_omar")
    title = 'طلب تجريبي "محفوظ" <script>غير منفذ</script>'
    before = len(repo.select("document_requests"))
    response = post(lawyer, "/requests/new", {
        "case_id": 1, "entity_id": 8, "request_type": "ZONING_STATUS_LETTER",
        "title": title, "intent": "submit",
    }, files={"file": ("invalid.pdf", b"not PDF", "application/pdf")})
    assert response.status_code == 422
    fields = FormFields(response.text)
    assert fields.title == title
    assert fields.selected == {"case_id": "1", "entity_id": "8", "request_type": "ZONING_STATUS_LETTER"}
    assert "احتفظنا ببيانات الطلب" in response.text
    assert "<script>غير منفذ</script>" not in response.text
    assert "&lt;script&gt;" in response.text
    assert len(repo.select("document_requests")) == before


def test_generic_binary_mime_is_still_rejected_and_form_is_preserved(as_user, repo):
    lawyer = as_user("lawyer_omar")
    before = len(repo.select("document_requests"))
    response = post(lawyer, "/requests/new", {
        "case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
        "title": "طلب لمتابعة نوع الملف", "intent": "draft",
    }, files={"file": ("request.pdf", PDF, "application/octet-stream")})
    assert response.status_code == 422 and "نوع الملف غير مسموح" in response.text
    assert FormFields(response.text).title == "طلب لمتابعة نوع الملف"
    assert len(repo.select("document_requests")) == before


def test_failed_submit_goes_to_saved_draft_not_empty_creation_form(as_user, repo):
    lawyer = as_user("lawyer_omar")
    before = len(repo.select("document_requests"))
    response = post(lawyer, "/requests/new", {
        "case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
        "title": "مسودة محفوظة بدون ملف", "intent": "submit",
    })
    assert response.status_code == 303
    assert len(repo.select("document_requests")) == before + 1
    rid = max(r["request_id"] for r in repo.select("document_requests"))
    assert response.location == f"/requests/{rid}"
    assert repo.get("document_requests", rid)["request_status"] == "DRAFT"
    page = lawyer.get(response.location)
    assert "حُفظت المسودة، ولم يُقدَّم الطلب" in page.text
    assert "مسودة محفوظة بدون ملف" in page.text


def test_corrected_pdf_can_be_submitted_after_a_rejected_upload(as_user, repo):
    lawyer = as_user("lawyer_omar")
    before = len(repo.select("document_requests"))
    data = {
        "case_id": 1, "entity_id": 3, "request_type": "CIVIL_RECORD_CHECK",
        "title": "طلب بعد تصحيح المرفق", "intent": "submit",
    }
    rejected = post(lawyer, "/requests/new", data,
                    files={"file": ("bad.pdf", b"invalid", "application/pdf")})
    assert rejected.status_code == 422
    assert len(repo.select("document_requests")) == before
    response = post(lawyer, "/requests/new", data,
                    files={"file": ("valid.pdf", PDF, "application/pdf")})
    assert response.status_code == 303
    assert len(repo.select("document_requests")) == before + 1
    rid = max(r["request_id"] for r in repo.select("document_requests"))
    assert response.location == f"/requests/{rid}"
    assert repo.get("document_requests", rid)["request_status"] == "SUBMITTED"


def test_print_fallback_keeps_the_print_permission_check(as_user, repo):
    citizen = as_user("citizen_tariq")
    response = citizen.get("/documents/2/print")
    assert response.status_code == 200
    assert 'href="/documents/2/raw?for=print"' in response.text
    assert "نافذة مستقلة للطباعة" in response.text
    repo.update("documents", 2, {"is_printable_by_citizen": 0})
    assert citizen.get("/documents/2/print").status_code == 403
    assert citizen.get("/documents/2/raw?for=print").status_code == 403
