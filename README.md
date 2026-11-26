# مسار العدل — Masar Al-Adl

Arabic-first judicial correspondence tracking prototype based on the supplied
`masar_adl_v6` application and V9 specification.

**نموذج أولي للعرض — ليس نظامًا رسميًا ولا جاهزًا للإنتاج.**
This application is not endorsed by a government body, is not connected to
Jordanian government systems, does not file court cases, and provides no legal advice.

## What is included

- Arabic RTL interface for citizens, assigned lawyers, court clerks, judges, and
  government-entity officers.
- Case follow-up summaries, public timelines, and private in-platform notifications.
- Lawyer draft requests, PDF replacement, submission and resubmission.
- Court review, return for modification, judge approval/rejection, and simulated
  sending to the target entity.
- Entity processing, manually recorded delay, and official-response upload.
- Court-controlled release of responses to citizens.
- Permission-checked PDF viewing, downloading, and dedicated print views.
- Read-only audit filters, R1–R8 path-integrity findings, and printable
  chain-of-custody reports.
- Explainable priority scores, scoped to authorized requests; advisory only.
- Demo reset to the exact supplied seed, without adding or changing seed rows.

### Submission package (`submission-package/`)
The `submission-package/` folder groups the evaluation materials and SQL reference files for the jury:
- `Masar_Al_Adl_Prototype_With_Login_Guide_AR.pdf`: Arabic jury walkthrough, problem-and-solution overview, advisory AI boundaries, and TEST login guide.
- `Masar_Al_Adl_Technical_Architecture_Doc.pdf`: Updated technical and architecture document covering the four-layer design, `RBAC + ABAC`, smart triage (0–100), R1–R8 path integrity / chain-of-custody, database tables, and diagram placeholders.
- `WhatsApp Video 2026-11-26 at 3.31.04 PM.mp4`: Prototype walkthrough video (`Masar Al-Adl` demo walkthrough) for demonstration purposes.
- `judicial_exchange_sqlserver.sql` and `judicial_exchange_seed_data.sql`: Original SQL Server schema and seed reference files (kept unchanged and never executed automatically).

> **Note:** Prototype for demonstration and evaluation only; not an official government system, not production-ready, and not legal advice.

## Technology and source layout

The supplied Python application is preserved rather than rewritten. The web
application is **FastAPI + Jinja2 + Bootstrap 5 RTL**, with a repository interface
for in-memory demo data or SQL Server. The initial web scaffold is not the running
application; no Node service handles judicial data or authentication.

```text
README.md                              This guide
requirements.txt                       Demo/runtime and test dependencies
pyproject.toml, uv.lock                 Workspace Python dependency lock
artifacts/masar-al-adl/
  serve.py                             One-command launcher using PORT
  masar_adl/
    main.py                            ASGI entry point
    app/
      main.py                          FastAPI HTTP boundary and safe errors
      auth.py, authz.py                 Authentication and central RBAC + ABAC
      repositories.py, schema.py        Data access and schema validation
      workflow.py                      Explicit workflow transition table
      documents.py                     Private PDFs and permission enforcement
      integrity.py, triage.py           Existing read-only rule engines
      templates/, static/              Shared Arabic interface
      resources/                       Licensed Arabic PDF font
    db/                                Original SQL references; never executed
    tests/                             Original suites plus hardening regressions
    scripts/make_pin_hash.py            Interactive Argon2id hash generator
    DEMO_GUIDE.md                       Presenter steps and TEST account list
```

## Competition handover

See [دليل المسابقة والتحكيم](COMPETITION_GUIDE_AR.md) for the judge walkthrough,
portable Python startup, publication checklist and explicit demo limitations.
Build and check a source-only archive with:

```bash
python scripts/package_competition.py --verify
```

The archive and actual extraction-test evidence are written to the ignored
`generated-artifacts/submission/` directory. Uploaded files, logs, sessions,
environment files and Git history are excluded. The pinned PDF.js runtime and
its license are included. A working development preview is not proof of a
working published judge URL; that must be checked separately after publishing.

