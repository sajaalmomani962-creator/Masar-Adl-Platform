import base64
import hashlib
import hmac
import secrets
import threading
import time

from itsdangerous import BadSignature, URLSafeTimedSerializer
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from . import audit
from .authz import account_active

GENERIC_FAIL = "بيانات الدخول غير صحيحة"
_password_hasher = PasswordHasher()


def make_pin_hash(pin: str, n=2 ** 14, r=8, p=1) -> str:
    """New hashes use Argon2id; legacy scrypt hashes remain verifiable."""
    return _password_hasher.hash(pin)


def verify_pin(pin: str, stored: str) -> bool:
    if not isinstance(stored, str):
        return False
    if stored.startswith("$argon2"):
        try:
            return _password_hasher.verify(stored, pin)
        except (Argon2Error, ValueError, TypeError):
            return False
    try:
        scheme, n, r, p, salt, h = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


class RateLimiter:
    def __init__(self, limit, window):
        self.limit, self.window, self._hits, self._lock = limit, window, {}, threading.Lock()

    def _prune(self, key, now):
        self._hits[key] = [t for t in self._hits.get(key, []) if now - t < self.window]

    def blocked(self, key):
        with self._lock:
            now = time.time()
            self._prune(key, now)
            return len(self._hits[key]) >= self.limit

    def hit(self, key):
        with self._lock:
            self._hits.setdefault(key, []).append(time.time())

    def clear(self, key):
        with self._lock:
            self._hits.pop(key, None)


class SessionStore:
    """Server-side sessions: logout/expiry truly invalidate them."""

    def __init__(self, idle, absolute):
        self.idle, self.absolute, self._s, self._lock = idle, absolute, {}, threading.Lock()

    def create(self, user_id):
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._s[token] = {"uid": user_id, "csrf": secrets.token_urlsafe(24), "created": now, "last": now}
        return token

    def get(self, token):
        if not token:
            return None
        with self._lock:
            s = self._s.get(token)
            if not s:
                return None
            now = time.time()
            if now - s["last"] > self.idle or now - s["created"] > self.absolute:
                del self._s[token]
                return None
            s["last"] = now
            return dict(s)

    def flash(self, token, kind, message):
        with self._lock:
            if token in self._s:
                self._s[token].setdefault("flash", []).append((kind, message))

    def pop_flash(self, token):
        with self._lock:
            s = self._s.get(token)
            return s.pop("flash", []) if s else []

    def destroy(self, token):
        with self._lock:
            self._s.pop(token, None)

    def destroy_user(self, user_id):
        with self._lock:
            for t in [t for t, s in self._s.items() if s["uid"] == user_id]:
                del self._s[t]


class LoginService:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store
        self.limiter = RateLimiter(settings.login_max_failures, settings.login_window)
        self._signer = URLSafeTimedSerializer(secrets.token_urlsafe(32), salt="login-csrf")

    def login_token(self):
        return self._signer.dumps("login")

    def check_login_token(self, tok):
        try:
            self._signer.loads(tok or "", max_age=3600)
            return True
        except BadSignature:
            return False

    @staticmethod
    def demo_password(user):
        """Demo-only convention (the schema has no password column): Demo@ + last 4 chars of national_id."""
        return "Demo@" + user["national_id"][-4:]

    def authenticate(self, repo, nid, password, ip):
        """Login = national_id + password. The schema stores no password, so:
        - if DEMO_USERS_JSON has a supported hash for this national_id, that hash is checked;
        - else, ONLY in demo mode, the documented demo password is accepted;
        - else (real DB without hashes) login is refused: never accept an unverifiable password."""
        nid, password = (nid or "").strip(), password or ""
        keys = [f"ip:{ip}", f"nid:{nid.lower()}"]
        if any(self.limiter.blocked(k) for k in keys):
            audit.app_logger().info("LOGIN-BLOCKED ip=%s nid=%s", ip, audit.mask_id(nid))
            return None, "محاولات كثيرة. أعد المحاولة بعد قليل."
        user = repo.one("users", {"national_id": nid}) if nid else None
        ok = bool(user) and account_active(repo, user)
        if ok:
            hashes = self.settings.demo_pins()
            if nid in hashes:
                ok = verify_pin(password, hashes[nid])
            elif getattr(repo, "mode", "") == "demo":
                ok = hmac.compare_digest(password, self.demo_password(user))
            else:
                ok = False
        if not ok:
            for k in keys:
                self.limiter.hit(k)
            audit.app_logger().info("LOGIN-FAILED ip=%s nid=%s", ip, audit.mask_id(nid))
            return None, GENERIC_FAIL
        self.limiter.clear(f"nid:{nid.lower()}")
        audit.app_logger().info("LOGIN-OK user=%s", user["user_id"])
        return user, None
