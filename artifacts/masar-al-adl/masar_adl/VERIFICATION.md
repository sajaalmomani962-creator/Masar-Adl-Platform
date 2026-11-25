# Demo verification — 2026-11-25

> **Latest delivery:** root `FINAL_DELIVERY_REPORT.md` supersedes the previous
> results below: **178 Python tests and all 16 browser cases passed**.
> Private App Storage was enabled for new PDFs in development, with an actual
> writer-exit/fresh-reader TEST probe, anonymous denial and cleanup checks.
> Demo request/document metadata is still not persistent.

> **Updated finalization, 2026-11-26:** see root `FINALIZATION_REPORT.md`.
> The final Python suite passes **147** tests. New local PDF rendering and
> two-page controls were verified in desktop/mobile-emulated Chromium.
> The complete browser run had 14 successes and two test-setup failures;
> after correcting the clerk/judge handoff, both targeted rejection checks passed.
> No unresolved failures remain in these 16 checked cases. Persistent cloud
> storage and actual physical-device/native printing remain unverified.
> The following sections preserve the earlier verification record.

## Scope and environment

The owner confirmed that real SQL Server connection details are unavailable.
Testing therefore uses the existing `DemoRepository`, original TEST fixtures,
and fake `pyodbc` adapter tests. No replacement database was added.
The running preview's `/health` reports `status=ok`, `data_mode=demo`.
No production publication or live database access was performed.

Automated tests create isolated applications with temporary document/log
directories. Browser tests use only TEST identities and in-memory demo records.
The one workflow restart needed to load fixes reset demo records and sessions,
as expected for this single-process prototype.

## Automated results

| Check | Actual result |
|---|---|
| `pnpm --filter @workspace/masar-al-adl run test` | 125 passed after combining the parallel regression fixes |
| `pnpm --filter @workspace/masar-al-adl run build` | Passed Python compilation |
| `node --check artifacts/masar-al-adl/masar_adl/app/static/app.js` | Passed |
| Managed web workflow startup | Clean application startup after restart |
| SQL Server adapter unit tests (included above) | Four passed, fake driver only |

The original 93 tests remain intact; this verification adds 26 cases for role
journeys and request recovery, alongside six regression cases from the parallel
testing work. The pre-sync suite passed 119 tests; the combined suite passes 125.

### Role and workflow coverage in isolated HTTP tests

All ten TEST accounts are checked for exact home routing, permitted/forbidden
dashboards, owned/assigned cases, visible request IDs, court-only audit/integrity
access, lawyer-only request creation, notification access, and logout.
Notification read actions are checked not to alter another account's records.

| Role | TEST accounts | Verified behavior |
|---|---|---|
| Citizen | `citizen_tariq`, `citizen_layla` | Own cases/requests only; drafts hidden; released response documents only |
| Lawyer | `lawyer_omar`, `lawyer_sara` | Assigned cases only; create/draft/upload/submit, replace PDF, return/resubmit |
| Court clerk | `clerk_noor` | Review, return, simulated send, release; judge decisions denied |
| Judge | `judge_adel` | Approval/rejection require reasons; audit, integrity, custody report |
| Land officer | `land_officer_rami` | Own sent requests; process and upload response; foreign requests denied |
| Civil-status officer | `civil_officer_dana` | Own sent requests; process and upload response; foreign requests denied |
| Government-entity officer | `gov_tax_fadi`, `gov_gam_hana` | Each account's own entity scope; empty seed inbox where applicable; processing and response upload |

Existing tests additionally cover delay/resume, invalid transitions, inactive
accounts/entities, CSRF, session expiry, login throttling, password hashes,
security headers, escaped output, ID guessing, path traversal, document
visibility/revocation/printing rules, internal-note privacy, read-only advisory
engines, atomic rollback, and exact seed restoration.

## Browser results

### Desktop lifecycle — passed at 1440 × 1000

Using the actual interface and native confirmation dialogs:

1. Lawyer created a civil-record request on case 1 with a valid PDF.
2. Clerk began review; no judge-approval action appeared for the clerk.
3. Judge approved with a private reason.
4. Clerk performed simulated sending to the entity.
5. Civil-status officer began processing and uploaded a PDF response.
6. Before court release, the citizen saw pending review and no document links.
7. Clerk released the response.
8. Citizen then saw response view, download and print links, and a response
   notification. Authenticated requests to those three endpoints succeeded;
   view/download returned PDFs with the appropriate content disposition.
