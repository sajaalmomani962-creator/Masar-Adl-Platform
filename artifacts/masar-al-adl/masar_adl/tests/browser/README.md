# Authenticated browser regressions

Run from the workspace root:

```sh
pnpm --filter @workspace/masar-al-adl run test:browser
```

This complements, rather than replaces, the original Python suite:

```sh
pnpm --filter @workspace/masar-al-adl run test
```

## Browser setup

The dependency is locked in the workspace. Replit's Chromium at
`/repl/tools/bin/chromium` is used when available. Elsewhere install the matching
Playwright browser once:

```sh
# After syncing project changes, install the locked JavaScript dependencies:
pnpm install --frozen-lockfile
pnpm --filter @workspace/masar-al-adl exec playwright install chromium
```

Use Node.js 24+ and the project's Python dependencies (the pinned PDF renderer
requires a modern Node runtime). Chromium also requires its
normal operating-system libraries.

## Safety and isolation

- The runner starts `server.py` as a disposable local test server on
  `127.0.0.1:8765`; an occupied port fails rather than reusing another server.
- The server explicitly injects `DemoRepository` and verifies TEST fixture
  identities. It never imports `main:app`, selects SQL/auto mode, runs database
  scripts, calls reset, or targets the preview/production database.
- PDF uploads and logs live in a temporary directory, removed on server exit.
  The test-only `/__TEST_fixture.pdf` route returns a constant generated TEST PDF.
  It is not added to the real application's routes.
- Each test uses fresh browser cookies and logs in using the existing UI and
  login tokens. Role changes use the real logout/login forms. CSRF,
  authorization, required reasons, native dialogs and file validation stay on.
- Each new request has a unique TEST title. No seed record is edited, no
  permission rows are changed, and existing tests and assertions are unchanged.
- Browser coverage deliberately has no remote base URL override.

## Coverage

Both projects run the same assertions: desktop Chromium at 1440×1000 and
touch/mobile Chromium at 390×844. These are responsive emulations, not a claim
of physical-device or Safari/Firefox coverage.

- Public login hides TEST cards; protected routes require login.
- All ten TEST accounts covering all seven roles reach their correct dashboard.
  Session reload/navigation, logout, notifications and mobile menu
  open/Escape/focus are checked; dashboards must not overflow the viewport.
- Normal TEST citizen national-ID/password login works.
- Every target entity selects its correct request type, including generic
  official letters and switching back without stale options.
- Three full journeys exercise land, civil-status and generic-government
  officers, on both screen sizes: lawyer saves draft, cannot submit without a
  PDF, uploads and submits; clerk reviews without judge-only controls; judge
  cannot approve without a reason (native empty validation and server-side
  whitespace rejection); clerk sends; the scoped officer processes and uploads;
  court releases; citizen opens the print window.
- An entity cannot access the request before sending. Its unreleased response
  remains hidden under the existing policy; the authorized lawyer can inspect
  it. The citizen cannot view/print before court release and cannot view the
  lawyer's attachment. Another citizen gets 404 for the request and all released
  document URLs.
- Internal notes/reasons stay hidden from the citizen. The print iframe's raw
  endpoint returns the exact uploaded PDF bytes with `application/pdf`.
  This checks the printable PDF, not a physical printer or an OS print dialog.
- Completed court releases no longer offer the release action, including after
  reload. The request remains in the existing `RESPONSE_RECEIVED` status; no
  new database state or permission was introduced.
- Successful journeys and role dashboards retain screenshots. Uncaught page
  script errors fail the journey; failures also retain Playwright traces.

## Reports and targeted runs

Outputs are ignored by Git/deployment under `generated-artifacts/browser/`:
HTML report in `report/`, JSON results in `results.json`, screenshots/traces in
`results/`. The next run replaces these outputs; copy evidence you need before
rerunning.

```sh
pnpm --filter @workspace/masar-al-adl exec playwright show-report ../../generated-artifacts/browser/report
pnpm --filter @workspace/masar-al-adl exec playwright test --project=phone
pnpm --filter @workspace/masar-al-adl exec playwright test --grep civil_officer_dana
```

Tests run serially against one in-memory demo process. Do not increase workers
or set `reuseExistingServer: true`: that would remove predictable isolation.

## Independent visual check limitations

The finalization extension now also tests actual local PDF.js canvas rendering
with nonblank pixel checks, two-page navigation, malformed-file recovery, and
return/rejection workflows at both configured sizes. It does not remove or
weaken existing assertions. The renderer uses authorized raw endpoints and
local library assets; it does not certify the native PDF viewer or printing.
See root `FINALIZATION_REPORT.md` for the exact full/targeted run history.

The separate authenticated browser check completed the civil-status journey,
including mobile notifications/menu/logout and the citizen's print tab. Its
headless PDF viewer showed a blocked placeholder although the authorized raw
URL returned a valid PDF. Embedded PDF rendering and actual printing in
physical-device browsers are **not verified** by this suite.

That check also encountered a TEST PDF labeled `application/octet-stream` by
its upload tool. The existing strict MIME validator correctly rejected it;
supplying the same TEST PDF with `application/pdf` succeeded. No MIME/security
validation was relaxed. Actual device/file-picker MIME behavior warrants
separate cross-browser checks.
