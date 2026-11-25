import logging
import re

from .schema import MAXLEN

_logger = None


def app_logger(settings=None):
    """Application log for events the audit_logs schema cannot hold (no actor/case)."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("masar.events")
        _logger.setLevel(logging.INFO)
        if settings is not None:
            try:
                settings.log_dir.mkdir(parents=True, exist_ok=True)
                h = logging.FileHandler(settings.log_dir / "app_events.log", encoding="utf-8")
                h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
                _logger.addHandler(h)
            except OSError:
                pass
    return _logger


def mask_id(nid: str) -> str:
    nid = nid or ""
    return re.sub(r".(?=.{4})", "*", nid)


def write(repo, actor_id, case_id, request_id, action, ok, details):
    """Insert into audit_logs. actor_user_id and case_id are NOT NULL in the schema."""
    if actor_id is None or case_id is None:
        app_logger().info("AUDIT-LOCAL %s %s %s", action, "SUCCESS" if ok else "FAILURE", details[:200])
        return
    repo.insert("audit_logs", {
        "actor_user_id": actor_id, "case_id": case_id, "request_id": request_id,
        "action_code": action, "result": "SUCCESS" if ok else "FAILURE",
        "details": details[: MAXLEN[("audit_logs", "details")]],
    })
