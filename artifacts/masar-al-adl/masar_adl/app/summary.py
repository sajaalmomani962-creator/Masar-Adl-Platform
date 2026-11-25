"""Read models for the dashboards and the citizen 'case follow-up summary' card.

All text comes from stored fields or fixed templates; nothing is inferred or invented.
"""
from .authz import Decision, can_access_case, can_access_request, document_decision, sees_full_timeline, sees_internal
from .labels import (COURT_ROLES, DELAY_REASONS, ENTITY_ROLES, STATUS_AR, STATUS_CLASS)

NA = "غير متاحة"


def delay_view(req):
    n = req["delay_days"] or 0
    if n <= 0:
        return None
    reason = DELAY_REASONS.get(req["delay_reason_code"]) if req["delay_reason_code"] else None
    return {"days": n, "reason": reason or NA,
            "note": "قيمة مسجّلة في النظام لأغراض المتابعة وليست مهلة قانونية أو رسمية."}


def timeline_for(repo, user, request_id):
    rows = repo.select("request_timeline", {"request_id": request_id}, order_by="event_at")
    if user["role"] == "CITIZEN":
        rows = [r for r in rows if r["is_visible_to_citizen"] == 1]
    actors = {u["user_id"]: u for u in repo.select("users")}
    for r in rows:
        r["actor_name"] = actors.get(r["actor_user_id"], {}).get("display_name", "") if user["role"] != "CITIZEN" else ""
    return rows


def documents_for(repo, user, req):
    """Documents the user may at least view; flags tell which buttons to render (server re-checks)."""
    out = []
    for d in repo.select("documents", {"request_id": req["request_id"]}, order_by="uploaded_at"):
        flags = {}
        for act in ("view", "download", "print"):
            dec, _, _ = document_decision(repo, user, d, req, act)
            flags[act] = dec == Decision.ALLOW
        if flags["view"]:
            d["can"] = flags
            out.append(d)
    return out


def request_view(repo, user, req):
    entity = repo.get("government_entities", req["target_entity_id"])
    v = {
        "req": req, "status_ar": STATUS_AR[req["request_status"]], "status_class": STATUS_CLASS[req["request_status"]],
        "entity_name": entity["entity_name_ar"] if entity else NA,
        "delay": delay_view(req),
        "timeline": timeline_for(repo, user, req["request_id"]),
        "documents": documents_for(repo, user, req),
    }
    if not sees_internal(user):
        v["req"] = {k: val for k, val in req.items() if k != "internal_note"}
    return v


def case_summary(repo, user, case):
    """Citizen/lawyer 'ملخص متابعة القضية' card; also reused for court staff."""
    reqs = [r for r in repo.select("document_requests", {"case_id": case["case_id"]}, order_by="-submitted_at")
            if can_access_request(repo, user, r)]
    views = [request_view(repo, user, r) for r in reqs]
    ids = {r["request_id"] for r in reqs}
    notes = [n for n in repo.select("notifications", {"user_id": user["user_id"]}, order_by="-created_at")
             if n["request_id"] in ids]
    return {"case": case, "requests": views, "notifications": notes,
            "public_summary": case["public_summary_ar"] or NA}


def cases_for(repo, user):
    return [c for c in repo.select("cases", order_by="case_id") if can_access_case(repo, user, c)]


def requests_for(repo, user):
    return [r for r in repo.select("document_requests", order_by="-submitted_at") if can_access_request(repo, user, r)]


def row_view(repo, req):
    case = repo.get("cases", req["case_id"])
    ent = repo.get("government_entities", req["target_entity_id"])
    return {"req": req, "case_number": case["case_number"], "entity_name": ent["entity_name_ar"],
            "status_ar": STATUS_AR[req["request_status"]], "status_class": STATUS_CLASS[req["request_status"]],
            "delay": delay_view(req)}
