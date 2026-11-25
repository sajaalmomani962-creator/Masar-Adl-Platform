"""مسار العدل — FastAPI web layer, preserving the original ASGI route contracts.

All policy lives in authz.py / workflow.py / documents.py; handlers only translate HTTP <-> services.
"""
import hmac
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from . import audit, documents, workflow
from .audit_view import audit_rows, can_view_audit
from . import integrity, triage
from .auth import LoginService, SessionStore
from .authz import account_active, can_access_case
from .config import BASE_DIR, Settings
from .errors import AppError, BadRequest, Forbidden, NotFound
from .labels import (COURT_ROLES, DELAY_REASONS, ENTITY_ROLES, EVENT_AR, ROLE_HOME, STATUS_AR, STATUS_CLASS)
from .repositories import DataModeError, build_repository
from .summary import case_summary, cases_for, request_view, requests_for, row_view

COOKIE = "masar_session"


class LoginInput(BaseModel):
    """Validate form values without changing the shared authentication service."""
    national_id: str = Field(default="", max_length=30)
    password: str = Field(default="", max_length=100)


templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.filters["dt"] = lambda v: v.strftime("%Y-%m-%d %H:%M") if isinstance(v, datetime) else (str(v) if v else "—")
templates.env.filters["d"] = lambda v: v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else (str(v) if v else "—")
templates.env.globals.update(STATUS_AR=STATUS_AR, EVENT_AR=EVENT_AR, DELAY_REASONS=DELAY_REASONS,
                             COURT_ROLES=COURT_ROLES, ENTITY_ROLES=ENTITY_ROLES)


class NotAuthenticated(Exception):
    pass


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        h = resp.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "SAMEORIGIN"
        h["Referrer-Policy"] = "same-origin"
        h["Content-Security-Policy"] = ("default-src 'self'; style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                                        "script-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; "
                                        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; frame-src 'self'; "
                                        "object-src 'self'; frame-ancestors 'self'; form-action 'self'")
        if request.url.path not in ("/static",) and not request.url.path.startswith("/static/"):
            h["Cache-Control"] = "no-store"
        return resp


