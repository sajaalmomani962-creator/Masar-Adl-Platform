"""مدقق سلامة المسار: explicit, explainable rules over timeline + audit + request fields.

Read-only. No AI decides anything; every finding names the rule that produced it, so a human
(judge/clerk) can verify and act. Output is a *suggestion to review*, never a verdict.
"""
from .labels import COURT_ROLES, DOC_TYPE_AR, ENTITY_ROLES, STATUS_AR

HIGH, MED, LOW = "high", "medium", "low"
SEV_AR = {HIGH: "عالية", MED: "متوسطة", LOW: "منخفضة"}
SEV_CLASS = {HIGH: "danger", MED: "warning", LOW: "secondary"}

POST_DECISION = {"APPROVED", "SENT_TO_ENTITY", "UNDER_PROCESSING", "DELAYED", "RESPONSE_RECEIVED"}
SENT_STATES = {"SENT_TO_ENTITY", "UNDER_PROCESSING", "DELAYED", "RESPONSE_RECEIVED"}
NOT_DRAFT = set(STATUS_AR) - {"DRAFT"}
RESPONSE_EVENTS = {"RESPONSE_RECEIVED", "ENTITY_RESPONSE_RECEIVED"}
EVENT_ACTOR = {   # event code -> predicate description key
    "REQUEST_CREATED": "lawyer", "REQUEST_SUBMITTED": "lawyer",
    "REVIEW_STARTED": "clerk", "SENT_TO_ENTITY": "clerk",
    "RETURNED_FOR_MODIFICATION": "court", "RESPONSE_RELEASED": "court", "INTERNAL_NOTE": "court",
    "COURT_APPROVED": "judge", "COURT_REJECTED": "judge",
    "PROCESSING_STARTED": "entity", "PROCESSING_RESUMED": "entity",
    "RESPONSE_RECEIVED": "entity", "ENTITY_RESPONSE_RECEIVED": "entity",
    "REQUEST_DELAYED": "entity_or_clerk",
}


def _f(rule, sev, req, title, detail):
    return {"rule": rule, "severity": sev, "request_id": req["request_id"] if req else None,
            "case_id": req["case_id"] if req else None, "title": title, "detail": detail,
            "severity_ar": SEV_AR[sev], "severity_class": SEV_CLASS[sev]}


def _actor_ok(kind, actor, req, case):
    if not actor:
        return False
    r = actor["role"]
    return {"lawyer": r == "LAWYER" and case["lawyer_user_id"] == actor["user_id"],
            "clerk": r == "COURT_CLERK", "judge": r == "COURT_JUDGE", "court": r in COURT_ROLES,
            "entity": r in ENTITY_ROLES and actor["entity_id"] == req["target_entity_id"],
            "entity_or_clerk": r == "COURT_CLERK" or (r in ENTITY_ROLES and actor["entity_id"] == req["target_entity_id"])
            }.get(kind, True)


