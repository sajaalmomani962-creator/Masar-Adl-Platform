"""Request lifecycle: one transition table, enforced on the server.

Every successful transition writes status + request_timeline + audit_logs + notifications
inside ONE transaction. Rejected attempts are audited (FAILURE) after the rollback.
"""
from . import audit, documents
from .authz import account_active, can_access_case, can_access_request
from .errors import BadRequest, Forbidden, NeedsApproval, NotFound
from .labels import COURT_ROLES, DELAY_REASONS, ENTITY_ROLES, ENTITY_REQUEST_TYPES, GENERIC_TYPE
from .schema import now

JUDGE_ONLY = {"approve", "reject"}


def _ent(ctx):
    return ctx["entity"]


ACTIONS = {
    "submit": dict(label="تقديم الطلب", roles={"LAWYER"}, frm={"DRAFT", "RETURNED_FOR_MODIFICATION"}, to="SUBMITTED",
                   event="REQUEST_SUBMITTED", vis=1, audit="SUBMIT_DOCUMENT_REQUEST",
                   desc=lambda c: f"قدّم المحامي طلب كتاب إلى {_ent(c)}.",
                   public=lambda c: f"قدّم المحامي طلب كتاب إلى {_ent(c)} وهو بانتظار مراجعة المحكمة.",
                   notify=[("clerks", "REQUEST_SUBMITTED", "طلب كتاب جديد", lambda c: f"طلب كتاب جديد على القضية {c['case_number']} بانتظار المراجعة."),
                           ("citizen", "REQUEST_SUBMITTED", "تقديم طلب كتاب", lambda c: f"قدّم محاميك طلب كتاب على قضيتك {c['case_number']}.")]),
    "start_review": dict(label="بدء المراجعة", roles={"COURT_CLERK"}, frm={"SUBMITTED"}, to="UNDER_COURT_REVIEW",
                         event="REVIEW_STARTED", vis=1, audit="START_COURT_REVIEW",
                         desc=lambda c: "بدأت المحكمة مراجعة الطلب.",
                         public=lambda c: "الطلب قيد المراجعة لدى المحكمة.",
                         notify=[("lawyer", "REVIEW_STARTED", "بدء مراجعة الطلب", lambda c: f"بدأت المحكمة مراجعة طلبك على القضية {c['case_number']}.")]),
    "return": dict(label="إعادة للتعديل", roles={"COURT_CLERK", "COURT_JUDGE"}, frm={"SUBMITTED", "UNDER_COURT_REVIEW"},
                   to="RETURNED_FOR_MODIFICATION", event="RETURNED_FOR_MODIFICATION", vis=0, needs_reason=True,
                   audit="RETURN_DOCUMENT_REQUEST",
                   desc=lambda c: f"أُعيد الطلب للتعديل. السبب: {c['reason']}",
                   public=lambda c: "أُعيد الطلب إلى المحامي لاستكمال متطلباته.",
                   notify=[("lawyer", "REQUEST_RETURNED", "إعادة طلب للتعديل", lambda c: f"أُعيد طلبك على القضية {c['case_number']} للتعديل. السبب: {c['reason']}")]),
    "approve": dict(label="موافقة القاضي", roles={"COURT_JUDGE"}, frm={"UNDER_COURT_REVIEW"}, to="APPROVED",
                    event="COURT_APPROVED", vis=1, needs_reason=True, audit="APPROVE_DOCUMENT_REQUEST", decision=True,
                    desc=lambda c: f"وافق القاضي على إرسال الكتاب إلى {_ent(c)}.",
                    public=lambda c: f"تمت موافقة المحكمة على الكتاب وجارٍ إرساله إلى {_ent(c)}.",
                    notify=[("lawyer", "REQUEST_APPROVED", "اعتماد طلب كتاب", lambda c: f"وافقت المحكمة على طلبك على القضية {c['case_number']}."),
                            ("citizen", "REQUEST_APPROVED", "اعتماد طلب كتاب", lambda c: f"تمت موافقة المحكمة على كتاب قضيتك {c['case_number']}."),
                            ("clerks", "REQUEST_APPROVED", "جاهز للإرسال", lambda c: f"الطلب على القضية {c['case_number']} جاهز للإرسال إلى الجهة.")]),
    "reject": dict(label="رفض القاضي", roles={"COURT_JUDGE"}, frm={"UNDER_COURT_REVIEW"}, to="REJECTED",
                   event="COURT_REJECTED", vis=1, needs_reason=True, audit="REJECT_DOCUMENT_REQUEST", decision=True,
                   desc=lambda c: "لم توافق المحكمة على إرسال الكتاب.",
                   public=lambda c: "لم توافق المحكمة على إرسال الكتاب.",
                   notify=[("lawyer", "REQUEST_REJECTED", "رفض طلب كتاب", lambda c: f"رفضت المحكمة طلبك على القضية {c['case_number']}. السبب: {c['reason']}"),
                           ("citizen", "REQUEST_REJECTED", "رفض طلب كتاب", lambda c: f"لم توافق المحكمة على كتاب قضيتك {c['case_number']}.")]),
    "send": dict(label="إرسال إلى الجهة (محاكاة)", roles={"COURT_CLERK"}, frm={"APPROVED"}, to="SENT_TO_ENTITY",
                 event="SENT_TO_ENTITY", vis=1, audit="SEND_TO_ENTITY", sets_sent=True,
                 desc=lambda c: f"أُرسل الكتاب إلكترونيًا إلى {_ent(c)} (محاكاة ضمن النموذج الأولي).",
                 public=lambda c: f"أُرسل الكتاب إلى {_ent(c)} بانتظار المعالجة.",
                 notify=[("entity", "REQUEST_RECEIVED", "كتاب وارد جديد", lambda c: f"ورد كتاب جديد على القضية {c['case_number']}."),
                         ("lawyer", "REQUEST_SENT", "إرسال الكتاب للجهة", lambda c: f"أُرسل كتابك على القضية {c['case_number']} إلى {_ent(c)}."),
                         ("citizen", "REQUEST_SENT", "إرسال الكتاب للجهة", lambda c: f"أُرسل كتاب قضيتك {c['case_number']} إلى {_ent(c)}.")]),
    "start_processing": dict(label="بدء المعالجة", roles=ENTITY_ROLES, frm={"SENT_TO_ENTITY"}, to="UNDER_PROCESSING",
                             event="PROCESSING_STARTED", vis=1, audit="START_PROCESSING",
                             desc=lambda c: f"بدأت {_ent(c)} معالجة الكتاب.",
                             public=lambda c: f"الكتاب قيد المعالجة لدى {_ent(c)}.",
                             notify=[("lawyer", "PROCESSING_STARTED", "بدء المعالجة", lambda c: f"بدأت {_ent(c)} معالجة كتابك على القضية {c['case_number']}.")]),
    "mark_delayed": dict(label="تسجيل تأخير", roles=ENTITY_ROLES | {"COURT_CLERK"}, frm={"SENT_TO_ENTITY", "UNDER_PROCESSING"},
                         to="DELAYED", event="REQUEST_DELAYED", vis=1, needs_delay=True, audit="MARK_REQUEST_DELAYED",
                         desc=lambda c: f"تم تسجيل تأخير {c['delay_days']} يوم على الطلب لدى الجهة.",
                         public=lambda c: f"الكتاب لدى {_ent(c)} وقيد المعالجة مع تأخير إداري.",
                         notify=[("lawyer", "REQUEST_DELAYED", "تنبيه تأخير طلب", lambda c: f"سُجل تأخير {c['delay_days']} يوم على طلبك لدى {_ent(c)}."),
                                 ("citizen", "REQUEST_DELAYED", "تنبيه تأخير طلب", lambda c: f"سُجل تأخير {c['delay_days']} يوم على كتاب قضيتك لدى {_ent(c)}.")]),
    "resume": dict(label="استئناف المعالجة", roles=ENTITY_ROLES, frm={"DELAYED"}, to="UNDER_PROCESSING",
                   event="PROCESSING_RESUMED", vis=1, audit="RESUME_PROCESSING",
                   desc=lambda c: f"استأنفت {_ent(c)} معالجة الكتاب.",
                   public=lambda c: f"الكتاب قيد المعالجة لدى {_ent(c)}.",
                   notify=[("lawyer", "PROCESSING_RESUMED", "استئناف المعالجة", lambda c: f"استأنفت {_ent(c)} معالجة كتابك على القضية {c['case_number']}.")]),
    "upload_response": dict(label="رفع الرد الرسمي", roles=ENTITY_ROLES, frm={"SENT_TO_ENTITY", "UNDER_PROCESSING", "DELAYED"},
                            to="RESPONSE_RECEIVED", event="RESPONSE_RECEIVED", vis=0, needs_upload=True,
                            audit="UPLOAD_ENTITY_RESPONSE", sets_response=True,
                            desc=lambda c: f"وصل رد {_ent(c)} وهو قيد مراجعة المحكمة قبل إتاحته.",
                            public=lambda c: f"وردّ رد {_ent(c)} وهو قيد مراجعة المحكمة قبل إتاحته.",
                            notify=[("clerks", "RESPONSE_PENDING_RELEASE", "رد بانتظار الإتاحة", lambda c: f"وصل رد على القضية {c['case_number']} بانتظار مراجعته وإتاحته."),
                                    ("lawyer", "RESPONSE_AVAILABLE", "وصول رد جهة", lambda c: f"وصل رد {_ent(c)} على طلبك في القضية {c['case_number']}.")]),
    "release_response": dict(label="إتاحة الرد للمواطن", roles=COURT_ROLES, frm={"RESPONSE_RECEIVED"}, to=None,
                             event="RESPONSE_RELEASED", vis=1, audit="RELEASE_RESPONSE_TO_CITIZEN",
                             desc=lambda c: "أتاحت المحكمة رد الجهة ضمن ملف الدعوى.",
                             public=lambda c: f"تم استلام رد {_ent(c)} وإتاحته ضمن ملف الدعوى.",
                             notify=[("citizen", "RESPONSE_AVAILABLE", "وصول رد جهة", lambda c: f"تم استلام رد {_ent(c)} على طلب الكتاب الخاص بقضيتك رقم {c['case_number']}."),
                                     ("lawyer", "RESPONSE_RELEASED", "إتاحة الرد", lambda c: f"أُتيح رد {_ent(c)} للمواطن على القضية {c['case_number']}.")]),
    "note": dict(label="حفظ الملاحظة الداخلية", roles=COURT_ROLES, frm=None, to=None, event="INTERNAL_NOTE", vis=0,
                 audit="UPDATE_INTERNAL_NOTE", desc=lambda c: "تحديث الملاحظة الداخلية.", public=None, notify=[]),
}


