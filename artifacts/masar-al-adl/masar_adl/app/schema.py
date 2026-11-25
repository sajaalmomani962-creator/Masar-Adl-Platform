"""Schema metadata mirrored from db/judicial_exchange_sqlserver.sql (read-only reference).

Used for (a) whitelisting table/column names in SQLServerRepository and
(b) making DemoRepository enforce the same NOT NULL / CHECK rules as the real DB.
"""
from datetime import datetime


def now():
    return datetime.now().replace(microsecond=0)


ROLES = ["CITIZEN", "LAWYER", "COURT_CLERK", "COURT_JUDGE", "LAND_OFFICER",
         "CIVIL_STATUS_OFFICER", "GOV_ENTITY_OFFICER"]
REQUEST_STATUSES = ["DRAFT", "SUBMITTED", "UNDER_COURT_REVIEW", "APPROVED", "REJECTED",
                    "SENT_TO_ENTITY", "UNDER_PROCESSING", "DELAYED", "RESPONSE_RECEIVED",
                    "RETURNED_FOR_MODIFICATION"]
DOC_TYPES = ["LAWYER_REQUEST_PDF", "ENTITY_RESPONSE", "PUBLIC_STATUS_CERTIFICATE"]
VISIBILITIES = ["AUTHORIZED_PARTIES", "COURT_AND_AUTHORIZED_LAWYER", "CITIZEN_AND_LAWYER"]
DOC_STATUSES = ["UPLOADED", "RECEIVED", "AVAILABLE", "REVOKED"]

TABLES = {
    "government_entities": dict(
        pk="entity_id",
        cols=["entity_code", "entity_name_ar", "entity_name_en", "entity_type", "is_active"],
        notnull=["entity_code", "entity_name_ar", "entity_name_en", "entity_type"],
        defaults={"is_active": 1}),
    "users": dict(
        pk="user_id",
        cols=["national_id", "username", "display_name", "role", "role_ar", "entity_id",
              "is_active", "created_at"],
        notnull=["national_id", "username", "display_name", "role", "role_ar"],
        defaults={"is_active": 1, "created_at": now}),
    "cases": dict(
        pk="case_id",
        cols=["case_number", "court_name", "court_type_ar", "court_location_ar", "case_type",
              "case_type_ar", "case_year", "registry_type", "registry_type_ar", "opened_date",
              "case_status", "case_status_ar", "citizen_user_id", "lawyer_user_id",
              "public_summary_ar", "party_search_type_ar", "last_updated_at"],
        notnull=["case_number", "court_name", "court_type_ar", "court_location_ar", "case_type",
                 "case_type_ar", "case_year", "registry_type", "registry_type_ar", "opened_date",
                 "case_status", "case_status_ar", "citizen_user_id", "lawyer_user_id",
                 "public_summary_ar"],
        defaults={"last_updated_at": now}),
    "case_parties": dict(
        pk="case_party_id",
        cols=["case_id", "user_id", "party_role", "party_role_ar", "is_primary", "party_name_ar",
              "party_identifier", "institution_name_ar", "party_category", "party_category_ar"],
        notnull=["case_id", "party_role", "party_role_ar", "party_name_ar", "party_category_ar"],
        defaults={"is_primary": 0, "party_category": "PERSON"}),
    "document_requests": dict(
        pk="request_id",
        cols=["case_id", "requested_by_user_id", "target_entity_id", "request_type",
              "request_title_ar", "request_status", "submitted_at", "court_decision_by_user_id",
              "court_decision_at", "sent_to_entity_at", "response_received_at", "delay_days",
              "delay_reason_code", "public_status_message_ar", "internal_note"],
        notnull=["case_id", "requested_by_user_id", "target_entity_id", "request_type",
                 "request_title_ar", "request_status", "public_status_message_ar"],
        defaults={"submitted_at": now, "delay_days": 0}),
    "documents": dict(
        pk="document_id",
        cols=["request_id", "document_type", "document_type_ar", "document_title_ar", "file_name",
              "uploaded_by_user_id", "visibility", "visibility_ar", "is_printable_by_citizen",
              "is_official", "document_status", "document_status_ar", "print_permission_note_ar",
              "attachment_notes_ar", "attachment_action_ar", "uploaded_at"],
        notnull=["request_id", "document_type", "document_type_ar", "document_title_ar",
                 "file_name", "uploaded_by_user_id", "visibility", "visibility_ar",
                 "document_status", "document_status_ar"],
        defaults={"is_printable_by_citizen": 0, "is_official": 0, "uploaded_at": now}),
    "request_timeline": dict(
        pk="timeline_id",
        cols=["request_id", "event_code", "event_description_ar", "actor_user_id", "event_at",
              "is_visible_to_citizen"],
        notnull=["request_id", "event_code", "event_description_ar", "actor_user_id"],
        defaults={"event_at": now, "is_visible_to_citizen": 0}),
    "audit_logs": dict(
        pk="audit_id",
        cols=["actor_user_id", "case_id", "request_id", "action_code", "action_at", "result",
              "details"],
        notnull=["actor_user_id", "case_id", "action_code", "result", "details"],
        defaults={"action_at": now}),
    "notifications": dict(
        pk="notification_id",
        cols=["user_id", "request_id", "notification_type", "notification_type_ar", "message_ar",
              "created_at", "is_read"],
        notnull=["user_id", "request_id", "notification_type", "notification_type_ar",
                 "message_ar"],
        defaults={"created_at": now, "is_read": 0}),
    "document_permissions": dict(
        pk="permission_id",
        cols=["role", "document_type", "can_view", "can_download", "can_print"],
        notnull=["role", "document_type"],
        defaults={"can_view": 0, "can_download": 0, "can_print": 0}),
}

