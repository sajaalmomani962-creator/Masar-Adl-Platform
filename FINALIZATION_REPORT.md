# Finalization report — 2026-11-26

> **Historical report, superseded by `FINAL_DELIVERY_REPORT.md`.** Private cloud
> PDF storage was subsequently implemented and activated in development.
> The latest complete runs pass **178 Python tests and 16 browser cases**.
> See `PERSISTENT_PDF_STORAGE.md` for the actual cloud restart proof and the
> remaining distinction between durable bytes and volatile demo metadata.

## 1. Implemented

- A local, read-only PDF.js preview on `/documents/{id}/preview`, reachable
  through **معاينة بديلة** on authorized document cards. The print page also
  offers this renderer when the browser's built-in PDF viewer is unusable.
- Explicit page loading, previous/next controls, page count, accessible status
  messages, a one-page-at-a-time canvas capped at four million pixels, safe
  failure feedback and the existing protected native-viewer links.
- Local parser/worker assets from the locked `pdfjs-dist` dependency, served
  through an exact filename allowlist. No third-party PDF service or CDN is
  contacted by the renderer. No PDF JavaScript, attachments or annotation
  actions are executed by this preview.
- Additive Python/browser regressions. Existing tests/assertions, schema, seed,
  advisory engines, authorization policies and PDF response contracts remain.
- New private uploads use exclusive creation with owner-only `0600`
  permissions, flushing and `fsync`. Failed writes remove their own partial
  file; collisions/symlinks are not followed or overwritten. Existing files
  and directories are not chmodded, migrated or deleted.

## 2. Bugs and limitations addressed

- A blocked/blank native PDF viewer no longer leaves the user without an
  in-page alternative in the tested Chromium environment.
- New files previously depended on the process umask for privacy; owner-only
  creation is now explicit.
- A failed disk write could leave a partial upload. Cleanup is now tested.
- A filename collision previously could overwrite an existing file; exclusive
  creation now rejects it without touching that file.
- Corrupt/signature-only PDF content produces a bounded preview failure with a
  retry/native-viewer option. Existing extension/MIME/size/signature validation
  is unchanged; this is not a new full PDF sanitizer or malware scanner.
- If the optional JavaScript bundle is unavailable in a Python-only install,
  the original PDF endpoints/native print path still work and the limitation is
  explained instead of silently presenting a broken alternative.

## 3. Tests and exact execution results

| Check | Result |
|---|---|
| Original merged Python baseline | 125 passed |
| Final Python suite | **147 passed, 0 failed** |
| Python compilation | Passed |
| JavaScript syntax checks | Passed |
| Full 16-case Chromium run | 14 passed; 2 new rejection tests failed due to incorrect test role setup |
| Corrected rejection-only rerun | **2 passed**, desktop and phone |
| Final browser coverage across both runs | **All 16 distinct cases verified; no unresolved failures** |
| Running preview | Clean startup after owner-approved restart |

The failed test setup tried to make a judge start review. The real workflow
assigns that step to the clerk. The test now performs clerk review, switches
accounts, and then exercises the judge's rejection. No application permission
was weakened to pass a test. The 14 unaffected successful cases were not rerun
unnecessarily. This is not a claim that a final single full invocation reported
16 green results.

An earlier baseline browser command hit its shell time limit after five desktop
cases passed. That interrupted run was not counted as a successful full run;
the subsequent complete 16-case execution and targeted correction are above.

Tests use disposable local `DemoRepository` applications, TEST accounts and
temporary directories, not the preview's records or any live database. The
browser test server refuses to reuse an occupied port and has no remote-target
override. Original assertions remain; new checks were added.

Run:

```sh
pnpm --filter @workspace/masar-al-adl run test
pnpm --filter @workspace/masar-al-adl run test:browser
pnpm --filter @workspace/masar-al-adl run build
```

Ignored test evidence is under `generated-artifacts/browser/`, including the
initial full-run JSON and screenshots, plus `rejection-recheck/` screenshots for
the corrected targeted run. The initial HTML report retains the two historical
failures; it is not the sole final verdict.

## 4. Storage status and restart durability

**Persistent cloud/private document storage was not activated or represented as
complete.** The safe local-file hardening above was implemented instead.

The storage skill and official App Storage/Python SDK documentation were read.
App Storage can persist private object bytes, but it does not persist this
application's process-local request/document metadata, sessions or permission
state. The supplied demo intentionally resets those records to its exact seed.
Changing the storage provider without a verified metadata and existing-file
mapping could leave inaccessible/orphaned files, or make existing documents
disappear. No bucket provisioning, live-file migration, replacement database,
schema changes or external credential handling was attempted.

Actual restart-boundary checks:

