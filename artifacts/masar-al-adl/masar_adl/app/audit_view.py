from .labels import COURT_ROLES


def can_view_audit(user):
    return user["role"] in COURT_ROLES


def audit_rows(repo, user, f):
    """Judge: everything. Clerk: only cases/requests the clerk has acted on."""
    if not can_view_audit(user):
        return None
    rows = repo.select("audit_logs", order_by="-action_at")
    if user["role"] == "COURT_CLERK":
        mine = {r["case_id"] for r in rows if r["actor_user_id"] == user["user_id"]}
        rows = [r for r in rows if r["case_id"] in mine]
    users = {u["user_id"]: u["display_name"] for u in repo.select("users")}
    cases = {c["case_id"]: c["case_number"] for c in repo.select("cases")}
    out = []
    for r in rows:
        if f.get("action") and f["action"].upper() not in r["action_code"]:
            continue
        if f.get("result") in ("SUCCESS", "FAILURE") and r["result"] != f["result"]:
            continue
        if f.get("actor") and str(r["actor_user_id"]) != f["actor"]:
            continue
        if f.get("case") and str(r["case_id"]) != f["case"]:
            continue
        if f.get("request") and str(r["request_id"] or "") != f["request"]:
            continue
        if f.get("date_from") and r["action_at"].strftime("%Y-%m-%d") < f["date_from"]:
            continue
        if f.get("date_to") and r["action_at"].strftime("%Y-%m-%d") > f["date_to"]:
            continue
        r["actor_name"] = users.get(r["actor_user_id"], "")
        r["case_number"] = cases.get(r["case_id"], "")
        out.append(r)
    return out
