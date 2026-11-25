# مسار العدل — Masar Al-Adl

Arabic RTL prototype for tracking judicial correspondence. Not an official
government service, not legal advice, and not production-ready.

## Run and verify

- Web: `pnpm --filter @workspace/masar-al-adl run dev`
- Tests: `pnpm --filter @workspace/masar-al-adl run test`
- Standalone: `python artifacts/masar-al-adl/serve.py`
- Normal login: `/login`; presenter-only TEST accounts: `/login?demo=1`
- Mode/health: `/health`
- Main guide: `README.md`; presenter guide:
  `artifacts/masar-al-adl/masar_adl/DEMO_GUIDE.md`

The web artifact runs the existing Python application, not the unused initial
React scaffold. Its managed web service handles both HTML and form submissions.
The shared Node API service is not the judicial application's backend.

## Source

`artifacts/masar-al-adl/masar_adl/` contains the supplied project:
FastAPI web boundary, Jinja2 templates, local Bootstrap RTL and Tajawal assets,
authorization, document access, workflow, repository adapters, integrity and
triage engines. `serve.py` uses the managed `PORT` and defaults to demo mode.
Python dependencies are recorded in root `pyproject.toml`/`uv.lock` and
`requirements.txt`. SQL Server's optional dependency is separate.

## Non-negotiable constraints

- Preserve the original SQL schema and seed in `db/`; never execute these files
  from application code or tests. No migrations, new tables, columns or roles.
- SQL Server is JudicialExchangeDB with exactly ten tables and seven existing
  roles. Do not replace it with PostgreSQL or another database.
- Keep `integrity.py` and `triage.py` as read-only advisory engines; no AI
  authorization, judicial decisions, state transitions or deadline invention.
- All access decisions must be enforced server-side. Citizen ownership, lawyer
  assignment, entity scope, document permissions/visibility and active accounts
  remain mandatory on every request.
- Entity responses require court release before citizen access. Approval and
  rejection require reasons; court-only content must not reach citizens.
- PDFs and application logs stay outside public/static folders and outside Git.
  Never fabricate missing files in live SQL Server mode.
- Keep all original tests and assertions. Baseline was 78 passing; strengthened
  coverage passed 98 tests. The valid approval test now includes its required reason.
- No external SQL Server connection was available for live verification.

## Operational limits

Use one worker only: demo data, server-side sessions and rate limits are in
memory. Demo writes survive requests but not process restarts. Reset restores
the exact seed. SQL mode must fail clearly on connection errors; auto mode may
fall back visibly to demo. Never expose SQL Server publicly.

Sessions, CSRF and rate limiting use the supplied demo authentication design.
Secrets/hashes belong only in the environment's secret manager. New hashes use
Argon2id; legacy scrypt verification is retained. Production identity/MFA,
durable storage, distributed sessions and malware scanning need separate work.

## Interface

Keep Arabic text RTL, Tajawal typography, the specified navy palette, local
assets and non-government scale mark. CSP intentionally disallows inline styles
and scripts. Use external styles/behavior and escaped data attributes. Public
login must not show TEST account details except with the explicit demo query.
