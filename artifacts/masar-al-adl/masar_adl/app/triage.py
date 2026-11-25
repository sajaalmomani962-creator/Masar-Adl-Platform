"""محرك الفرز الذكي: Smart Triage & Priority Scoring.

Explainable, rule-based scoring (0-100) over fields that already exist in the schema. Every point comes
from a named factor, so the reason shown to the user is exactly what produced the score.
STRICTLY ADVISORY and read-only: it never approves/rejects/sends/changes a status or any permission;
it only orders and explains. The final decision stays with the authorised user.
"""
import os
from datetime import datetime

from .labels import COURT_ROLES, ENTITY_ROLES, STATUS_AR

HIGH_AT, MEDIUM_AT = 45, 20
LEVEL_AR = {"high": "مرتفعة", "medium": "متوسطة", "normal": "عادية", "none": "لا إجراء مطلوب"}
LEVEL_CLASS = {"high": "danger", "medium": "warning", "normal": "primary", "none": "secondary"}
ACTIVE = {"SUBMITTED", "UNDER_COURT_REVIEW", "APPROVED", "SENT_TO_ENTITY", "UNDER_PROCESSING", "DELAYED",
          "RETURNED_FOR_MODIFICATION", "RESPONSE_RECEIVED"}
OPEN_AT_ENTITY = {"SENT_TO_ENTITY", "UNDER_PROCESSING", "DELAYED"}
# statuses that need an action from the viewer's role (+15)
OWNER_ACTION = {
    "COURT_CLERK": {"SUBMITTED", "APPROVED", "RESPONSE_RECEIVED"},
    "COURT_JUDGE": {"UNDER_COURT_REVIEW"},
    **{r: {"SENT_TO_ENTITY", "UNDER_PROCESSING", "DELAYED"} for r in ENTITY_ROLES},
}


def as_of(repo):
    """Real clock on a real database; in demo mode the latest timestamp in the data (stable, repeatable demo)."""
    env = os.getenv("TRIAGE_AS_OF", "").strip()
    if env:
        return datetime.fromisoformat(env)
    if getattr(repo, "mode", "") != "demo":
        return datetime.now()
    stamps = []
    for r in repo.select("document_requests"):
        stamps += [r[k] for k in ("submitted_at", "court_decision_at", "sent_to_entity_at", "response_received_at") if r.get(k)]
    stamps += [e["event_at"] for e in repo.select("request_timeline")]
    return max(stamps) if stamps else datetime.now()


def _last_stage_time(req, events):
    stamps = [e["event_at"] for e in events] + [req[k] for k in
              ("submitted_at", "court_decision_at", "sent_to_entity_at", "response_received_at") if req.get(k)]
    return max(stamps) if stamps else None


def score_request(req, viewer_role, now, events, docs, open_at_entity):
    st = req["request_status"]
    if st not in ACTIVE:
        return {"score": 0, "level": "none", "reasons": [], "text": "لا إجراء مطلوب على هذا الطلب الآن."}
    unreleased = st == "RESPONSE_RECEIVED" and any(
        d["document_type"] == "ENTITY_RESPONSE" and d["visibility"] == "COURT_AND_AUTHORIZED_LAWYER"
        and d["document_status"] != "REVOKED" for d in docs)
    if st == "RESPONSE_RECEIVED" and not unreleased:
        return {"score": 0, "level": "none", "reasons": [], "text": "لا إجراء مطلوب على هذا الطلب الآن."}
    pts, why = 0, []

    d = req["delay_days"] or 0
    if d > 0:
        p = min(30, d * 4)
        pts += p
        why.append((p, f"تأخير مسجّل {d} يوم"))
    last = _last_stage_time(req, events)
    if last:
        w = max(0, (now - last).days)
        if w > 0:
            p = min(25, round(w * 1.5))
            pts += p
            why.append((p, f"مرّت {w} يوم دون أي حدث جديد على الطلب"))
    if st == "DELAYED":
        pts += 15
        why.append((15, "الحالة «متأخر»"))
    if st == "RETURNED_FOR_MODIFICATION":
        pts += 15
        why.append((15, "أُعيد الطلب للتعديل"))
    if unreleased and viewer_role in COURT_ROLES:
        pts += 15
        why.append((15, "رد الجهة وصل ولم يُراجَع ويُتَح للمواطن بعد"))
    if st in OWNER_ACTION.get(viewer_role, set()) and not (unreleased and viewer_role in COURT_ROLES):
        pts += 15
        why.append((15, f"الطلب بانتظار إجراء من دورك (الحالة: {STATUS_AR[st]})"))
    if viewer_role in COURT_ROLES and (req.get("internal_note") or "").strip():
        pts += 5
        why.append((5, "توجد ملاحظة مراجعة داخلية على الطلب"))
    if open_at_entity >= 2:
        pts += 5
        why.append((5, f"على الجهة {open_at_entity} طلبات مفتوحة"))

    pts = min(100, pts)
    level = "high" if pts >= HIGH_AT else "medium" if pts >= MEDIUM_AT else "normal"
    why.sort(key=lambda x: -x[0])
    reasons = [t for _, t in why]
    text = (f"أولوية {LEVEL_AR[level]} بسبب: " + "، ".join(reasons[:3]) + ".") if reasons else "أولوية عادية: لا مؤشرات تأخير."
    return {"score": pts, "level": level, "reasons": reasons, "text": text}


def triage_map(repo, viewer, requests):
    """{request_id: result} for the (already access-filtered) requests the viewer may see."""
    now = as_of(repo)
    tl, docs = {}, {}
    for e in repo.select("request_timeline"):
        tl.setdefault(e["request_id"], []).append(e)
    for d in repo.select("documents"):
        docs.setdefault(d["request_id"], []).append(d)
    open_by_entity = {}
    for r in repo.select("document_requests"):
        if r["request_status"] in OPEN_AT_ENTITY:
            open_by_entity[r["target_entity_id"]] = open_by_entity.get(r["target_entity_id"], 0) + 1
    out = {}
    for r in requests:
        res = score_request(r, viewer["role"], now, tl.get(r["request_id"], []), docs.get(r["request_id"], []),
                            open_by_entity.get(r["target_entity_id"], 0))
        res.update(level_ar=LEVEL_AR[res["level"]], level_class=LEVEL_CLASS[res["level"]], as_of=now)
        out[r["request_id"]] = res
    return out


def attach(rows, tmap):
    """Add .triage to row views and sort most urgent first (stable; ties keep the original order)."""
    for r in rows:
        r["triage"] = tmap[r["req"]["request_id"]]
    return sorted(rows, key=lambda r: -r["triage"]["score"])
