# SQL Server validation status

Checked on 2026-11-25 against the current development workspace.

**Status: live verification deferred; demo development is not blocked.**
The owner confirmed that real connection details are currently unavailable and
authorized continued testing with the existing demo repository and fake driver.
No connection to the owner's JudicialExchangeDB was attempted. This report is
not approval to use the application against live judicial data. See
[VERIFICATION.md](VERIFICATION.md) for the separate demo verification results.

## Actual results

- No SQL Server connection settings or credentials are configured in the
  workspace secret/environment manager. Secret values were not retrieved.
- The integration search returned no Microsoft SQL Server integration.
- Python cannot find `pyodbc`; `odbcinst` is also unavailable. ODBC Driver 18
  availability therefore has not been established.
- `python -m pytest tests/test_sqlserver_repo.py -q`, run from this directory,
  passed all four tests. These use a fake `pyodbc` module, not a SQL Server.
  Even the commit/rollback tests operate only on the fake connection.
- Static inspection of `app/repositories.py` found `Encrypt=yes` and configurable
  certificate trust; `app/config.py` defaults to ODBC Driver 18, database
  `JudicialExchangeDB`, and certificate verification enabled.
- The repository's health query is `SELECT 1`. Its read methods parameterize
  filter values and whitelist identifiers. These are code observations, not
  evidence of live health, schema compatibility, permissions, or row scoping.

No database scripts, DDL, seeds, migrations, or live writes were executed.
No database was substituted, public endpoint created, or application data mode
changed.

## Required before live validation

1. The owner approves a private network route from the validation environment
   to the existing SQL Server. Do not expose SQL Server publicly to unblock
   validation. Confirm the route without sharing private endpoint details in
   chat or committed reports.
2. The owner supplies a dedicated least-privilege, read-only database identity
   through the secure secret manager. It must be able to read only the approved
   tables and metadata; it must not have write, DDL, or procedure-execution
   permissions that can alter data. A client read-only connection hint alone is
   not an access-control boundary.
3. Configure `SQL_SERVER_HOST`, `SQL_SERVER_PORT`, `SQL_SERVER_DATABASE`,
   `SQL_SERVER_USERNAME`, and `SQL_SERVER_PASSWORD` securely. Use the existing
   `JudicialExchangeDB`. Never print a connection string or raw connection error
   that might contain credentials or private endpoint details.
4. Install `pyodbc` and Microsoft ODBC Driver 18 using the supported dependency
   setup. Configure the trusted CA/certificate chain and keep
   `SQL_SERVER_TRUST_CERT=false`; do not bypass certificate validation.
5. Obtain owner-approved scope identifiers for the read queries, without
   committing personal data or identifiers to this report.

## Pending read-only checks

- Confirm Driver 18 is registered, the private route reaches the intended
  server, and certificate/hostname verification succeeds with encryption.
- Instantiate `SQLServerRepository` directly with the read-only identity.
  Do not start normal application workflows or use automatic demo fallback as
  proof of connection; application workflows can write audit/workflow data.
- Run the repository health query and confirm the connected database is
  `JudicialExchangeDB`. Establish the account's effective permissions with the
  owner before business-data queries.
- Compare metadata for the tables and columns in `app/schema.py` against the
  live schema, including types, nullability, keys, and the account's default
  schema/name resolution. Treat restricted metadata visibility as inconclusive,
  not proof that a table is absent. Do not repair mismatches automatically.
- Exercise `get` and `select` only for approved scope identifiers and small,
  bounded result sets. The adapter uses `SELECT *` with no built-in row limit:
  do not run an unfiltered select or read unrelated records. Record only
  pass/fail and sanitized counts, not record contents.
- Report live outcomes and any remaining incompatibilities here. Leave all
  insert/update, transaction-write, application workflow, and write-permission
  validation out of this read-only session.

Live health, encryption negotiation, schema compatibility, scoped query
behavior, and write behavior all remain unverified.