def _users_of(repo, kind, case, req):
    if kind == "citizen":
        return [case["citizen_user_id"]]
    if kind == "lawyer":
        return [case["lawyer_user_id"]]
    if kind == "clerks":
        return [u["user_id"] for u in repo.select("users", {"role": "COURT_CLERK", "is_active": 1})]
    if kind == "entity":
        return [u["user_id"] for u in repo.select("users", {"entity_id": req["target_entity_id"], "is_active": 1})
                if u["role"] in ENTITY_ROLES]
    return []


def available_actions(repo, user, req):
    """Actions to *offer* in the UI. The server re-checks everything on POST."""
    out = []
    if not can_access_request(repo, user, req):
        return out
    for key, a in ACTIONS.items():
        if key == "note":
            if user["role"] in a["roles"]:
                out.append(key)
            continue
        roles = a["roles"]
        if user["role"] in roles and req["request_status"] in a["frm"]:
            if key == "release_response" and not any(
                d["visibility"] != "CITIZEN_AND_LAWYER" and d["document_status"] != "REVOKED"
                for d in repo.select("documents", {"request_id": req["request_id"], "document_type": "ENTITY_RESPONSE"})
            ):
                continue
            out.append(key)
    return out


def entity_name(repo, entity_id):
    e = repo.get("government_entities", entity_id)
    return e["entity_name_ar"] if e else "الجهة"