CHECKS = {
    ("government_entities", "entity_type"): {"JUDICIAL", "GOVERNMENT"},
    ("users", "role"): set(ROLES),
    ("cases", "case_type"): {"REAL_ESTATE", "CIVIL", "INHERITANCE", "ADMINISTRATIVE", "PERSONAL_STATUS"},
    ("cases", "registry_type"): {"BIDAYAH", "SULH", "APPEAL"},
    ("cases", "case_status"): {"REGISTERED", "IN_PROGRESS", "WAITING_FOR_DOCUMENTS", "UNDER_REVIEW", "COMPLETED"},
    ("case_parties", "party_role"): {"CLAIMANT", "DEFENDANT", "AUTHORIZED_LAWYER", "OTHER"},
    ("case_parties", "party_category"): {"PERSON", "INSTITUTION"},
    ("document_requests", "request_status"): set(REQUEST_STATUSES),
    ("documents", "document_type"): set(DOC_TYPES),
    ("documents", "visibility"): set(VISIBILITIES),
    ("documents", "document_status"): set(DOC_STATUSES),
    ("audit_logs", "result"): {"SUCCESS", "FAILURE"},
    ("document_permissions", "role"): set(ROLES),
    ("document_permissions", "document_type"): set(DOC_TYPES),
}

MAXLEN = {
    ("document_requests", "public_status_message_ar"): 500,
    ("document_requests", "internal_note"): 1000,
    ("document_requests", "request_title_ar"): 220,
    ("request_timeline", "event_description_ar"): 300,
    ("audit_logs", "details"): 500,
    ("notifications", "message_ar"): 500,
    ("documents", "document_title_ar"): 220,
    ("documents", "file_name"): 255,
}


def validate_row(table: str, row: dict, partial: bool = False):
    """Raise ValueError if row violates NOT NULL / CHECK / length rules (demo mirror of the DB)."""
    meta = TABLES[table]
    for col, val in row.items():
        if col == meta["pk"]:
            continue
        if col not in meta["cols"]:
            raise ValueError(f"unknown column {table}.{col}")
        if (col in meta["notnull"]) and val is None:
            raise ValueError(f"NOT NULL violated {table}.{col}")
        allowed = CHECKS.get((table, col))
        if allowed is not None and val is not None and val not in allowed:
            raise ValueError(f"CHECK violated {table}.{col}={val!r}")
        mx = MAXLEN.get((table, col))
        if mx and isinstance(val, str) and len(val) > mx:
            raise ValueError(f"value too long {table}.{col}")
    if not partial:
        for col in meta["notnull"]:
            if row.get(col) is None:
                raise ValueError(f"NOT NULL violated {table}.{col}")
    if table == "documents" and row.get("is_printable_by_citizen") and row.get("visibility") not in (None, "CITIZEN_AND_LAWYER"):
        raise ValueError("CHECK violated chk_citizen_print_visibility")
    if table == "document_permissions" and not partial:
        if (row.get("can_print") and not row.get("can_download")) or (row.get("can_download") and not row.get("can_view")):
            raise ValueError("CHECK violated chk_permission_consistency")