9. Lawyer saw both request and response documents after release.

The judge's private reason was absent from citizen request/notification/print
HTML and lawyer request HTML. Direct pre-release denial and lawyer access to the
unreleased response are verified by automated HTTP tests, not this browser run.
Actual OS printing is not verified.

### All-account navigation — passed at both viewport sizes

The same browser session checked **each of the ten accounts listed above** at
1440 × 1000 and 390 × 844. For each account, the correct dashboard rendered,
the phone menu opened, role-appropriate navigation links appeared, notifications
opened from the menu, and logout returned to login.

Case and request scoping matched the seed: Tariq/Omar saw case 1,
Layla/Sara case 2, Rami request 1, Hana request 2, and Dana/Fadi empty seed
inboxes. Court menus included audit and integrity; other roles did not.
Entity breadcrumbs showed case numbers without forbidden case links.
Cross-role denials were also exercised; these correctly add test-denial audit
entries to the demo log.

There was no document-wide horizontal overflow at either width and no reported
application console errors. Wide tables/progress trackers scroll within their
own containers; their details/actions remain reachable. These are emulated
browser viewports, not physical-device or cross-browser certification.

At phone size, the judge's audit `FAILURE` filter returned failure rows,
the integrity high-severity filter worked, and the request 1 custody report
rendered with usable controls. Integrity summary counts intentionally describe
the full scope; only the findings list is filtered. Report links in the findings
list refer to requests with findings; other authorized reports remain reachable
directly.

Minor visual observations remain: the demo-reset label wraps in the desktop
court header, and mixed Arabic/Latin case-number text may reorder visually.
Neither blocked navigation or actions; mixed-direction typography has not been
certified across browsers.

### Corrected phone request-form journey

Passed at 390 × 844 as `lawyer_omar`:

1. A `.pdf` with the correct MIME type but invalid content was rejected on the
   new-request form. Case 1, entity 3, `CIVIL_RECORD_CHECK` and the unique title
   remained selected. JavaScript restored the request-type selection correctly.
   No request was created. The browser verified the rendered error; the exact
   validation-error status is asserted separately by the automated regression.
   The combined implementation consistently uses HTTP 422 for form validation
   errors while preserving the same rendered recovery behavior.
2. Submitting without a file then opened one saved draft, showed the explicit
   not-submitted warning and PDF upload controls, and did not claim submission.
3. Uploading a valid PDF left that request in draft state with a document card.
4. Submitting the draft changed it to submitted, displayed the court-review
   message, and added the submission history entry without creating a duplicate.

No phone page overflow or application console errors were reported. The hidden
release action after release is verified by the automated tests for each entity's
response workflow; it was not rerun in the browser.

## Issues corrected

- Missing-PDF submission now opens the saved draft with a warning and upload
  controls, instead of sending the lawyer back to a blank new-request form.
- Rejected uploads retain the case, entity, request type and escaped title.
  Browsers require users to select a file again; the error explains this.
- Entity request breadcrumbs no longer link to forbidden case-detail pages.
- Court release actions disappear when no unreleased response remains.
  Server-side checks still reject invalid/repeated actions.

PDF MIME validation remains strict; an upload sent as
`application/octet-stream` is rejected rather than weakening validation to
accommodate the browser-test harness.

The combined implementation also retains server-rendered request-type options
and a protected standalone print-window link from the parallel testing work.
Embedded PDF rendering and native printing still depend on the browser: an
authorized PDF endpoint returning valid bytes does not prove successful rendering
or physical printing.

## Requires the real database or external infrastructure

None of the following is claimed as verified:

- Private network connectivity, ODBC Driver 18 registration, SQL Server
  authentication, encryption/certificate negotiation, live health, live schema
  compatibility, effective database permissions or scoped queries.
- Real database writes, transactions, concurrency or production performance.
- Real government sending, identity verification, email/SMS, digital signatures,
  antivirus scanning or physical printing.
- Durable shared file/session storage and multi-instance operation.

See [SQLSERVER_VALIDATION.md](SQLSERVER_VALIDATION.md) for the pending read-only
procedure. Demo writes are process-local and reset on restart. Seed anomalies
and intentionally restrictive document permissions remain unchanged.