1. An isolated writer process saved a TEST PDF and exited completely.
2. A fresh reader process on the **same filesystem** read identical bytes
   (SHA-256 matched): **passed**.
3. A fresh isolated demo application retained those local bytes but did not
   retain newly created request/document metadata: **passed as the documented
   demo behavior**, not as end-to-end persistence.
4. The owner explicitly approved restarting/resetting the preview; it came up
   cleanly. The isolated browser server was independent of that restart.

**Not verified:** App Storage uploads, cloud object durability, availability after
republishing/replacing a filesystem, shared multi-instance storage, persistent
uploaded-document access after a demo restart, backup/restore or live SQL
metadata. Do not use the preview for important documents.

Required future storage work must keep the existing server-side authorization,
private namespaces and existing document schema, with an audited migration
strategy and a non-destructive cloud restart test using TEST objects only.
The generic React/PostgreSQL/authentication blueprint was not substituted for
the supplied Python/SQL Server application.

References consulted:

- https://docs.replit.com/features/data-and-storage/object-storage
- https://docs.replit.com/features/sdks/object-storage-python-sdk

## 5. PDF/browser/device compatibility

| Environment / behavior | Actual result |
|---|---|
| System Chromium 155.0.8059.79, Linux, 1440×1000 | Verified |
| Same Chromium, mobile/touch emulation, 390×844 | Verified; not a physical phone |
| Ten TEST accounts / seven roles | Dashboard, navigation, logout and notification coverage passed |
| Land, civil-status and generic-government workflows | Passed on both viewports |
| Local preview of generated Arabic-watermarked TEST PDF | Canvas rendered nonblank document content on both viewports |
| Two-page embedded-font TEST PDF | Previous/next controls and boundary states passed on both viewports |
| Malformed TEST PDF | Explicit recoverable failure passed on both viewports |
| Native embedded PDF viewer | Previously blocked/blank in headless Chromium; not certified |
| Protected raw/view/download responses | Permission/status/content-type/PDF-byte checks passed |
| Physical Android/iPhone, Safari, Firefox, Edge | Unavailable; not tested |
| Native OS print dialog / physical paper output | Unavailable; not tested |
| Encrypted, digitally signed, XFA, complex forms, all languages/fonts/codecs | Not certified |
| PDF screen-reader/text accessibility | Canvas is image-only; original PDF remains the text/accessibility path |

Firefox/WebKit executables were not installed. The runner used the actually
available system Chromium, not Playwright's absent bundled Chromium. No
physical-device, cross-browser or printing pass is inferred from emulation.

The alternative preview is deliberately excluded from browser-page printing so
it cannot silently print only the currently displayed page as if it were the
whole document. Use the protected native PDF path for full-document printing.

## 6. Security and authorization

- New preview access uses the same `view` decision as existing PDF access;
  raw page bytes are fetched through the existing audited protected endpoint.
- All ten TEST accounts have explicit preview access/denial checks. Unrelated
  users receive 404; related but disallowed access receives 403.
- Unreleased responses, revoked documents, other citizens' records and lawyer
  attachments remain protected. Print/download permission is not granted by
  preview access. Repeated raw requests recheck authorization.
- Existing CSRF, national-ID/password/demo-token login, session expiry,
  throttling, safe errors, internal-note privacy, audit and release policies
  remain unchanged and covered by the preserved suite.
- No uploaded files are mounted publicly. Static library serving uses an exact
  allowlist. PDF evaluation is disabled; no PDF scripts/attachment actions are
  wired into the renderer. The content-security policy was not relaxed.
- SQL schema/seed, `authz.py`, triage/integrity rules and live database were not
  changed or executed. No live credentials, real user data or SQL scripts were
  used for verification.
- This is regression verification, not a penetration test or security
  certification. Malware scanning and production identity requirements remain.

## 7. Remaining blockers / external checks

- Safely provisioned, isolated private cloud storage and an approved persistent
  metadata/existing-file strategy; full restart/redeploy durability is pending.
- Secure TEST SQL Server access to verify the existing adapter against a real
  database. Mock adapter tests are not proof of real connectivity or transactions.
- Physical-device native PDF viewing/file-picker MIME behavior and actual print
  output; actual Safari/Firefox/Edge verification.
- Production identity/MFA, malware scanning, backups, operational monitoring,
  concurrency and multi-instance session/rate-limit design.
- Existing separately proposed authorization/concurrency/database-resilience
  tasks are not claimed complete by these regressions.

## 8. Delivery decision

**Ready for delivery as a clearly labeled TEST/demo prototype.**
The safe changes are implemented, checked and loaded in the running preview.
**Not ready for live judicial/production data or a guarantee of durable uploaded
documents.** Deferred storage, infrastructure and physical-device checks are
explicit blockers to that stronger claim.
