"""Run the supplied ASGI application on the artifact-managed port."""
import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent / "masar_adl"
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATA_MODE", "demo")
os.chdir(ROOT)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        # One worker: the prototype's demo data, sessions and rate limits are in memory.
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        access_log=False,
    )