def check_request(repo, req, ctx):
    users, cases = ctx["users"], ctx["cases"]
    case = cases[req["case_id"]]
    st = req["request_status"]
    tl = ctx["timeline"].get(req["request_id"], [])
    docs = ctx["docs"].get(req["request_id"], [])
    audits = [a for a in ctx["audit"] if a["request_id"] == req["request_id"]]
    out = []

    # R1 chronology of milestones
    marks = [("التقديم", req["submitted_at"]), ("قرار المحكمة", req["court_decision_at"]),
             ("الإرسال للجهة", req["sent_to_entity_at"]), ("استلام الرد", req["response_received_at"])]
    present = [(n, t) for n, t in marks if t]
    for (n1, t1), (n2, t2) in zip(present, present[1:]):
        if t2 < t1:
            out.append(_f("R1", HIGH, req, "تسلسل زمني معكوس", f"«{n2}» ({t2:%Y-%m-%d %H:%M}) سابق لـ «{n1}» ({t1:%Y-%m-%d %H:%M})."))

    # R2 status needs its stamps
    if st in POST_DECISION and not (req["court_decision_at"] and req["court_decision_by_user_id"]):
        out.append(_f("R2", HIGH, req, "حالة بلا قرار مسجّل", f"الحالة «{STATUS_AR[st]}» لكن لا يوجد قرار محكمة (تاريخ/متخذ القرار)."))
    if req["court_decision_by_user_id"]:
        dec = users.get(req["court_decision_by_user_id"])
        if not dec or dec["role"] != "COURT_JUDGE":
            out.append(_f("R2", HIGH, req, "قرار من غير القاضي", "متخذ قرار المحكمة المسجّل ليس بدور قاضٍ."))
    if st in SENT_STATES and not req["sent_to_entity_at"]:
        out.append(_f("R2", MED, req, "إرسال بلا تاريخ", "الطلب في حالة ما بعد الإرسال دون تاريخ إرسال."))
    if st == "RESPONSE_RECEIVED":
        if not req["response_received_at"]:
            out.append(_f("R2", MED, req, "رد بلا تاريخ استلام", "الحالة «تم استلام الرد» دون تاريخ استلام."))
        if not [d for d in docs if d["document_type"] == "ENTITY_RESPONSE" and d["document_status"] != "REVOKED"]:
            out.append(_f("R3", HIGH, req, "رد بلا مستند", "الحالة «تم استلام الرد» ولا يوجد مستند رد جهة."))
    if (req["delay_days"] or 0) > 0 and st not in ("DELAYED", "UNDER_PROCESSING", "RESPONSE_RECEIVED", "SENT_TO_ENTITY"):
        out.append(_f("R2", LOW, req, "تأخير في حالة غير متوقعة", f"تأخير {req['delay_days']} يوم والحالة «{STATUS_AR[st]}»."))

    # R4 expected timeline events exist
    codes = {e["event_code"] for e in tl}
    missing = []
    if st in NOT_DRAFT and "REQUEST_SUBMITTED" not in codes:
        missing.append("تقديم الطلب")
    if st in POST_DECISION and "COURT_APPROVED" not in codes:
        missing.append("موافقة القاضي")
    if st == "RESPONSE_RECEIVED" and not (codes & RESPONSE_EVENTS):
        missing.append("وصول الرد")
    if st == "DELAYED" and "REQUEST_DELAYED" not in codes:
        missing.append("تسجيل التأخير")
    if missing:
        out.append(_f("R4", MED, req, "أحداث ناقصة في الخط الزمني", "لا يوجد حدث لـ: " + "، ".join(missing) + "."))

    # R5 event actors have the right role / relation
    for e in tl:
        kind = EVENT_ACTOR.get(e["event_code"])
        if kind and not _actor_ok(kind, users.get(e["actor_user_id"]), req, case):
            a = users.get(e["actor_user_id"])
            out.append(_f("R5", HIGH, req, "فاعل لا يطابق الحدث",
                          f"الحدث {e['event_code']} نفّذه «{a['display_name'] if a else '؟'}» ({a['role'] if a else '؟'}) وهذا لا يطابق دور/ارتباط المخوّل به."))

    # R6 audit trail backs the decision
    if req["court_decision_at"] and req["court_decision_by_user_id"]:
        ok = [a for a in audits if a["result"] == "SUCCESS" and a["actor_user_id"] == req["court_decision_by_user_id"]
              and a["action_code"] in ("APPROVE_DOCUMENT_REQUEST", "REJECT_DOCUMENT_REQUEST")]
        if not ok:
            out.append(_f("R6", MED, req, "قرار بلا أثر تدقيق", "لا يوجد في audit_logs سجل نجاح لقرار المحكمة من متخذه."))
    for d in docs:
        up = users.get(d["uploaded_by_user_id"])
        if d["document_type"] == "ENTITY_RESPONSE" and not _actor_ok("entity", up, req, case):
            out.append(_f("R5", HIGH, req, "رفع رد من غير الجهة", f"المستند {d['document_id']} رفعه من ليس موظفًا في الجهة المستهدفة."))
        if d["document_type"] == "LAWYER_REQUEST_PDF" and not _actor_ok("lawyer", up, req, case):
            out.append(_f("R5", HIGH, req, "ملف محامٍ من غير المسند", f"المستند {d['document_id']} رفعه من ليس محامي القضية."))
        if d["is_printable_by_citizen"] and d["document_type"] == "LAWYER_REQUEST_PDF":
            out.append(_f("R7", HIGH, req, "مستند داخلي متاح للطباعة للمواطن", f"المستند {d['document_id']} من نوع ملف المحامي ومعلَّم للطباعة."))
    return out


