"""Build a source-only submission and optionally verify its extracted copy.

No SQL, credentials, uploaded files, sessions or cloud operations are used.
Generated archives/evidence stay under the ignored generated-artifacts directory.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts" / "submission"
PREFIX = "masar-al-adl"
ARCHIVE = OUT / "masar-al-adl-competition.zip"
ROOT_FILES = {
    "README.md", "requirements.txt", "pyproject.toml", "uv.lock",
    "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
    ".gitignore", ".replitignore",
    "tsconfig.json", "tsconfig.base.json",
    "COMPETITION_GUIDE_AR.md", "FINAL_DELIVERY_REPORT.md",
    "PERSISTENT_PDF_STORAGE.md", "FINALIZATION_REPORT.md",
}
SOURCE_ROOTS = ("artifacts/", "lib/", "scripts/")
DENIED_PARTS = {
    "node_modules", "__pycache__", ".pytest_cache", "storage", "logs",
    ".git", ".agents", ".local", "generated-artifacts", "test-results",
    "playwright-report", "dist", ".cache",
}


def source_paths():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    for relative in sorted(set(result.stdout.decode().split("\0")) - {""}):
        path = PurePosixPath(relative)
        if relative not in ROOT_FILES and not relative.startswith(SOURCE_ROOTS):
            continue
        if any(part in DENIED_PARTS for part in path.parts):
            continue
        if any(part == ".env" or part.startswith(".env.") for part in path.parts):
            continue
        if path.suffix in {".pyc", ".log", ".sqlite", ".sqlite3", ".db"}:
            continue
        source = ROOT / relative
        if source.is_file() and source.resolve().is_relative_to(ROOT):
            yield relative, source


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verification.json").unlink(missing_ok=True)
    entries = dict(source_paths())
    library = ROOT / "artifacts/masar-al-adl/node_modules/pdfjs-dist"
    for name in ("build/pdf.min.mjs", "build/pdf.worker.min.mjs", "LICENSE"):
        source = library / name
        if not source.is_file():
            raise RuntimeError("Install the pinned workspace PDF.js package before packaging.")
        entries[f"artifacts/masar-al-adl/node_modules/pdfjs-dist/{name}"] = source
    manifest = {}
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, source in sorted(entries.items()):
            content = source.read_bytes()
            manifest[name] = hashlib.sha256(content).hexdigest()
            bundle.writestr(f"{PREFIX}/{name}", content)
        bundle.writestr(f"{PREFIX}/SUBMISSION_MANIFEST.json", json.dumps(
            {"algorithm": "sha256", "files": manifest}, indent=2, ensure_ascii=False,
        ))
    return manifest


SMOKE = r'''
import asyncio, json, re, tempfile
from pathlib import Path
import httpx
from app.config import Settings
from app.main import create_app
from app.repositories import DemoRepository

async def run():
    with tempfile.TemporaryDirectory(prefix="masar-TEST-submission-") as directory:
        root = Path(directory)
        repo = DemoRepository()
        users = repo.select("users")
        assert all(user["national_id"].startswith("TEST-") for user in users)
        app = create_app(Settings(data_mode="demo", pdf_storage_backend="local",
            storage_dir=root/"storage", log_dir=root/"logs"), repo=repo)
        for user in users:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                    base_url="http://TEST-only") as client:
                page = await client.get("/login?demo=1")
                assert page.status_code == 200 and "TEST-NID-" in page.text
                token = re.search(r'name="login_token" value="([^"]+)"', page.text).group(1)
                login = await client.post("/demo-login",
                    data={"login_token":token, "username":user["username"]})
                assert login.status_code == 303, user["username"]
                dashboard = await client.get(login.headers["location"], follow_redirects=True)
                assert dashboard.status_code == 200 and dashboard.url.path != "/login"
                if user["username"] == "citizen_tariq":
                    for mode in ("view", "download"):
                        pdf = await client.get(f"/documents/2/{mode}")
                        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
                        assert pdf.headers["cache-control"] == "no-store"
                    for mode in ("print", "preview"):
                        assert (await client.get(f"/documents/2/{mode}")).status_code == 200
                if user["username"] == "citizen_layla":
                    assert (await client.get("/documents/2/view")).status_code == 404
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url="http://TEST-only") as client:
            health = await client.get("/health")
            assert health.status_code == 200 and health.json()["data_mode"] == "demo"
            for asset in ("pdf.mjs", "pdf.worker.mjs"):
                assert (await client.get("/static/vendor/pdfjs/"+asset)).status_code == 200
        print(json.dumps({"TEST_accounts":len(users), "login_and_dashboards":"passed",
            "PDF_HTTP_routes_and_renderer_assets":"passed", "unrelated_citizen_denied":True,
            "SQL_or_cloud_operations":False}))
asyncio.run(run())
'''


def verify(manifest):
    with tempfile.TemporaryDirectory(prefix="masar-submission-extracted-") as directory:
        with zipfile.ZipFile(ARCHIVE) as bundle:
            assert bundle.testzip() is None
            for member in bundle.namelist():
                path = PurePosixPath(member)
                assert not path.is_absolute() and ".." not in path.parts
            bundle.extractall(directory)
        extracted = Path(directory) / PREFIX
        for name, digest in manifest.items():
            assert hashlib.sha256((extracted / name).read_bytes()).hexdigest() == digest, name
        application = extracted / "artifacts/masar-al-adl/masar_adl"
        tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                               cwd=application, text=True, capture_output=True)
        print(tests.stdout)
        if tests.returncode:
            raise RuntimeError("Extracted suite failed; do not deliver this package.")
        smoke = subprocess.run([sys.executable, "-c", SMOKE], cwd=application,
                               text=True, capture_output=True)
        if smoke.returncode:
            # Avoid printing application internals or environmental values.
            raise RuntimeError("Extracted TEST smoke failed; do not deliver this package.")
        evidence = {
            "archive": ARCHIVE.name,
            "archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
            "source_files_verified": len(manifest),
            "python_suite": tests.stdout.strip(),
            "extracted_TEST_smoke": json.loads(smoke.stdout.strip().splitlines()[-1]),
            "published_URL_verified": False,
            "physical_device_tests_performed": False,
        }
        (OUT / "verification.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    manifest = build()
    if args.verify:
        verify(manifest)
    print(f"Package prepared: {ARCHIVE.relative_to(ROOT)}")
