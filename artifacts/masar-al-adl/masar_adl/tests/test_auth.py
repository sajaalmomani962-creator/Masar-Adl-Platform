import re
import time

from client import Client
from conftest import login, post
from app.auth import make_pin_hash

ROLE_LANDING = {"citizen_tariq": "/citizen", "citizen_layla": "/citizen", "lawyer_omar": "/lawyer", "lawyer_sara": "/lawyer",
                "clerk_noor": "/court", "judge_adel": "/court", "land_officer_rami": "/entity",
                "civil_officer_dana": "/entity", "gov_tax_fadi": "/entity", "gov_gam_hana": "/entity"}


def _token(c):
    return re.search(r'name="login_token" value="([^"]+)"', c.get("/login").text).group(1)


def _login(app, nid, password, c=None):
    c = c or Client(app)
    d = {"login_token": _token(c), "national_id": nid, "password": password}
    return c, c.post("/login", d)


def test_correct_login_routes_each_role(app_):
    for username, landing in ROLE_LANDING.items():
        c = login(app_, username)  # quick login -> same session path
        r = c.get("/")
        assert r.status_code == 303 and r.location == landing, username
        assert c.get(landing).status_code == 200


def _demo_pw(u):
    return "Demo@" + u["national_id"][-4:]


def test_login_with_national_id_and_password_for_every_seed_user(app_, repo):
    for u in repo.select("users"):
        c, r = _login(app_, u["national_id"], _demo_pw(u))
        assert r.status_code == 303 and r.location == ROLE_LANDING[u["username"]], u["username"]


def test_login_form_has_only_two_fields(app_):
    html = Client(app_).get("/login").text
    form = html[html.index('action="/login"'):]
    form = form[:form.index("</form>")]
    assert 'name="national_id"' in form and 'name="password"' in form and 'type="password"' in form
    assert 'name="username"' not in form and "اسم المستخدم" not in form
    assert "كلمة السر" in form and "الرقم الوطني" in form


def test_wrong_login_generic_message(app_, repo):
    u = repo.one("users", {"username": "citizen_tariq"})
    _, r1 = _login(app_, u["national_id"], "wrong")               # right id, wrong password
    _, r2 = _login(app_, "TEST-NID-0000", "nobody")               # unknown id
    _, r3 = _login(app_, u["national_id"], "citizen_tariq")       # username is NOT a password
    assert r1.status_code == r2.status_code == r3.status_code == 401
    msg = lambda r: re.search(r'alert-danger">([^<]+)', r.text).group(1)
    assert msg(r1) == msg(r2) == msg(r3)


def test_password_not_accepted_for_other_users_account(app_, repo):
    t, l = repo.one("users", {"username": "citizen_tariq"}), repo.one("users", {"username": "citizen_layla"})
    _, r = _login(app_, t["national_id"], _demo_pw(l))
    assert r.status_code == 401


def test_real_db_mode_without_hashes_refuses_password_login(app_, repo, monkeypatch):
    u = repo.one("users", {"username": "citizen_tariq"})
    monkeypatch.setattr(repo, "mode", "sqlserver", raising=False)
    _, r = _login(app_, u["national_id"], _demo_pw(u))
    assert r.status_code == 401


def test_inactive_user_cannot_login(app_, repo):
    u = repo.one("users", {"username": "citizen_tariq"})
    repo.update("users", u["user_id"], {"is_active": 0})
    _, r = _login(app_, u["national_id"], _demo_pw(u))
    assert r.status_code == 401


def test_logout_invalidates_session(app_):
    c = login(app_, "citizen_tariq")
    old = dict(c.cookies)
    r = post(c, "/logout")
    assert r.status_code == 303
    c2 = Client(app_)
    c2.cookies = old
    assert c2.get("/citizen").status_code == 303  # redirected to login


def test_session_expiry(app_):
    c = login(app_, "citizen_tariq")
    store = app_.state.store
    for s in store._s.values():
        s["last"] = time.time() - store.idle - 5
    r = c.get("/citizen")
    assert r.status_code == 303 and r.location == "/login"


def test_rate_limit_blocks_after_failures(app_):
    c = Client(app_)
    for _ in range(6):
        _login(app_, "TEST-NID-X", "x", c=c)
    _, r = _login(app_, "TEST-NID-X", "x", c=c)
    assert "محاولات كثيرة" in r.text


def test_hash_env_overrides_demo_password_and_stores_hash_only(app_, repo, monkeypatch):
    import json
    u = repo.one("users", {"username": "citizen_tariq"})
    monkeypatch.setenv("DEMO_USERS_JSON", json.dumps({u["national_id"]: make_pin_hash("S3cret!pw")}))
    _, bad = _login(app_, u["national_id"], "wrong")
    _, old = _login(app_, u["national_id"], _demo_pw(u))          # demo password no longer valid for this user
    _, ok = _login(app_, u["national_id"], "S3cret!pw")
    assert bad.status_code == 401 and old.status_code == 401 and ok.status_code == 303
    assert "S3cret" not in json.dumps(repo.select("users"), default=str)


def test_session_cookie_flags(app_):
    c = Client(app_)
    r = c.post("/demo-login", {"login_token": _token(c), "username": "citizen_tariq"})
    raw = r.headers["set-cookie-raw"][0].lower()
    assert "httponly" in raw and "samesite=lax" in raw


def test_login_screen_hides_demo_data_by_default(app_):
    html = Client(app_).get("/login").text
    assert "TEST-NID" not in html and "Demo@" not in html and "/demo-login" not in html
    shown = Client(app_).get("/login?demo=1").text            # presenter-only view
    assert "TEST-NID" in shown and "/demo-login" in shown
