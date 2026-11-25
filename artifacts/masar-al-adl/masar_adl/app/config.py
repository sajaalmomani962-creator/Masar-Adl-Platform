"""Settings from environment variables (use Replit Secrets). No credentials in code."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(name, default=False):
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    data_mode: str = field(default_factory=lambda: os.getenv("DATA_MODE", "auto").strip().lower())
    sql_host: str = field(default_factory=lambda: os.getenv("SQL_SERVER_HOST", ""))
    sql_port: str = field(default_factory=lambda: os.getenv("SQL_SERVER_PORT", "1433"))
    sql_database: str = field(default_factory=lambda: os.getenv("SQL_SERVER_DATABASE", "JudicialExchangeDB"))
    sql_username: str = field(default_factory=lambda: os.getenv("SQL_SERVER_USERNAME", ""))
    sql_password: str = field(default_factory=lambda: os.getenv("SQL_SERVER_PASSWORD", ""))
    sql_driver: str = field(default_factory=lambda: os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 18 for SQL Server"))
    sql_trust_cert: bool = field(default_factory=lambda: _bool("SQL_SERVER_TRUST_CERT", False))
    sql_timeout: int = field(default_factory=lambda: int(os.getenv("SQL_SERVER_TIMEOUT", "5")))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage"))))
    log_dir: Path = field(default_factory=lambda: Path(os.getenv("LOG_DIR", str(BASE_DIR / "logs"))))
    secure_cookies: bool = field(default_factory=lambda: _bool("SECURE_COOKIES", False))
    idle_timeout: int = field(default_factory=lambda: int(os.getenv("SESSION_IDLE_SECONDS", "1800")))
    absolute_timeout: int = field(default_factory=lambda: int(os.getenv("SESSION_MAX_SECONDS", "28800")))
    max_upload_bytes: int = 10 * 1024 * 1024
    login_max_failures: int = field(default_factory=lambda: int(os.getenv("LOGIN_MAX_FAILURES", "6")))
    login_window: int = 300

    def demo_pins(self) -> dict:
        """Optional extra verification: DEMO_USERS_JSON = {"<national_id>": "scrypt$..."} (hashes only)."""
        raw = os.getenv("DEMO_USERS_JSON", "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except ValueError:
            return {}