def _fail(repo, user, req, action, msg, exc):
    audit.write(repo, user["user_id"], req["case_id"], req["request_id"], ACTIONS[action]["audit"], False, msg)
    exc.audit_logged = True
    raise exc


def perform(repo, settings, user, request_id, action, params=None, upload=None):
    """Audit validation failures as well as policy denials, after any rollback."""
    try:
        return _perform(repo, settings, user, request_id, action, params, upload)
    except Exception as exc:
        if not getattr(exc, "audit_logged", False):
            req = repo.get("document_requests", request_id) if isinstance(request_id, int) else None
            if req:
                code = ACTIONS.get(action, {}).get("audit", "INVALID_REQUEST_ACTION")
                try:
                    audit.write(repo, user["user_id"], req["case_id"], request_id, code, False,
                                "تعذّر تنفيذ الإجراء على الطلب")
                except Exception:
                    audit.app_logger().error("WORKFLOW-FAILURE audit_unavailable")
        raise


def _perform(repo, settings, user, request_id, action, params=None, upload=None):
    params = params or {}
    if action not in ACTIONS:
        raise BadRequest("إجراء غير معروف")
    a = ACTIONS[action]
    req = repo.get("document_requests", request_id) if isinstance(request_id, int) else None
    if not req or not can_access_request(repo, user, req):
        if req:  # known record, user not related: audit it, answer 404 (do not reveal existence)
            _fail(repo, user, req, action, f"محاولة وصول غير مصرح بها للطلب {request_id}", NotFound())
        raise NotFound()
    role = user["role"]
    if role not in a["roles"]:
        if action in JUDGE_ONLY and role == "COURT_CLERK":
            _fail(repo, user, req, action, "قرار قضائي يتطلب القاضي المخوّل", NeedsApproval())
        _fail(repo, user, req, action, f"الدور {role} غير مخوّل بالإجراء {action}", Forbidden())
    if a["frm"] is not None and req["request_status"] not in a["frm"]:
        _fail(repo, user, req, action, f"انتقال غير مسموح من الحالة {req['request_status']}", BadRequest("الإجراء غير متاح في الحالة الحالية للطلب"))

    case = repo.get("cases", req["case_id"])
    ctx = {"entity": entity_name(repo, req["target_entity_id"]), "case_number": case["case_number"],
           "actor": user["display_name"], "reason": (params.get("reason") or "").strip(),
           "delay_days": 0}
    if a.get("needs_reason") and not ctx["reason"]:
        raise BadRequest("السبب مطلوب")
    if len(ctx["reason"]) > 200:
        raise BadRequest("السبب طويل جدًا (200 حرفًا كحد أقصى)")
    if a.get("needs_delay"):
        try:
            ctx["delay_days"] = int(params.get("delay_days", ""))
        except (TypeError, ValueError):
            raise BadRequest("عدد أيام التأخير غير صالح")
        if not 1 <= ctx["delay_days"] <= 365:
            raise BadRequest("عدد أيام التأخير يجب أن يكون بين 1 و365")
        if params.get("delay_reason_code") not in DELAY_REASONS:
            raise BadRequest("سبب التأخير غير صالح")
    if action == "submit":
        has_pdf = [d for d in repo.select("documents", {"request_id": request_id, "document_type": "LAWYER_REQUEST_PDF"})
                   if d["document_status"] != "REVOKED"]
        if not has_pdf:
            raise BadRequest("يجب رفع ملف PDF للطلب قبل التقديم")
    stored_name = None
    if a.get("needs_upload"):
        if not upload:
            raise BadRequest("يجب إرفاق ملف الرد (PDF)")
        documents.validate_pdf(upload["filename"], upload["content_type"], upload["data"], settings.max_upload_bytes)
        stored_name = documents.save_pdf(settings, upload["data"])
    if action == "release_response":
        pending = [d for d in repo.select("documents", {"request_id": request_id, "document_type": "ENTITY_RESPONSE"})
                   if d["visibility"] != "CITIZEN_AND_LAWYER" and d["document_status"] != "REVOKED"]
        if not pending:
            raise BadRequest("لا يوجد رد بانتظار الإتاحة")
    if action == "note":
        note = (params.get("note") or "").strip()
        if len(note) > 1000:
            raise BadRequest("الملاحظة طويلة جدًا")

    with repo.transaction():
        fields, ts = {}, now()
        if a["to"]:
            fields["request_status"] = a["to"]
        if a.get("public"):
            msg = a["public"](ctx)
            fields["public_status_message_ar"] = msg
        if action == "submit":
            fields["submitted_at"] = ts
        if a.get("decision"):
            fields.update(court_decision_by_user_id=user["user_id"], court_decision_at=ts)
        if a.get("sets_sent"):
            fields["sent_to_entity_at"] = ts
        if a.get("sets_response"):
            fields["response_received_at"] = ts
        if a.get("needs_delay"):
            fields.update(delay_days=ctx["delay_days"], delay_reason_code=params["delay_reason_code"])
        if action in ("return", "reject", "approve"):
            prev = req["internal_note"] or ""
            fields["internal_note"] = (prev + f"\n[{a['label']}] {ctx['reason']}").strip()[-1000:]
        if action == "note":
            fields["internal_note"] = note or None
        if fields:
            repo.update("document_requests", request_id, fields)

        if action == "upload_response":
            repo.insert("documents", dict(
                request_id=request_id, document_type="ENTITY_RESPONSE", document_type_ar="رد الجهة الحكومية",
                document_title_ar=f"رد {ctx['entity']} على الطلب {request_id}", file_name=stored_name,
                uploaded_by_user_id=user["user_id"], visibility="COURT_AND_AUTHORIZED_LAWYER",
                visibility_ar="المحكمة والمحامي الموكل فقط", is_printable_by_citizen=0, is_official=1,
                document_status="RECEIVED", document_status_ar="مستلم",
                print_permission_note_ar="بانتظار إتاحة المحكمة", attachment_notes_ar="رد تجريبي مرفوع من الجهة",
                attachment_action_ar="معاينة"))
        if action == "release_response":
            for d in repo.select("documents", {"request_id": request_id, "document_type": "ENTITY_RESPONSE"}):
                if d["visibility"] != "CITIZEN_AND_LAWYER" and d["document_status"] != "REVOKED":
                    repo.update("documents", d["document_id"], dict(
                        visibility="CITIZEN_AND_LAWYER", visibility_ar="المواطن والمحامي الموكل",
                        is_printable_by_citizen=1, print_permission_note_ar="متاح للطباعة للمواطن والمحامي",
                        attachment_action_ar="تنزيل وطباعة"))
        repo.insert("request_timeline", dict(
            request_id=request_id, event_code=a["event"], event_description_ar=a["desc"](ctx)[:300],
            actor_user_id=user["user_id"], is_visible_to_citizen=a["vis"]))
        for kind, ntype, ntype_ar, mk in a["notify"]:
            for uid in dict.fromkeys(_users_of(repo, kind, case, req)):
                if uid != user["user_id"]:
                    repo.insert("notifications", dict(user_id=uid, request_id=request_id, notification_type=ntype,
                                                     notification_type_ar=ntype_ar, message_ar=mk(ctx)[:500]))
        repo.update("cases", case["case_id"], {"last_updated_at": ts})
        audit.write(repo, user["user_id"], case["case_id"], request_id, a["audit"], True,
                    f"{a['label']} للطلب {request_id} على القضية {case['case_number']}")
    return repo.get("document_requests", request_id)


