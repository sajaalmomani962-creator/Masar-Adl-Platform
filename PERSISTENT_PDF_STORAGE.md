# Private persistent PDF storage

## Implemented and active

The current **development preview** uses Replit App Storage for **new PDF
uploads**. `/health` reports `document_storage: app_storage`. The Python SDK
uses the explicitly configured project bucket and Replit-managed development
authentication. No production connection/credentials or live SQL database were
used. This is an additional storage integration, not a government or AI API.

Existing local files remain readable in place. No existing file was uploaded,
migrated, deleted, renamed or re-permissioned automatically.

## Unchanged application contracts

- Existing Python/FastAPI/Jinja application, authentication, seven roles,
  permissions, ten-table SQL schema, seed and workflows are retained.
- The existing `documents.file_name` holds an opaque versioned reference for
  new cloud objects. No new column, table or replacement database is needed.
- References contain a random identifier, repository scope and SHA-256 digest,
  not a person's name, national ID, case title, bucket credential or signed URL.
- Object namespaces separate actual `demo` and `sqlserver` repository modes.
- Every view/download/print/preview first passes the original authorization
  decision. Only then may the backend contact storage. No public object route
  or browser-readable signed URL was added.
- Responses preserve `application/pdf`, inline/attachment disposition,
  no-store caching, byte-range behavior and audit logging.
- Downloaded objects are checked for PDF signature, size and digest before
  being returned. This is not malware scanning or legal signature verification.
- Per-response transfer files are owner-only, outside static folders, and
  removed on completion/error/disconnection. HTML print/preview checks do not
  create a transfer file.
- Missing objects and outages fail explicitly; they never silently fall back
  to local files or cause fabricated sample PDFs to replace cloud objects.
- Invalid references and cross-scope references are denied before storage IO.

## Configuration

| Variable | Meaning |
|---|---|
| `PDF_STORAGE_BACKEND=local` | Default portable/offline backend for new writes |
| `PDF_STORAGE_BACKEND=app_storage` | Write new PDFs to the private cloud bucket |
| `MASAR_PDF_BUCKET_ID` | Explicit non-secret bucket selector, required for cloud writes/reads |
| `STORAGE_DIR` | Legacy private files and temporary per-response transfers |

Configure values through the environment configuration, not committed files.
The SDK dependency is recorded in requirements, `pyproject.toml` and `uv.lock`.
The current activation was scoped to **development**, not an untested production
deployment. No raw platform credentials are embedded or logged.

Do not change the selected bucket while references to it remain in metadata
without an approved migration. A backend write rollback to `local` does not
disable reads of previously saved cloud references: keep their bucket selector.
Legacy filenames always resolve locally; cloud errors do not search local
storage. No automatic cross-backend migration or destructive garbage collection
was added.

The supplied React/Express/PostgreSQL storage template was not transplanted into
this Python/SQL Server application. The official Python SDK is used behind the
existing server-side policy instead.

## Actual verification

- Full Python suite: **178 passed**, including 31 additive private-storage cases.
- Full browser suite: **16 passed in one complete run**, Chromium desktop and
  mobile/touch emulation. Its ordinary fixtures deliberately use local storage
  so browser regressions cannot contact a cloud service or real database.
- A separate **real App Storage** probe used one freshly generated TEST PDF:
  1. An independent writer process uploaded it and exited.
  2. A fresh reader process used a separate empty local storage directory and
     an injected TEST-only repository with the known reference fixture.
  3. Authorized application view/download/raw-print responses returned the
     original SHA-256-matching PDF; a byte-range read returned 206.
  4. Another TEST citizen received 404; a subsequent revoked-document read
     received 403. Per-response transfer files were removed.
  5. An unauthenticated direct cloud read received a denial (403/404).
  6. Only that probe's own object was deleted; its absence was checked.
- All probe flags passed. No production metadata, existing objects, live SQL,
  SQL scripts or real user data were used.

Repeat the explicit cloud probe only in an approved development environment:

```sh
python artifacts/masar-al-adl/masar_adl/tools/verify_private_storage.py
```

It uses `MASAR_PDF_BUCKET_ID`; an explicit `--bucket-id` accepts a development
bucket identifier, not credentials. It creates/deletes only its own TEST object.
Ordinary `pytest` and browser tests do not run this external operation.

## Critical durability boundary

**Private PDF bytes are now persistent in App Storage. Demo metadata is not.**

The existing demo repository, sessions and rate limits remain process-local.
Restart/reset restores the seed and loses newly created requests/document
references, even though their cloud bytes remain. The verification reader was
given its known TEST metadata explicitly; this is not automatic restoration of
the demo repository.

The existing SQL Server adapter can store those references in the unchanged
schema when properly configured, but no real SQL connection or write was
performed. This work does not certify a published redeployment, database backup,
multi-instance operation or permanent in-app access after demo resets.

Retention, unused-object cleanup, old-file migration and cloud backup/restore
need an audited policy before production use. In particular, deleting an object
after an uncertain database commit can destroy a valid document, so automatic
cross-system rollback deletion was deliberately not added.

Do not use the demo for important documents. Physical devices, Safari/Firefox/
Edge, native print dialogs and physical printer output remain unverified.

## Official documentation consulted

- https://docs.replit.com/features/data-and-storage/object-storage
- https://docs.replit.com/features/sdks/object-storage-python-sdk
