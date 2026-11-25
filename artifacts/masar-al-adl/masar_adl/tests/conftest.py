import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["DATA_MODE"] = "demo"
os.environ["PDF_STORAGE_BACKEND"] = "local"  # Ordinary tests must never call cloud services.

import pytest

from app.config import Settings
from app.main import create_app
from client import Client


@pytest.fixture()
def env(tmp_path):
    s = Settings()
    s.data_mode = "demo"
    s.storage_dir = tmp_path / "storage"
    s.log_dir = tmp_path / "logs"
    app = create_app(s)
    return app, app.state.repo, s


@pytest.fixture()
def app_(env):
    return env[0]


@pytest.fixture()
def repo(env):
    return env[1]


@pytest.fixture()
def settings(env):
    return env[2]


def login(app, username):
    c = Client(app)
    html = c.get("/login").text
    import re
    tok = re.search(r'name="login_token" value="([^"]+)"', html).group(1)
    r = c.post("/demo-login", {"login_token": tok, "username": username})
    assert r.status_code == 303, r.text[:200]
    return c


@pytest.fixture()
def as_user(app_):
    def _f(username):
        return login(app_, username)
    return _f


PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def post(c, path, data=None, files=None):
    d = dict(data or {})
    d["csrf"] = c.csrf()
    return c.post(path, d, files=files)


def act(c, rid, action, files=None, **kw):
    return post(c, f"/requests/{rid}/action", {"action": action, **kw}, files=files)


def audit_rows(repo, **where):
    return repo.select("audit_logs", where or None)


def flow_to_review(as_user, repo, entity_id=3, rtype="CIVIL_RECORD_CHECK", case_id=1):
    omar = as_user("lawyer_omar")
    r = post(omar, "/requests/new", {"case_id": case_id, "entity_id": entity_id, "request_type": rtype,
                                     "title": "طلب اختبار آلي", "intent": "submit"},
             files={"file": ("a.pdf", PDF, "application/pdf")})
    assert r.status_code == 303
    rid = max(x["request_id"] for x in repo.select("document_requests"))
    return omar, rid