# ---------- creation / lawyer PDF ----------

def request_type_options(repo, entity_id):
    return ENTITY_REQUEST_TYPES.get(entity_id) or [GENERIC_TYPE]


def create_request(repo, settings, user, case_id, entity_id, request_type, title, upload=None, submit=False):
    if user["role"] != "LAWYER" or not account_active(repo, user):
        raise Forbidden()
    case = repo.get("cases", case_id) if isinstance(case_id, int) else None
    if not can_access_case(repo, user, case):
        if case:
            audit.write(repo, user["user_id"], case["case_id"], None, "CREATE_DOCUMENT_REQUEST", False,
                        "محاولة إنشاء طلب على قضية غير مسندة للمحامي")
        raise NotFound()
    ent = repo.get("government_entities", entity_id) if isinstance(entity_id, int) else None
    if not ent or ent["entity_type"] != "GOVERNMENT" or not ent["is_active"]:
        raise BadRequest("الجهة المستهدفة غير صالحة")
    if request_type not in [t for t, _ in request_type_options(repo, entity_id)]:
        raise BadRequest("نوع الطلب غير صالح لهذه الجهة")
    title = (title or "").strip()
    if not 5 <= len(title) <= 220:
        raise BadRequest("عنوان الطلب يجب أن يكون بين 5 و220 حرفًا")
    if upload:
        documents.validate_pdf(upload["filename"], upload["content_type"], upload["data"], settings.max_upload_bytes)
    with repo.transaction():
        rid = repo.insert("document_requests", dict(
            case_id=case_id, requested_by_user_id=user["user_id"], target_entity_id=entity_id,
            request_type=request_type, request_title_ar=title, request_status="DRAFT",
            public_status_message_ar="الطلب قيد الإعداد لدى المحامي."))
        repo.insert("request_timeline", dict(request_id=rid, event_code="REQUEST_CREATED",
                    event_description_ar="أنشأ المحامي مسودة طلب كتاب.", actor_user_id=user["user_id"],
                    is_visible_to_citizen=0))
        audit.write(repo, user["user_id"], case_id, rid, "CREATE_DOCUMENT_REQUEST", True,
                    f"إنشاء مسودة طلب كتاب موجه إلى {ent['entity_name_ar']} على القضية {case['case_number']}.")
        if upload:
            _attach(repo, settings, user, rid, upload)
    if submit:
        perform(repo, settings, user, rid, "submit")
    return rid