def check_audit_access(ctx):
    """R8: a successful access by someone not bound to that case/request."""
    out = []
    for a in ctx["audit"]:
        if a["result"] != "SUCCESS":
            continue
        u, case = ctx["users"].get(a["actor_user_id"]), ctx["cases"].get(a["case_id"])
        if not u or not case:
            continue
        bad = (u["role"] == "CITIZEN" and case["citizen_user_id"] != u["user_id"]) or \
              (u["role"] == "LAWYER" and case["lawyer_user_id"] != u["user_id"])
        if u["role"] in ENTITY_ROLES and a["request_id"]:
            req = ctx["requests"].get(a["request_id"])
            bad = bad or (req and req["target_entity_id"] != u["entity_id"])
        if bad:
            out.append({"rule": "R8", "severity": HIGH, "severity_ar": SEV_AR[HIGH], "severity_class": SEV_CLASS[HIGH],
                        "request_id": a["request_id"], "case_id": a["case_id"],
                        "title": "نجاح وصول بلا ارتباط بالقضية",
                        "detail": f"سجل التدقيق #{a['audit_id']}: «{u['display_name']}» ({u['role']}) نجح في «{a['action_code']}» على قضية {case['case_number']} غير مرتبطة به."})
    return out


def build_context(repo):
    reqs = repo.select("document_requests")
    tl = {}
    for e in repo.select("request_timeline", order_by="event_at"):
        tl.setdefault(e["request_id"], []).append(e)
    docs = {}
    for d in repo.select("documents"):
        docs.setdefault(d["request_id"], []).append(d)
    return {"users": {u["user_id"]: u for u in repo.select("users")},
            "cases": {c["case_id"]: c for c in repo.select("cases")},
            "requests": {r["request_id"]: r for r in reqs}, "timeline": tl, "docs": docs,
            "audit": repo.select("audit_logs", order_by="action_at")}


def run(repo, only_cases=None):
    ctx = build_context(repo)
    findings = []
    for r in ctx["requests"].values():
        if only_cases is None or r["case_id"] in only_cases:
            findings += check_request(repo, r, ctx)
    for f in check_audit_access(ctx):
        if only_cases is None or f["case_id"] in only_cases:
            findings.append(f)
    order = {HIGH: 0, MED: 1, LOW: 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["request_id"] or 0))
    return findings


def custody_report(repo, req):
    """سلسلة العهدة: one merged, time-ordered story of who did what to this request."""
    ctx = build_context(repo)
    users = ctx["users"]
    rows = []
    for label, key in (("تقديم الطلب", "submitted_at"), ("قرار المحكمة", "court_decision_at"),
                       ("الإرسال للجهة", "sent_to_entity_at"), ("استلام الرد", "response_received_at")):
        if req[key]:
            rows.append({"at": req[key], "kind": "معلَم", "text": label, "who": ""})
    for e in ctx["timeline"].get(req["request_id"], []):
        rows.append({"at": e["event_at"], "kind": "حدث", "text": e["event_description_ar"],
                     "who": users.get(e["actor_user_id"], {}).get("display_name", "")})
    for a in ctx["audit"]:
        if a["request_id"] == req["request_id"]:
            rows.append({"at": a["action_at"], "kind": "تدقيق " + ("✓" if a["result"] == "SUCCESS" else "✗"),
                         "text": f"{a['action_code']} — {a['details']}", "who": users.get(a["actor_user_id"], {}).get("display_name", "")})
    for d in ctx["docs"].get(req["request_id"], []):
        rows.append({"at": d["uploaded_at"], "kind": "مستند", "text": f"{DOC_TYPE_AR.get(d['document_type'], d['document_type'])} ({d['document_status']})",
                     "who": users.get(d["uploaded_by_user_id"], {}).get("display_name", "")})
    rows.sort(key=lambda r: r["at"])
    return rows


def scope_cases(repo, user):
    """None = all cases (judge). Clerk: only cases the clerk acted on (same rule as the audit page)."""
    if user["role"] == "COURT_JUDGE":
        return None
    return {a["case_id"] for a in repo.select("audit_logs") if a["actor_user_id"] == user["user_id"]}


def summarize(findings):
    c = {HIGH: 0, MED: 0, LOW: 0}
    for f in findings:
        c[f["severity"]] += 1
    return c