def create_app(settings: Settings = None, repo=None):
    settings = settings or Settings()
    audit.app_logger(settings)
    note = "injected"
    if repo is None:
        repo, note = build_repository(settings)
    documents.ensure_demo_files(repo, settings)
    store = SessionStore(settings.idle_timeout, settings.absolute_timeout)
    login_svc = LoginService(settings, store)

    # ---------------- helpers ----------------
    def session_of(request):
        tok = request.cookies.get(COOKIE)
        s = store.get(tok)
        return tok, s

    def current(request):
        tok, s = session_of(request)
        if not s:
            raise NotAuthenticated()
        user = repo.get("users", s["uid"])
        if not user or not account_active(repo, user):
            store.destroy(tok)
            raise NotAuthenticated()
        return tok, s, user

    def render(request, name, user=None, s=None, tok=None, status=200, **ctx):
        base = {"user": user, "csrf": s["csrf"] if s else "", "demo": repo.mode == "demo",
                "data_mode": repo.mode, "flashes": store.pop_flash(tok) if tok else [],
                "ROLE_HOME": ROLE_HOME,
                "unread": len(repo.select("notifications", {"user_id": user["user_id"], "is_read": 0})) if user else 0}
        base.update(ctx)
        return templates.TemplateResponse(request, name, base, status_code=status)

    async def form_of(request, s):
        form = await request.form()
        if not hmac.compare_digest(str(form.get("csrf", "")), s["csrf"]):
            raise Forbidden("رمز الحماية غير صالح. أعد تحميل الصفحة.")
        return form

    async def upload_of(form, key="file"):
        f = form.get(key)
        if f is None or not hasattr(f, "read") or not getattr(f, "filename", ""):
            return None
        data = await f.read(settings.max_upload_bytes + 1)
        return {"filename": f.filename, "content_type": f.content_type, "data": data}

    def go(url, tok=None, kind=None, msg=None):
        if tok and msg:
            store.flash(tok, kind, msg)
        return RedirectResponse(url, status_code=303)

    def role_gate(user, roles):
        if user["role"] not in roles:
            raise Forbidden()

    def intid(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            raise NotFound()

    def set_cookie(resp, token, request):
        resp.set_cookie(COOKIE, token, httponly=True, samesite="lax",
                        secure=settings.secure_cookies or request.url.scheme == "https",
                        max_age=settings.absolute_timeout, path="/")

    # ---------------- auth ----------------
    async def login_page(request):
        _, s = session_of(request)
        if s:
            return RedirectResponse("/", 303)
        users = repo.select("users", order_by="user_id") if repo.mode == "demo" else []
        return render(request, "login.html", login_token=login_svc.login_token(), demo_users=users,
                      demo_hint=(repo.mode == 'demo'),
                      show_quick=(repo.mode == "demo" and request.query_params.get("demo") == "1"))

    async def login_post(request):
        form = await request.form()
        users = repo.select("users", order_by="user_id") if repo.mode == "demo" else []
        if not login_svc.check_login_token(form.get("login_token")):
            return render(request, "login.html", status=400, login_token=login_svc.login_token(),
                          demo_users=users, error="انتهت صلاحية الصفحة. أعد المحاولة.",
                          demo_hint=(repo.mode == 'demo'))
        ip = request.client.host if request.client else "?"
        try:
            payload = LoginInput.model_validate({
                "national_id": form.get("national_id", ""),
                "password": form.get("password", ""),
            })
        except ValidationError:
            # Malformed input follows the same rate-limited generic failure path.
            payload = LoginInput()
        user, err = login_svc.authenticate(repo, payload.national_id, payload.password, ip)
        if not user:
            return render(request, "login.html", status=401, login_token=login_svc.login_token(), demo_users=users,
                          error=err, demo_hint=(repo.mode == 'demo'))
        return start_session(user, request)

    def start_session(user, request):
        tok = store.create(user["user_id"])
        resp = RedirectResponse(ROLE_HOME[user["role"]], 303)
        set_cookie(resp, tok, request)
        return resp

    async def demo_login(request):
        if repo.mode != "demo":
            raise NotFound()
        form = await request.form()
        if not login_svc.check_login_token(form.get("login_token")):
            raise Forbidden("انتهت صلاحية الصفحة")
        user = repo.one("users", {"username": str(form.get("username", ""))})
        if not user or not account_active(repo, user):
            raise NotFound()
        audit.app_logger().info("DEMO-LOGIN user=%s", user["user_id"])
        return start_session(user, request)

    async def logout(request):
        tok, s, user = current(request)
        await form_of(request, s)
        store.destroy(tok)
        resp = RedirectResponse("/login", 303)
        resp.delete_cookie(COOKIE, path="/")
        return resp

    async def home(request):
        tok, s, user = current(request)
        return RedirectResponse(ROLE_HOME[user["role"]], 303)

    # ---------------- dashboards ----------------
    async def citizen_home(request):
        tok, s, user = current(request)
        role_gate(user, {"CITIZEN"})
        cases = cases_for(repo, user)
        notes = repo.select("notifications", {"user_id": user["user_id"]}, order_by="-created_at")
        return render(request, "dash_citizen.html", user, s, tok, cases=cases,
                      summaries=[case_summary(repo, user, c) for c in cases], recent=notes[:5])

    async def lawyer_home(request):
        tok, s, user = current(request)
        role_gate(user, {"LAWYER"})
        rows = [row_view(repo, r) for r in requests_for(repo, user)]
        return render(request, "dash_lawyer.html", user, s, tok, cases=cases_for(repo, user), rows=rows)

    async def court_home(request):
        tok, s, user = current(request)
        role_gate(user, COURT_ROLES)
        reqs = requests_for(repo, user)
        rows = triage.attach([row_view(repo, r) for r in reqs], triage.triage_map(repo, user, reqs))
        if user["role"] == "COURT_CLERK":
            groups = [("بانتظار المراجعة", {"SUBMITTED"}), ("جاهزة للإرسال للجهة", {"APPROVED"}),
                      ("ردود بانتظار الإتاحة", {"RESPONSE_RECEIVED"}), ("بقية الطلبات", None)]
            title = "مساحة كاتب المحكمة"
        else:
            groups = [("بانتظار قرار القاضي", {"UNDER_COURT_REVIEW"}), ("بقية الطلبات", None)]
            title = "مساحة القاضي"
        used, sections = set(), []
        for label, sts in groups:
            items = [r for r in rows if (sts is None and r["req"]["request_id"] not in used)
                     or (sts and r["req"]["request_status"] in sts)]
            if sts == {"RESPONSE_RECEIVED"}:
                items = [r for r in items if any(
                    d["visibility"] != "CITIZEN_AND_LAWYER" and d["document_status"] != "REVOKED"
                    for d in repo.select("documents", {
                        "request_id": r["req"]["request_id"], "document_type": "ENTITY_RESPONSE",
                    })
                )]
            used |= {r["req"]["request_id"] for r in items}
            sections.append((label, items))
        return render(request, "dash_court.html", user, s, tok, sections=sections, title=title,
                      top=[r for r in rows if r["triage"]["level"] in ("high", "medium")][:3])

    async def entity_home(request):
        tok, s, user = current(request)
        role_gate(user, ENTITY_ROLES)
        reqs = requests_for(repo, user)
        rows = triage.attach([row_view(repo, r) for r in reqs], triage.triage_map(repo, user, reqs))
        ent = repo.get("government_entities", user["entity_id"])
        return render(request, "dash_entity.html", user, s, tok, rows=rows, entity=ent,
                      top=[r for r in rows if r["triage"]["level"] in ("high", "medium")][:3])

    # ---------------- cases / requests ----------------
    async def case_page(request):
        tok, s, user = current(request)
        case = repo.get("cases", intid(request.path_params["case_id"]))
        if not can_access_case(repo, user, case):
            if case:
                audit.write(repo, user["user_id"], case["case_id"], None, "VIEW_CASE_SUMMARY", False,
                            f"محاولة وصول غير مصرح بها للقضية {case['case_number']}")
            raise NotFound()
        if user["role"] in ENTITY_ROLES:
            raise NotFound()
        audit.write(repo, user["user_id"], case["case_id"], None, "VIEW_CASE_SUMMARY", True,
                    f"استعلام عن ملخص القضية {case['case_number']}")
        parties = repo.select("case_parties", {"case_id": case["case_id"]})
        return render(request, "case.html", user, s, tok, summary=case_summary(repo, user, case), parties=parties)

    def render_request_form(request, user, s, tok, values=None, error=None, status=200):
        values = values or {}
        ents = [e for e in repo.select("government_entities") if e["entity_type"] == "GOVERNMENT" and e["is_active"]]
        types = {e["entity_id"]: workflow.request_type_options(repo, e["entity_id"]) for e in ents}
        selected_entity = next(
            (e["entity_id"] for e in ents if str(e["entity_id"]) == values.get("entity_id")),
            ents[0]["entity_id"] if ents else None,
        )
        return render(request, "request_new.html", user, s, tok, cases=cases_for(repo, user), entities=ents,
                      types=types, types_json={str(k): v for k, v in types.items()},
                      values=values, error=error, status=status, initial_types=types.get(selected_entity, []))

    async def request_new(request):
        tok, s, user = current(request)
        role_gate(user, {"LAWYER"})
        return render_request_form(request, user, s, tok)

    async def request_create(request):
        tok, s, user = current(request)
        role_gate(user, {"LAWYER"})
        form = await form_of(request, s)
        # Only non-sensitive form fields are echoed back, escaped by Jinja.
        # Browsers intentionally require the file to be selected again.
        values = {key: str(form.get(key, ""))[:limit] for key, limit in
                  (("case_id", 20), ("entity_id", 20), ("request_type", 60), ("title", 220))}
        try:
            rid = workflow.create_request(
                repo, settings, user, intid(form.get("case_id")), intid(form.get("entity_id")),
                str(form.get("request_type", "")), str(form.get("title", "")), await upload_of(form),
                submit=False)
        except (NotFound, Forbidden):
            raise
        except AppError as e:
            return render_request_form(request, user, s, tok, values=values, error=e.message, status=422)
        if form.get("intent") == "submit":
            try:
                workflow.perform(repo, settings, user, rid, "submit")
            except (NotFound, Forbidden):
                raise
            except AppError as e:
                # The draft was already saved. Take the lawyer to it rather
                # than inviting a duplicate new request after a failed submit.
                return go(f"/requests/{rid}", tok, "warning", f"حُفظت المسودة، ولم يُقدَّم الطلب: {e.message}")
        return go(f"/requests/{rid}", tok, "success", "تم حفظ الطلب" if form.get("intent") != "submit" else "تم تقديم الطلب للمحكمة")

    async def request_page(request):
        tok, s, user = current(request)
        rid = intid(request.path_params["request_id"])
        req = repo.get("document_requests", rid)
        from .authz import can_access_request
        if not can_access_request(repo, user, req):
            if req:
                audit.write(repo, user["user_id"], req["case_id"], rid, "VIEW_REQUEST", False,
                            f"محاولة وصول غير مصرح بها للطلب {rid}")
            raise NotFound()
        case = repo.get("cases", req["case_id"])
        return render(request, "request.html", user, s, tok, v=request_view(repo, user, req), case=case,
                      actions=workflow.available_actions(repo, user, req), ACTIONS=workflow.ACTIONS)

    async def request_pdf(request):
        tok, s, user = current(request)
        form = await form_of(request, s)
        rid = intid(request.path_params["request_id"])
        try:
            workflow.attach_lawyer_pdf(repo, settings, user, rid, await upload_of(form))
        except AppError as e:
            if isinstance(e, (NotFound, Forbidden)):
                raise
            return go(f"/requests/{rid}", tok, "danger", e.message)
        return go(f"/requests/{rid}", tok, "success", "تم رفع الملف")

    async def request_action(request):
        tok, s, user = current(request)
        form = await form_of(request, s)
        rid = intid(request.path_params["request_id"])
        action = str(form.get("action", ""))
        try:
            workflow.perform(repo, settings, user, rid, action,
                             {k: str(v) for k, v in form.items() if isinstance(v, str)}, await upload_of(form))
        except (NotFound, Forbidden):
            raise
        except AppError as e:
            return go(f"/requests/{rid}", tok, "danger", e.message)
        return go(f"/requests/{rid}", tok, "success", "تم تنفيذ الإجراء")

    # ---------------- documents ----------------
    async def document_get(request):
        tok, s, user = current(request)
        did, mode = intid(request.path_params["doc_id"]), request.path_params["mode"]
        if mode == "print":
            doc, _ = documents.open_document(repo, settings, user, did, "print")
            return render(request, "print.html", user, s, tok, doc=doc)
        if mode == "raw":
            act = request.query_params.get("for", "view")
            if act not in ("view", "print"):
                raise NotFound()
            # Raw PDF URLs are directly accessible, so they must also be audited.
            doc, path = documents.open_document(repo, settings, user, did, act)
            return FileResponse(path, media_type="application/pdf",
                                headers={"Content-Disposition": f'inline; filename="document-{did}.pdf"'})
        if mode not in ("view", "download"):
            raise NotFound()
        doc, path = documents.open_document(repo, settings, user, did, mode)
        disp = "attachment" if mode == "download" else "inline"
        return FileResponse(path, media_type="application/pdf",
                            headers={"Content-Disposition": f'{disp}; filename="document-{did}.pdf"'})

    # ---------------- notifications / audit / misc ----------------
    async def notifications_page(request):
        tok, s, user = current(request)
        notes = repo.select("notifications", {"user_id": user["user_id"]}, order_by="-created_at")
        return render(request, "notifications.html", user, s, tok, notes=notes)

    async def notifications_read(request):
        tok, s, user = current(request)
        await form_of(request, s)
        for n in repo.select("notifications", {"user_id": user["user_id"], "is_read": 0}):
            repo.update("notifications", n["notification_id"], {"is_read": 1})
        return go("/notifications")

    async def audit_page(request):
        tok, s, user = current(request)
        if not can_view_audit(user):
            raise Forbidden()
        f = {k: (request.query_params.get(k) or "").strip() for k in
             ("action", "result", "actor", "case", "request", "date_from", "date_to")}
        rows = audit_rows(repo, user, f)
        return render(request, "audit.html", user, s, tok, rows=rows, f=f, users=repo.select("users"))

    async def integrity_page(request):
        tok, s, user = current(request)
        if not can_view_audit(user):
            raise Forbidden()
        scope = integrity.scope_cases(repo, user)
        findings = integrity.run(repo, scope)
        sev = request.query_params.get("severity", "")
        shown = [f for f in findings if not sev or f["severity"] == sev]
        return render(request, "integrity.html", user, s, tok, findings=shown, counts=integrity.summarize(findings),
                      sev=sev, total=len(findings))

    async def custody_page(request):
        tok, s, user = current(request)
        if not can_view_audit(user):
            raise Forbidden()
        try:
            rid = int(request.path_params["request_id"])
        except ValueError:
            raise NotFound()
        req = repo.get("document_requests", rid)
        scope = integrity.scope_cases(repo, user)
        if not req or (scope is not None and req["case_id"] not in scope):
            raise NotFound()
        ctx = integrity.build_context(repo)
        findings = integrity.check_request(repo, req, ctx) + [f for f in integrity.check_audit_access(ctx) if f["request_id"] == rid]
        return render(request, "custody.html", user, s, tok, req=req, rows=integrity.custody_report(repo, req),
                      findings=findings, case=ctx["cases"][req["case_id"]])

    async def demo_reset(request):
        tok, s, user = current(request)
        await form_of(request, s)
        if repo.mode != "demo":
            raise NotFound()
        repo.reset()
        store.flash(tok, "success", "أُعيد ضبط بيانات العرض التجريبية")
        return go(ROLE_HOME[user["role"]])

    async def health(request):
        ok, msg = repo.health()
        return JSONResponse({"status": "ok" if ok else "error", "data_mode": repo.mode, "note": note,
                             "demo_banner": "وضع تجريبي — البيانات ليست من قاعدة البيانات الحية" if repo.mode == "demo" else None},
                            status_code=200 if ok else 503)

    # ---------------- errors ----------------
    async def on_app_error(request, exc):
        tok, s = session_of(request)
        user = repo.get("users", s["uid"]) if s else None
        return render(request, "error.html", user, s, None, status=exc.status, code=exc.status, message=exc.message)

    async def on_unauth(request, exc):
        return RedirectResponse("/login", 303)

    async def on_404(request, exc):
        return render(request, "error.html", None, None, None, status=404, code=404, message="الصفحة غير موجودة")

    async def on_500(request, exc):
        # Avoid putting database messages, input values or credentials in logs.
        audit.app_logger().error("UNHANDLED error_type=%s", type(exc).__name__)
        return render(request, "error.html", None, None, None, status=500, code=500,
                      message="حدث خطأ غير متوقع. تم تسجيله.")

    routes = [
        Route("/", home), Route("/health", health),
        Route("/login", login_page, methods=["GET"]), Route("/login", login_post, methods=["POST"]),
        Route("/demo-login", demo_login, methods=["POST"]), Route("/logout", logout, methods=["POST"]),
        Route("/citizen", citizen_home), Route("/lawyer", lawyer_home), Route("/court", court_home),
        Route("/entity", entity_home),
        Route("/cases/{case_id}", case_page),
        Route("/requests/new", request_new, methods=["GET"]), Route("/requests/new", request_create, methods=["POST"]),
        Route("/requests/{request_id}", request_page),
        Route("/requests/{request_id}/pdf", request_pdf, methods=["POST"]),
        Route("/requests/{request_id}/action", request_action, methods=["POST"]),
        Route("/documents/{doc_id}/{mode}", document_get),
        Route("/notifications", notifications_page), Route("/notifications/read", notifications_read, methods=["POST"]),
        Route("/audit", audit_page), Route("/integrity", integrity_page),
        Route("/integrity/requests/{request_id}", custody_page), Route("/demo/reset", demo_reset, methods=["POST"]),
        Mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static"),
    ]
    # Keep Starlette Route objects deliberately: HTML form handlers and custom
    # safe errors retain their exact contracts, under FastAPI's ASGI application.
    app = FastAPI(title="مسار العدل", version="9.0.0", docs_url=None, redoc_url=None,
                    openapi_url=None, routes=routes, middleware=[Middleware(SecurityHeaders)],
                    exception_handlers={AppError: on_app_error, NotAuthenticated: on_unauth, 404: on_404, 500: on_500})
    app.state.repo, app.state.settings, app.state.store, app.state.login = repo, settings, store, login_svc
    return app


def app_factory():
    try:
        return create_app()
    except DataModeError as e:
        raise SystemExit(f"خطأ إعداد: {e}")
