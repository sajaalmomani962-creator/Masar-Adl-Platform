"""Explicit TEST-only cloud durability probe. Never opens SQL or existing files.

The parent writes no PDF cache. A child writes one fresh TEST object and exits;
a second child restores only its known TEST metadata in an injected in-memory
repository and checks authorized HTTP access. The parent deletes its own object.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import documents, private_storage
from app.config import Settings


def settings_for(bucket, root):
    settings = Settings(data_mode="demo", pdf_storage_backend="app_storage",
                        pdf_storage_bucket=bucket, storage_dir=root / "storage", log_dir=root / "logs")
    private_storage.configure(settings, "demo")
    return settings


def write_fixture(bucket, state):
    with TemporaryDirectory(prefix="masar-TEST-cloud-writer-") as directory:
        settings = settings_for(bucket, Path(directory))
        data = documents.sample_pdf_bytes("TEST private cloud restart verification")
        reference = documents.save_pdf(settings, data)
        # State holds TEST metadata only, never credentials or the PDF bytes.
        state.write_text(json.dumps({
            "reference": reference, "sha256": hashlib.sha256(data).hexdigest(),
        }), encoding="utf-8")
        state.chmod(0o600)


def read_fixture(bucket, state):
    import httpx
    from app.main import create_app
    from app.repositories import DemoRepository
    known = json.loads(state.read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="masar-TEST-cloud-reader-") as directory:
        settings = settings_for(bucket, Path(directory))
        repo = DemoRepository()
        assert all(u["national_id"].startswith("TEST-") for u in repo.select("users"))
        # This explicit TEST reference fixture is NOT persistence of demo metadata.
        repo.update("documents", 2, {"file_name": known["reference"]})
        app = create_app(settings, repo=repo)

        async def scenario():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="http://TEST-only") as client:
                async def login(username):
                    page = await client.get("/login")
                    token = re.search(r'name="login_token" value="([^"]+)"', page.text).group(1)
                    response = await client.post("/demo-login", data={"login_token": token, "username": username})
                    assert response.status_code == 303
                await login("citizen_tariq")
                for path in ("/documents/2/view", "/documents/2/download", "/documents/2/raw?for=print"):
                    response = await client.get(path)
                    assert response.status_code == 200
                    assert hashlib.sha256(response.content).hexdigest() == known["sha256"]
                    assert response.headers["content-type"] == "application/pdf"
                    assert response.headers["cache-control"] == "no-store"
                response = await client.get("/documents/2/raw?for=view", headers={"Range": "bytes=0-4"})
                assert response.status_code == 206 and response.content == b"%PDF-"
                assert (await client.get("/documents/2/print")).status_code == 200
                client.cookies.clear()
                await login("citizen_layla")
                assert (await client.get("/documents/2/view")).status_code == 404
                client.cookies.clear()
                await login("citizen_tariq")
                repo.update("documents", 2, {"document_status": "REVOKED"})
                assert (await client.get("/documents/2/raw?for=view")).status_code == 403
            assert not list((settings.storage_dir / ".private-pdf-transfers").glob("*.pdf"))
        asyncio.run(scenario())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket-id", default=os.getenv("MASAR_PDF_BUCKET_ID", ""))
    parser.add_argument("--phase", choices=("writer", "reader"), help=argparse.SUPPRESS)
    parser.add_argument("--state", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.bucket_id:
        parser.error("Configure MASAR_PDF_BUCKET_ID or supply the development TEST bucket identifier")
    if args.phase:
        if args.phase == "writer":
            write_fixture(args.bucket_id, args.state)
        else:
            read_fixture(args.bucket_id, args.state)
        return
    from replit.object_storage import Client
    from urllib.error import HTTPError
    from urllib.request import urlopen
    client = Client(bucket_id=args.bucket_id)
    with TemporaryDirectory(prefix="masar-TEST-cloud-proof-") as directory:
        state = Path(directory) / "TEST-metadata.json"
        settings = settings_for(args.bucket_id, Path(directory))
        results = {}
        try:
            for phase in ("writer", "reader"):
                subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                "--bucket-id", args.bucket_id, "--phase", phase, "--state", str(state)],
                               check=True, capture_output=True, timeout=90)
                results[f"{phase}_process_passed"] = True
            reference = json.loads(state.read_text(encoding="utf-8"))["reference"]
            key = private_storage.object_key(settings, reference)
            # No Authorization header, signed query or cookie is attached.
            try:
                with urlopen(f"https://storage.googleapis.com/{args.bucket_id}/{key}", timeout=20) as response:
                    status = response.status
            except HTTPError as error:
                status = error.code
            assert status in (403, 404), "Anonymous read was not denied"
            results["anonymous_read_denied"] = True
        finally:
            if state.exists():
                reference = json.loads(state.read_text(encoding="utf-8"))["reference"]
                key = private_storage.object_key(settings, reference)
                client.delete(key, ignore_not_found=True)
                results["owned_TEST_object_removed"] = not client.exists(key)
        assert results.get("owned_TEST_object_removed")
        print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Avoid copying SDK/network messages into reports or shell output.
        print(f"TEST private storage verification failed: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