def _attach(repo, settings, user, rid, upload):
    name = documents.save_pdf(settings, upload["data"])
    for d in repo.select("documents", {"request_id": rid, "document_type": "LAWYER_REQUEST_PDF"}):
        if d["document_status"] != "REVOKED":
            repo.update("documents", d["document_id"], {"document_status": "REVOKED", "document_status_ar": "مسحوب"})
    repo.insert("documents", dict(
        request_id=rid, document_type="LAWYER_REQUEST_PDF", document_type_ar="نسخة PDF لطلب المحامي",
        document_title_ar="طلب كتاب - نسخة مقدم الطلب", file_name=name, uploaded_by_user_id=user["user_id"],
        visibility="COURT_AND_AUTHORIZED_LAWYER", visibility_ar="المحكمة والمحامي الموكل فقط",
        is_printable_by_citizen=0, is_official=0, document_status="UPLOADED", document_status_ar="مرفوع",
        print_permission_note_ar="غير متاح للطباعة للمواطن", attachment_action_ar="معاينة"))


def attach_lawyer_pdf(repo, settings, user, request_id, upload):
    req = repo.get("document_requests", request_id) if isinstance(request_id, int) else None
    if user["role"] != "LAWYER" or not req or not can_access_request(repo, user, req):
        if req:
            audit.write(repo, user["user_id"], req["case_id"], request_id, "UPLOAD_LAWYER_PDF", False, "رفع غير مصرح به")
        raise NotFound()
    if req["request_status"] not in ("DRAFT", "RETURNED_FOR_MODIFICATION"):
        raise BadRequest("لا يمكن تعديل المرفق بعد التقديم")
    if not upload:
        raise BadRequest("اختر ملف PDF")
    documents.validate_pdf(upload["filename"], upload["content_type"], upload["data"], settings.max_upload_bytes)
    with repo.transaction():
        _attach(repo, settings, user, request_id, upload)
        audit.write(repo, user["user_id"], req["case_id"], request_id, "UPLOAD_LAWYER_PDF", True,
                    f"رفع ملف PDF للطلب {request_id}")
