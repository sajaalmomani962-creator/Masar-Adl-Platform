"""Print an Argon2id hash for the optional demo password. Put the output in DEMO_USERS_JSON, e.g.
   {"TEST-NID-9901001001": "<hash printed here>"}
Never commit PINs or hashes."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.auth import make_pin_hash  # noqa: E402

print(make_pin_hash(getpass.getpass("PIN: ")))