## Run

### In this project

Use the **مسار العدل** preview. The managed web command is:

```bash
pnpm --filter @workspace/masar-al-adl run dev
```

It starts one Python process, binds to `0.0.0.0`, respects the configured `PORT`,
and defaults to demo mode when `DATA_MODE` is unset. Open `/login` for the normal
two-field login or `/login?demo=1` for the explicitly marked demonstration accounts.
`/health` reports the current data mode.

### On a local machine

Python 3.12+ is recommended:

```bash
pip install -r requirements.txt
python artifacts/masar-al-adl/serve.py
```

The standalone launcher defaults to port 8000. Alternatively:

```bash
cd artifacts/masar-al-adl/masar_adl
DATA_MODE=demo uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

Run only **one worker/instance** for this prototype: demo data, sessions and rate
limits are process-local. Demo changes persist across requests and different user
sessions in that process, but reset on restart. The reset action also restores
the original seed.

New PDF bytes can persist independently in private App Storage, but this does
not restore process-local request/document metadata after a demo reset. See
[PERSISTENT_PDF_STORAGE.md](PERSISTENT_PDF_STORAGE.md) for the exact boundary.

## Data modes and SQL Server

| `DATA_MODE` | Behavior |
|---|---|
| `demo` | Exact supplied TEST fixtures, in memory; clear demo banner on every page |
| `auto` | Attempt configured SQL Server connection with a short timeout; fall back to demo with a visible banner |
| `sqlserver` | Require SQL Server; fail with a safe setup message instead of silently falling back |

The original files in `db/` define **JudicialExchangeDB**, exactly ten tables,
seven roles, and the supplied fixed IDs. They are reference-only. Neither the
application nor its tests execute the SQL scripts, create a database, perform
migrations, or modify the seed.

For a deliberate SQL Server setup:

1. Arrange an approved private network/VPN or secure temporary tunnel to the
   existing SQL Server. Cloud `localhost` is not the user's computer.
2. Install the optional Python dependency:
   `pip install -r artifacts/masar-al-adl/masar_adl/requirements-sqlserver.txt`.
3. Provide ODBC Driver 18 for SQL Server in the runtime. It is not forced into
   the demo environment.
4. Configure the variables below through the environment's secret manager.
5. Test connectivity and authorization with **read-only operations first**.

**Never expose SQL Server publicly, disable its firewall, or commit connection
credentials. No live SQL Server was available or tested during this work.**

The owner has deferred live verification because the connection details are
unavailable. This does **not** block development or demonstration: use the
existing in-memory `demo` repository and isolated mock-adapter tests. Do not
invent credentials, substitute a database, or treat a passing demo health
check as evidence of SQL Server connectivity.
The [SQL Server validation report](artifacts/masar-al-adl/masar_adl/SQLSERVER_VALIDATION.md)
records actual prerequisites and the pending read-only checks.

## Environment variables

| Variable | Purpose |
|---|---|
| `PORT` | Listening port; launcher default 8000, managed preview supplies its port |
| `DATA_MODE` | `demo`, `auto`, or `sqlserver`; launcher defaults to `demo` |
| `SQL_SERVER_HOST` | Private reachable SQL Server host |
| `SQL_SERVER_PORT` | SQL Server port; default 1433 |
| `SQL_SERVER_DATABASE` | Existing database; default JudicialExchangeDB |
| `SQL_SERVER_USERNAME` / `SQL_SERVER_PASSWORD` | Database credentials; secrets only |
| `SQL_SERVER_DRIVER` | Default ODBC Driver 18 for SQL Server |
| `SQL_SERVER_TRUST_CERT` | Explicit certificate-trust option; default false |
| `SQL_SERVER_TIMEOUT` | Short connection timeout in seconds; default 5 |
| `SECURE_COOKIES` | Set to 1 over HTTPS; HTTPS requests also automatically get Secure cookies |
| `DEMO_USERS_JSON` | Optional national-ID-to-password-hash mapping; secret only |
| `SESSION_IDLE_SECONDS` | Idle session expiry; default 1800 |
| `SESSION_MAX_SECONDS` | Absolute session expiry; default 28800 |
| `LOGIN_MAX_FAILURES` | Login failures allowed within the rate-limit window; default 6 |
| `STORAGE_DIR` | Private file directory, never a public/static directory |
| `LOG_DIR` | Local application-event directory |
| `TRIAGE_AS_OF` | Optional ISO timestamp override for reproducible scoring |

## Authentication and authorization

The normal login has exactly two visible fields: **الرقم الوطني** and **كلمة السر**.
National IDs are text, not digits-only. The database has no password column, and
none is added.

- Optional password hashes in `DEMO_USERS_JSON` are authoritative for that account.
- New hashes use **Argon2id**; existing scrypt hashes remain supported.
- Without a hash, only demo mode accepts its documented demonstration convention.
  Real SQL Server mode refuses passwords it cannot verify.
- Use `/login?demo=1` in demo mode for labeled TEST accounts and the password
  convention. The normal login panel contains no account list or hints.
- Quick login is demo-only and still requires a valid login token and active
  account. It is not a production identity mechanism.
- Logout invalidates server-side sessions; idle/absolute timeouts, HttpOnly,
  SameSite=Lax, HTTPS Secure cookies, CSRF checks, and login rate limits apply.
- RBAC + ABAC decisions are enforced on the server, including record ownership,
  lawyer assignment, target entity, activity status, document type, visibility,
  and operation permission. Unknown/unrelated records do not reveal their existence.

Generate a hash interactively without putting a password in shell history:

```bash
cd artifacts/masar-al-adl/masar_adl
python scripts/make_pin_hash.py
```

Store the resulting mapping in `DEMO_USERS_JSON` through a secret manager, not
in source files, documentation, or SQL. Production requires an owner-approved
authentication method or national digital identity and additional hardening.

## Workflow and privacy

```text
DRAFT → SUBMITTED → UNDER_COURT_REVIEW → APPROVED
      → SENT_TO_ENTITY → UNDER_PROCESSING → RESPONSE_RECEIVED
