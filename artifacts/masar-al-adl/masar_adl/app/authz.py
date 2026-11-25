"""Central RBAC + ABAC engine. Deny by default. No AI involved in any decision."""
from enum import Enum

from .labels import COURT_ROLES, ENTITY_ROLES


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"  # allowed in kind, but waits for a human decision (e.g. judge)


# statuses at which the target entity may see a request at all
ENTITY_VISIBLE = {"SENT_TO_ENTITY", "UNDER_PROCESSING", "DELAYED", "RESPONSE_RECEIVED"}
# statuses a citizen may see (drafts are never shown)
CITIZEN_HIDDEN = {"DRAFT"}


def account_active(repo, user) -> bool:
    if not user or not user.get("is_active"):
        return False
    if user.get("entity_id") is not None:
        ent = repo.get("government_entities", user["entity_id"])
        if not ent or not ent["is_active"]:
            return False
    if user["role"] in ENTITY_ROLES:
        ent = repo.get("government_entities", user["entity_id"]) if user.get("entity_id") else None
        if not ent or ent["entity_type"] != "GOVERNMENT":
            return False
    return True


def can_access_case(repo, user, case) -> bool:
    if not case or not account_active(repo, user):
        return False
    role = user["role"]
    if role == "CITIZEN":
        return case["citizen_user_id"] == user["user_id"]
    if role == "LAWYER":
        return case["lawyer_user_id"] == user["user_id"]
    return role in COURT_ROLES  # single-court demo: court staff see all cases


def can_access_request(repo, user, req) -> bool:
    if not req or not account_active(repo, user):
        return False
    role = user["role"]
    if role in ENTITY_ROLES:
        return (req["target_entity_id"] == user["entity_id"]) and req["request_status"] in ENTITY_VISIBLE
    case = repo.get("cases", req["case_id"])
    if not can_access_case(repo, user, case):
        return False
    if role == "CITIZEN" and req["request_status"] in CITIZEN_HIDDEN:
        return False
    return True


def sees_internal(user) -> bool:
    return user["role"] in COURT_ROLES


def sees_full_timeline(user) -> bool:
    return user["role"] in COURT_ROLES or user["role"] == "LAWYER" or user["role"] in ENTITY_ROLES


def document_decision(repo, user, doc, req, action):
    """Return (Decision, reason_ar, related) for action in {'view','download','print'}.

    related=False means the user has no relation to the record at all (caller answers 404).
    """
    if not can_access_request(repo, user, req):
        return Decision.DENY, "السجل غير متاح", False
    perm = repo.one("document_permissions", {"role": user["role"], "document_type": doc["document_type"]})
    flag = {"view": "can_view", "download": "can_download", "print": "can_print"}[action]
    if not perm or not perm[flag]:
        return Decision.DENY, "لا تملك صلاحية على هذا النوع من المستندات", True
    role = user["role"]
    status, vis = doc["document_status"], doc["visibility"]
    if status == "REVOKED" and role not in COURT_ROLES:
        return Decision.DENY, "المستند مسحوب", True
    if role == "CITIZEN":
        if vis != "CITIZEN_AND_LAWYER":
            return Decision.DENY, "المستند غير مخصص للمواطن", True
        if status not in ("RECEIVED", "AVAILABLE"):
            return Decision.DENY, "المستند غير متاح بعد", True
        if action == "print" and not doc["is_printable_by_citizen"]:
            return Decision.DENY, "هذا المستند غير متاح للطباعة للمواطن", True
    elif role in ENTITY_ROLES:
        if doc["document_type"] != "ENTITY_RESPONSE" or vis != "CITIZEN_AND_LAWYER":
            return Decision.DENY, "المستند غير مخصص للجهة", True
    return Decision.ALLOW, "", True