```

Exceptional states are `RETURNED_FOR_MODIFICATION`, `REJECTED`, and `DELAYED`.
Only the allowed role in the allowed state may perform an action. A judge's
approval or rejection requires a written reason; reasons remain internal.
Successful transitions atomically update status, timeline, audit records, and
notifications. Rejected attempts are audited where the schema allows.

Entity responses remain court/lawyer-only until an authorized court user releases
them to the citizen. PDF uploads require a PDF extension, MIME type, signature,
and maximum 10 MiB size. Files use generated names in private storage.
New uploads in the current development preview use private App Storage with
opaque references in the existing filename column; legacy local files remain
in place. All file access still passes the same server-side authorization.
Demo startup creates the three seed-referenced sample PDFs with the Arabic stamp
**مستند تجريبي**. Live-data mode never fabricates missing documents.

Every document view, download and print-view opening—including a direct raw-PDF
URL—is permission checked and audited. A print event records opening the print
view, not proof that a physical printer completed printing.

## Priority, integrity and seed anomalies

`triage.py` and `integrity.py` retain the supplied rule engines. They never approve,
reject, send, change state, or change permissions. No external AI service is used.

- Priority scores are explainable, advisory, and shown only to court/entity roles.
- Demo scoring uses the latest data timestamp, not an invented legal deadline.
- Integrity checks flag chronology, missing milestones, actor mismatches, missing
  response documents, decision/audit inconsistencies, and access-policy anomalies.
- The seed intentionally includes anomalous history. Audit entry 4 and incomplete
  request histories must remain visible to the checker, not be "fixed" by changing
  seed data. Current access checks still deny that unrelated citizen access.

## Tests

```bash
pnpm --filter @workspace/masar-al-adl run test
# or
cd artifacts/masar-al-adl/masar_adl
python -m pytest -q tests
```

The original upload was run before application changes: **78 passed**.
After the migration, interface update and initial hardening: **93 passed**.
The latest delivery verification (2026-11-26) passes **178 Python tests**
and **16 browser cases in one complete run**, with no failures.
See [FINAL_DELIVERY_REPORT.md](FINAL_DELIVERY_REPORT.md) for the private-cloud
restart proof, exact scope, remaining limitations and delivery decision.
All original tests and assertions are retained. The successful approval scenario
now supplies a reason, matching V9, and new regressions explicitly reject approval
without one. Added coverage includes FastAPI identity, Argon2id/legacy hash
verification, raw-PDF auditing, HTTPS cookies, live-mode document safety, invalid
transition inputs, restricted response visibility, and inactive-entity sessions.
Additional checks cover exact dashboard/record access for all ten TEST accounts,
all four entity accounts processing their own requests, notification ownership,
missing-PDF draft recovery, invalid-upload form preservation, and hiding completed
response-release actions. Build compilation and JavaScript syntax checks pass.

An authenticated desktop browser also completed the lawyer → clerk → judge →
entity → court release → citizen lifecycle, including PDF endpoints and private
reason visibility checks. All ten TEST accounts passed dashboard/menu,
notification and logout checks at **1440 × 1000** and **390 × 844**. Phone browser
checks also passed the judge's audit/integrity filters and custody report, and
the lawyer's invalid-upload → retained form → saved draft → PDF upload → submission
recovery journey. Mock tests cover rejection, return/resubmission,
delay/resume, invalid uploads, document permissions, CSRF, sessions and atomic
rollback; these are not claims of live SQL Server behavior.
See the [verification report](artifacts/masar-al-adl/masar_adl/VERIFICATION.md)
for the role/device results and remaining limits.

Upload-validation errors preserve the title, case, entity and request type.
If submission fails after a draft was saved, the lawyer is taken to that existing
draft instead of an empty creation form. Browsers still require the file to be
selected again after an error. Protected standalone print links are retained
when a browser's embedded PDF viewer is unavailable.

## Known limitations

1. **Not production-ready.** No real government integration, real identity
   verification, email, SMS, or legally approved deadlines are implemented.
2. SQL Server is supported through the supplied adapter, but only its fake-driver
   tests have run; a real secure SQL Server connection is unverified.
3. Demo changes, sessions and rate limits are in memory and lost on restart.
   New PDFs in development use private App Storage; legacy local files are not
   migrated. Persistent bytes do not make demo request/document metadata durable.
4. `audit_logs` requires an actor and case. Login failures or unknown records
   cannot be inserted there; applicable events use the application logger instead.
5. There is no administrator/independent-monitor role. Judges see the audit log;
   clerks see only cases they handled. Production monitoring needs a separately
   approved policy; no extra role or table was added.
6. Seed permissions deliberately omit entity access to lawyer PDFs and public
   status certificates. Court staff also have type-specific printing restrictions.
   No permission row is silently added to bypass these limits.
7. A single court exists in the seed. Court staff share that court's case scope.
8. PDF validation is not malware scanning, content sanitization, or digital
   signature verification. Those, MFA, distributed sessions/rate limits and
   production storage/backup/retention verification remain production requirements.
9. Integrity rules detect observable inconsistencies, not fraud or legal fault.
   Priority weights need real-world calibration and are not binding decisions.
10. Native embedded PDF viewing depends on browser support. The headless test browser
    blocked its built-in PDF viewer, although the protected PDF endpoints
    returned valid bytes. The print page includes a protected standalone-window
    link and a local read-only PDF.js alternative. Actual canvas rendering and
    two-page navigation were checked in desktop/mobile-emulated Chromium; native
    print-dialog output and physical printer output were not verified.
11. Browser verification uses the demo environment and emulated viewports,
    not live government services or physical phones. See the verification report
    for the exact coverage; native printer completion is not verified.

**Proposed schema changes: none applied.** If entity access to lawyer attachments
or an independent audit role is desired later, it requires an explicit policy
decision and separate approval, not a change hidden in this implementation.
